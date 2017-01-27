import attr
import click
import subprocess
import sys

from .base import BasePlugin
from ..cli.argument_types import ContainerType, HostType
from ..cli.colors import RED
from ..docker.introspect import FormationIntrospector


@attr.s
class AttachPlugin(BasePlugin):
    """
    Plugin for attaching into a running container
    """

    def load(self):
        self.add_command(attach)


@click.command()
@click.argument("container", type=ContainerType())
@click.option("--host", "-h", type=HostType(), default="default")
@click.option("--shell", default="/bin/bash")
@click.pass_obj
def attach(app, container, host, shell):
    """
    Attaches to a container
    """
    # See if the container is running
    formation = FormationIntrospector(host, app.containers).introspect()
    for instance in formation:
        if instance.container == container:
            # Launch into an attached shell
            status_code = subprocess.call(["docker", "exec", "-it", instance.name, shell])
            sys.exit(status_code)
    # It's not running ;(
    click.echo(RED("Container {} is not running. It must be started to attach.".format(container.name)))
