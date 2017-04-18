import os
import sys
import base64
import click
import subprocess

from .base import BasePlugin
from ..docker.introspect import FormationIntrospector
from ..exceptions import DockerRuntimeError
from ..constants import PluginHook


class SSHAgentPlugin(BasePlugin):
    """
    Plugin for running an SSH agent container at boot.

    This container needs special handling as it needs local keys injected into
    environment variables at runtime.
    """

    CONTAINER_NAME = "ssh-agent"

    requires = ["boot-containers"]

    def load(self):
        self.add_hook(PluginHook.PRE_BUILD, self.pre_build)
        self.add_hook(PluginHook.PRE_START, self.pre_start)

    def pre_build(self, host, container, task):
        """
        Injects the SSH_AUTH_HOST variable into builds if it's needed.
        """
        # TODO: Rename this to SSH_AUTH_HOST
        # See if this container needs ssh-agent during build
        uses_ssh, required = self.container_needs_ssh(container, "build")
        if not uses_ssh:
            return
        # See if the SSH auth container is running
        if self.ssh_container_running(host):
            if 'SSH_AUTH_HOST' in container.possible_buildargs:
                container.buildargs['SSH_AUTH_HOST'] = host.build_host_ip
            # TODO Deprecate TUGBOAT_SSH_AUTH_HOST by deleting the below lines.
            if 'TUGBOAT_SSH_AUTH_HOST' in container.possible_buildargs:
                container.buildargs['TUGBOAT_SSH_AUTH_HOST'] = host.build_host_ip
        elif required:
            raise DockerRuntimeError(
                "The container {} needs an SSH Agent to build but one is not started".format(container.name),
            )

    def pre_start(self, host, instance, task):
        """
        Catches the ssh-agent container being started and gives it the right
        environment variables, as well as passing the auth details into containers.
        """
        # See if it's the ssh-agent container that we need to give runtime config to
        if instance.container.name == self.CONTAINER_NAME:
            for i, path in enumerate(self.key_paths()):
                instance.environment["SSHKEY%s" % i] = self.read_key(path)
                task.add_extra_info("Key {}: {}".format(i, path))
        # Or another container that needs the env variable
        else:
            # See if this container needs ssh-agent during build
            uses_ssh, required = self.container_needs_ssh(instance.container, "run")
            if not uses_ssh:
                return
            # See if the SSH auth container is running
            if self.ssh_container_running(host):
                instance.environment['SSH_AUTH_HOST'] = host.build_host_ip
                # TODO Deprecate TUGBOAT_SSH_AUTH_HOST by deleting the below line.
                instance.environment['TUGBOAT_SSH_AUTH_HOST'] = host.build_host_ip
            elif required:
                raise DockerRuntimeError(
                    "The container {} needs an SSH Agent to run but one is not started".format(instance.container.name)
                )

    def container_needs_ssh(self, container, phase):
        """
        Returns (True, True) if the container needs SSH to start,
        (True, False) if it can use it but doesn't require it, or
        (False, False) if it doesn't need it.
        """
        configs = container.get_ancestral_extra_data("boot")
        uses_ssh = False
        required = False
        for config in configs:
            for name, required in config.get(phase, {}).items():
                if name == self.CONTAINER_NAME:
                    required = required.lower().strip() == "required"
                    uses_ssh = True
        return uses_ssh, required

    def ssh_container_running(self, host):
        """
        Returns True if the agent container is running on the host, False otherwise.
        """
        formation = FormationIntrospector(host, self.app.containers).introspect()
        for instance in formation:
            if instance.container.name == self.CONTAINER_NAME:
                return True
        return False

    def key_paths(self):
        """
        Returns paths to the current user's SSH keys
        """
        options = [
            "~/.ssh/id_ecdsa",
            "~/.ssh/id_rsa",
            "~/.ssh/id_dsa",
            "~/.ssh/identity",
        ]
        for option in options:
            path = os.path.expanduser(option)
            if os.path.isfile(path):
                yield path

    def read_key(self, path):
        """
        Returns a key, optionally prompting for passphrase.
        """
        # Read key
        with open(path, "rb") as fh:
            key_contents = fh.read()
        # If it's encrypted, then decrypt it
        if b"ENCRYPTED" in key_contents:
            with self.app.root_task.paused_output():
                print("Decrypting key %s" % path)
                rsa_proc = subprocess.Popen(
                    ["openssl", "rsa"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                key_contents = rsa_proc.communicate(input=key_contents)[0]
                if rsa_proc.returncode:
                    click.echo(click.style(
                        "Incorrect passphrase!",
                        fg="red",
                    ))
                    sys.exit(1)
        # Return key b64 encoded
        return base64.b64encode(key_contents)
