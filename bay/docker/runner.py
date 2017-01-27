import os
import threading
import sys
import time
import dockerpty

from docker.errors import NotFound

from .introspect import FormationIntrospector
from .towline import Towline
from .images import ImageRepository
from ..cli.tasks import Task
from ..exceptions import DockerRuntimeError, DockerInteractiveException, ImageNotFoundException, NotFoundException
from ..utils.threading import ExceptionalThread


network_lock = threading.Lock()


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
        self.images = ImageRepository(self.host)
        self.introspector = FormationIntrospector(self.host, self.formation.graph)
        self.task = task
        # Allows things to override and not have anything stop
        self.stop = stop

    def missing_images(self):
        """
        Verifies that all the images needed to run the formation are present
        on the host. Returns [] if things are good, or the Instances missing
        images if they're not.
        """
        missing = []
        for instance in self.formation:
            try:
                self.images.image_version(instance.image, instance.image_tag)
            except ImageNotFoundException:
                missing.append(instance)
        return missing

    def run(self):
        """
        Runs through and performs all the actions. Blocks until completion.
        """
        self.actions = []
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

    # Stopping

    def stop_containers(self, instances):
        """
        Stops all the specified containers in parallel, still respecting links
        """
        # Work out what containers are linked to the ones we wish to stop
        incoming_links = {}
        current_formation = self.introspector.introspect()
        for instance in instances:
            incoming_links[instance] = set()
            for potential_linker in current_formation:
                links_to = potential_linker.links.values()
                if instance in links_to:
                    incoming_links[instance].add(potential_linker)
        # Parallel-stop things
        to_stop = set(instances)
        stopping = set()
        last_stopping = set()
        stopped = set()
        stop_threads = {}
        while to_stop or stopping:
            # See if we can stop anything new - everything that depends on it must also be stopped
            for instance in list(to_stop):
                if all((linker not in to_stop and linker not in stopping) for linker in incoming_links[instance]):
                    stop_threads[instance] = ExceptionalThread(target=self.stop_container, args=(instance,), daemon=True)
                    stop_threads[instance].start()
                    to_stop.remove(instance)
                    stopping.add(instance)
            # See if anything finished stopping
            for instance in list(stopping):
                if not stop_threads[instance].is_alive():
                    stopping.remove(instance)
                    stopped.add(instance)
                    stop_threads[instance].maybe_raise()
                    del stop_threads[instance]
            # If there's nothing in progress, we've deadlocked
            if (stopping == last_stopping) and to_stop and not stopping:
                raise DockerRuntimeError(
                    "Deadlock during stop: Cannot stop any of {}".format(
                        ", ".join(i.name for i in to_stop)
                    ),
                )
            last_stopping = stopping
            # Don't idle hot
            time.sleep(0.1)

    def stop_container(self, instance):
        stop_task = Task("Stopping {}".format(instance.name), parent=self.task)
        self.host.client.stop(instance.name)
        stop_task.finish(status="Done", status_flavor=Task.FLAVOR_GOOD)

    # Starting

    def start_containers(self, instances):
        """
        Starts all the specified containers in parallel, respecting links
        """
        # Parallel-start things
        current_formation = self.introspector.introspect()
        to_start = set(instances)
        starting = set()
        idle_iterations = 0
        started = set(started_instance for started_instance in current_formation)
        start_threads = {}
        while to_start or starting:
            # See if we can start anything new - everything that it depends on must be started
            for instance in list(to_start):
                if all((dependency in started) for dependency in instance.links.values()):
                    start_threads[instance] = ExceptionalThread(target=self.start_container, args=(instance,), daemon=True)
                    start_threads[instance].start()
                    to_start.remove(instance)
                    starting.add(instance)
                    idle_iterations = 0
            # See if anything finished stopping
            for instance in list(starting):
                if not start_threads[instance].is_alive():
                    starting.remove(instance)
                    started.add(instance)
                    # Collect exceptions from the thread - if it's an interactive exception, run the rest of it.
                    try:
                        start_threads[instance].maybe_raise()
                    except DockerInteractiveException as e:
                        e.handler()
                        sys.exit(0)
                    del start_threads[instance]
                    idle_iterations = 0
            # If there's nothing in progress, we've deadlocked
            if idle_iterations > 10 and to_start and not starting:
                raise DockerRuntimeError(
                    "Deadlock during start: Cannot start any of {}".format(
                        ", ".join(i.name for i in to_start)
                    ),
                )
            idle_iterations += 1
            # Don't idle hot
            time.sleep(0.1)

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
        start_task = Task("Starting {}".format(instance.name), parent=self.task)

        self.remove_stopped(instance)

        # Run plugins
        self.app.run_hooks("pre-start", host=self.host, instance=instance, task=start_task)

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
        volume_mountpoints = []
        volume_binds = {}
        for mount_path, source in instance.container.bound_volumes.items():
            if not os.path.isdir(source):
                raise DockerRuntimeError(
                    "Volume mount source directory {} does not exist".format(source)
                )
            volume_mountpoints.append(mount_path)
            volume_binds[source] = {"bind": mount_path, "mode": "rw"}
        for mount_path, source in instance.container.named_volumes.items():
            volume_mountpoints.append(mount_path)
            volume_binds[source] = {"bind": mount_path, "mode": "rw"}

        for mount_name in instance.devmodes:
            mount_config = instance.container.devmodes[mount_name]
            for mount_path, source in mount_config.items():
                volume_mountpoints.append(mount_path)
                git_match = instance.container.git_volume_pattern.match(source)
                if git_match:
                    source = os.path.abspath("../{}/".format(git_match.group(1)))

                if os.path.exists(source):
                    volume_binds[source] = {"bind": mount_path, "mode": "rw"}
                else:
                    raise NotFoundException("The source path does not exist")

        # Get image, or add container to the not found exception for use further up
        try:
            image_hash = self.images.image_version(instance.image, instance.image_tag)
        except ImageNotFoundException as e:
            e.container = instance.container
            raise e

        # Create container
        container_pointer = self.host.client.create_container(
            image_hash,
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

        # Fetch IP address of container for use in next parts of the code
        container_details = self.host.client.inspect_container(instance.name)
        instance.ip_address = container_details["NetworkSettings"]["Networks"][instance.formation.network]['IPAddress']

        # Loop through all waits and build instances
        wait_instances = []
        for wait in instance.container.waits:
            # Look up wait in app
            try:
                wait_class = self.app.waits[wait["type"]]
            except KeyError:
                raise DockerRuntimeError(
                    "Unknown wait type {} for {}".format(wait["type"], instance.container.name)
                )
            # Initialise it and attach a task
            params = wait.get("params", {})
            params["instance"] = instance
            wait_instance = wait_class(**params)
            wait_instance.task = Task("Waiting for {}".format(wait_instance.description()), parent=start_task)
            wait_instances.append(wait_instance)

        # Check on them all until they finish
        while wait_instances:
            # See if the container actually died
            if not self.host.container_running(instance.name):
                start_task.update(status="Dead", status_flavor=Task.FLAVOR_BAD)
                raise DockerRuntimeError(
                    "Container {} died while waiting for boot completion".format(instance.container.name)
                )
            # Check the waits
            start_task.update(status="Waiting")
            for wait_instance in list(wait_instances):
                if wait_instance.ready():
                    wait_instance.task.finish(status="Done", status_flavor=Task.FLAVOR_GOOD)
                    wait_instances.remove(wait_instance)
            time.sleep(1)

        start_task.finish(status="Done", status_flavor=Task.FLAVOR_GOOD)
