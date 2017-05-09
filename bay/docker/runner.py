import dockerpty
import functools
import os
import sys
import threading
import time

from docker.errors import NotFound

from .introspect import FormationIntrospector
from .towline import Towline
from ..cli.tasks import Task
from ..constants import PluginHook
from ..exceptions import DockerRuntimeError, DockerInteractiveException, NotFoundException
from ..utils.sorting import dependency_sort
from ..utils.threading import ExceptionalThread, ThreadSet


network_lock = threading.Lock()

# Tracks which containers are being started/stopped globally to avoid starting the same one twice.
changing_containers = ThreadSet()


class FormationRunner:
    """
    Takes a ContainerFormation to aim for and a host to run it on, and brings
    the two in line by starting/stopping/configuring containers.

    It can run actions in parallel in background threads if needs be.
    """

    def __init__(self, app, host, formation, task, stop=True):
        self.app = app
        self.host = host
        self.formation = formation
        self.introspector = FormationIntrospector(self.host, self.formation.graph)
        self.task = task
        # Allows things to override and not have anything stop
        self.stop = stop

    def run(self):
        """
        Runs through and performs all the actions. Blocks until completion.
        """
        self.actions = []
        # Check the formation is valid
        self.formation.validate()
        # Work out what containers need turning off, and which need turning on
        # Containers that have changes will need both.
        to_stop = set()
        to_start = set()
        current_formation = self.introspector.introspect()
        for instance in current_formation:
            if instance not in self.formation:
                to_stop.add(instance)
        # Now see if there are any that are entirely new
        for instance in self.formation:
            if instance not in current_formation:
                to_start.add(instance)
            else:
                # It's in both - stop and start if it's changed
                if instance.different_from(current_formation[instance.name]):
                    to_stop.add(instance)
                    to_start.add(instance)
        # Stop containers in parallel
        if to_stop and self.stop:
            self.stop_containers(to_stop)
        # Start containers in parallel
        if to_start:
            self.start_containers(to_start)

    # Shared "dependency-based parallel execution" code

    def parallel_execute(self, instances, ready_to_execute, executor, done=None):
        """
        Runs the "executor" in parallel threads on "instances" when the condition
        "ready_to_execute" is met for an instance. Handles deadlocking as well.
        """
        idle_iterations = 0
        queued = set(instances)
        processing = set()
        done = done or set()
        threads = {}
        while queued or processing:
            # See if we can stop anything new - everything that depends on it must also be stopped
            for instance in list(queued):
                if ready_to_execute(instance, done):
                    threads[instance] = ExceptionalThread(
                        target=executor,
                        args=(instance,),
                        daemon=True,
                    )
                    threads[instance].start()
                    queued.remove(instance)
                    processing.add(instance)
                    idle_iterations = 0
            # See if anything finished stopping
            for instance in list(processing):
                if not threads[instance].is_alive():
                    processing.remove(instance)
                    done.add(instance)
                    # Collect exceptions from the thread - if it's an interactive exception, run the rest of it.
                    try:
                        threads[instance].maybe_raise()
                    except DockerInteractiveException as e:
                        e.handler()
                        sys.exit(0)
                    del threads[instance]
                    idle_iterations = 0
            # If there's nothing in progress, we've deadlocked
            if idle_iterations > 10 and queued and not processing:
                raise DockerRuntimeError(
                    "Deadlock during stop: Cannot stop any of {}.".format(
                        ", ".join(i.name for i in queued),
                    ),
                )
            idle_iterations += 1
            # Don't idle hot
            time.sleep(0.1)

    # Stopping

    def stop_containers(self, instances):
        """
        Stops all the specified containers in parallel, still respecting links
        """
        current_formation = self.introspector.introspect()

        # Inner function that we can pass to dependency_sort
        @functools.lru_cache(maxsize=512)
        def get_incoming_links(instance):
            result = set()
            for potential_linker in current_formation:
                links_to = potential_linker.links.values()
                if instance in links_to:
                    result.add(potential_linker)
            return result

        # Resolve container list to include descendency
        instances = dependency_sort(instances, get_incoming_links)
        # Parallel-stop things
        self.parallel_execute(
            instances,
            lambda instance, done: all((linker in done) for linker in get_incoming_links(instance)),
            executor=self.stop_container,
        )

    def stop_container(self, instance):
        # Wait for the global container manipulation lock
        with changing_containers.entry_lock(instance.name):
            # See if it was already stopped
            if not self.host.container_running(instance.name, ignore_exists=True):
                return
            # Stop the container
            stop_task = Task(
                "Stopping {}".format(instance.container.name),
                parent=self.task,
                collapse_if_finished=True,
            )
            self.host.client.stop(
                instance.name,
                timeout=0 if instance.container.fast_kill else 10,
            )
            stop_task.finish(status="Done", status_flavor=Task.FLAVOR_GOOD)

    # Starting

    def start_containers(self, instances):
        """
        Starts all the specified containers in parallel, respecting links
        """
        current_formation = self.introspector.introspect()
        self.parallel_execute(
            instances,
            lambda instance, done: all((dependency in done) for dependency in instance.links.values()),
            executor=self.start_container,
            done=set(started_instance for started_instance in current_formation),
        )

    def remove_stopped(self, instance):
        """
        Sees if there is a container with the same name and removes it if
        there is and it's stopped.
        """
        if self.host.container_exists(instance.name):
            if self.host.container_running(instance.name):
                raise DockerRuntimeError("The container {} is already running.".format(instance.container.name))
            else:
                self.host.client.remove_container(instance.name)

    def start_container(self, instance):
        """
        Creates the Docker container on the host, ready to be started.
        """
        # Make sure it's not an abstract container being started.
        if instance.container.abstract and not instance.foreground:
            raise ValueError("You cannot boot an abstract container.")

        # Wait for the global container manipulation lock
        with changing_containers.entry_lock(instance.name):
            # See if the container was already started
            if self.host.container_running(instance.name, ignore_exists=True):
                return

            start_task = Task(
                "Starting {}".format(instance.container.name),
                parent=self.task,
                collapse_if_finished=True,
            )

            self.remove_stopped(instance)

            # Run plugins
            self.app.run_hooks(PluginHook.PRE_START, host=self.host, instance=instance, task=start_task)

            # See if network exists and if not, create it
            with network_lock:
                try:
                    self.host.client.inspect_network(instance.formation.network)
                except NotFound:
                    self.host.client.create_network(
                        name=instance.formation.network,
                        driver="bridge",
                    )

            # Create network configuration for the new container
            networking_config = self.host.client.create_networking_config({
                instance.formation.network: self.host.client.create_endpoint_config(
                    aliases=[instance.formation.network],
                    links=[
                        (link.name, alias)
                        for alias, link in instance.links.items()
                    ]
                ),
            })

            # Work out volumes configuration
            volume_mode = "rw,cached" if self.host.supports_cached_volumes else "rw"
            volume_mountpoints = []
            volume_binds = {}
            for mount_path, source in instance.container.bound_volumes.items():
                if not os.path.isdir(source):
                    raise DockerRuntimeError(
                        "Volume mount source directory {} does not exist".format(source)
                    )
                volume_mountpoints.append(mount_path)
                volume_binds[source] = {"bind": mount_path, "mode": volume_mode}
            for mount_path, source in instance.container.named_volumes.items():
                volume_mountpoints.append(mount_path)
                volume_binds[source] = {"bind": mount_path, "mode": volume_mode}

            # Add any active devmodes
            for mount_name in instance.devmodes:
                for mount_path, source in instance.container.devmodes[mount_name].items():
                    volume_mountpoints.append(mount_path)
                    source = os.path.abspath(source)
                    if os.path.exists(source):
                        volume_binds[source] = {"bind": mount_path, "mode": volume_mode}
                    else:
                        raise NotFoundException("The volume source path {} does not exist".format(source))

            # Create container
            container_pointer = self.host.client.create_container(
                instance.image_id,
                command=instance.command,
                detach=not instance.foreground,
                stdin_open=instance.foreground,
                tty=instance.foreground,
                # Ports is a list of ports in the container to expose
                ports=list(instance.ports.keys()),
                environment=instance.environment,
                volumes=volume_mountpoints,
                name=instance.name,
                host_config=self.host.client.create_host_config(
                    binds=volume_binds,
                    port_bindings=instance.ports,
                    publish_all_ports=True,
                    security_opt=['seccomp:unconfined'],
                ),
                networking_config=networking_config,
                labels={
                    "com.eventbrite.bay.container": instance.container.name,
                }
            )

            # Foreground containers launch into a PTY at this point. We use an exception so that
            # it happens in the main thread.
            if instance.foreground:
                def handler():
                    dockerpty.start(self.host.client, container_pointer)
                    self.host.client.remove_container(container_pointer)
                start_task.finish(status="Going to shell", status_flavor=Task.FLAVOR_GOOD)
                raise DockerInteractiveException(handler)

            else:
                # Make a towline instance and wait on it
                self.host.client.start(container_pointer)
                towline = Towline(self.host, instance.name)
                while True:
                    status, message = towline.status
                    if status is None:
                        if message is not None:
                            start_task.update(status=message)
                    elif status is True:
                        break
                    elif status is False:
                        raise DockerRuntimeError(
                            "Container {} failed to boot!".format(instance.container.name),
                            code="BOOT_FAIL",
                            instance=instance,
                        )
                    time.sleep(0.5)

            # Replace the instance with an introspected copy of the live one so it has networking details
            instance = FormationIntrospector(self.host, self.app.containers).introspect_single_container(instance.name)

            # Run plugins
            self.app.run_hooks(PluginHook.POST_START, host=self.host, instance=instance, task=start_task)

            start_task.finish(status="Done", status_flavor=Task.FLAVOR_GOOD)
