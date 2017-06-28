import attr
from docker.errors import NotFound

from .base import BasePlugin
from ..cli.tasks import Task
from ..constants import PluginHook
from ..docker.build import Builder
from ..docker.introspect import FormationIntrospector
from ..docker.runner import FormationRunner


@attr.s
class BuildVolumesPlugin(BasePlugin):
    """
    Plugin for showing information about containers
    """

    requires = ["build"]

    def load(self):
        self.add_hook(PluginHook.PRE_START, self.pre_start)
        self.add_hook(PluginHook.PRE_GROUP_BUILD, self.pre_group_build)
        self.add_hook(PluginHook.POST_BUILD, self.post_build)

    def _get_providers(self):
        providers = {}
        for container in self.app.containers:
            provides_volume = container.extra_data.get("provides-volume", None)
            if provides_volume:
                providers[provides_volume] = container
        return providers

    def pre_start(self, host, instance, task):
        """
        Safety net to stop you booting volume-providing containers normally,
        and to catch and build volume containers if they're needed
        """
        # Safety net
        if instance.container.extra_data.get("provides-volume", None):
            raise ValueError("You cannot run a volume-providing container {}".format(instance.container.name))
        # If the container has named volumes, see if they're provided by anything else
        # and if so, if they're built.
        # First, collect what volumes are provided by what containers
        providers = self._get_providers()
        # Now see if any of the volumes we're trying to add need it
        for _, name in instance.container.named_volumes.items():
            if name in providers:
                # Alright, this is one that could be provided. Does it already exist?
                try:
                    host.client.inspect_volume(name)
                except NotFound:
                    # Aha! Build it!
                    Builder(
                        host,
                        providers[name],
                        self.app,
                        parent_task=task,
                        logfile_name=self.app.config.get_path(
                            'bay',
                            'build_log_path',
                            self.app,
                        ),
                        verbose=True,
                    ).build()

    def pre_group_build(self, host, containers, task):
        """
        Build volume-providing containers for all required volumes.
        """
        providers = self._get_providers()
        volumes_to_build = set()
        for container in containers:
            for volume in container.named_volumes.values():
                volumes_to_build.add(volume)
        for name in volumes_to_build:
            if name in providers:
                Builder(
                    host,
                    providers[name],
                    self.app,
                    parent_task=task,
                    logfile_name=self.app.config.get_path(
                        'bay',
                        'build_log_path',
                        self.app,
                    ),
                    verbose=True,
                ).build()

    def post_build(self, host, container, task):
        """
        Intercepts builds of volume-providing containers and unpacks them.

        Volumes are stored with the ID of the corresponding volume-providing image. This will only run the container
        to recreate the volume if the image's ID (hash) has changed.
        """
        image_details = host.client.inspect_image(container.image_name)
        provides_volume = container.extra_data.get("provides-volume", None)

        def should_extract_volume():
            if not provides_volume:
                return False
            try:
                volume_details = host.client.inspect_volume(provides_volume)
            except NotFound:
                return True
            return volume_details.get('Labels', {}).get('build_id') != image_details['Id']

        if should_extract_volume():
            # Stop all containers that have the volume mounted
            formation = FormationIntrospector(host, self.app.containers).introspect()
            instances_to_remove = []
            for instance in list(formation):
                # If there are no names, then we remove everything
                if provides_volume in instance.container.named_volumes.values():
                    # Make sure that it was not removed already as a dependent
                    instances_to_remove.append(instance)
                    if instance.formation:
                        formation.remove_instance(instance)
            if instances_to_remove:
                stop_task = Task("Stopping containers", parent=task)
                FormationRunner(self.app, host, formation, stop_task).run()
                stop_task.finish(status="Done", status_flavor=Task.FLAVOR_GOOD)
                remove_task = Task("Removing containers", parent=task)
                for instance in instances_to_remove:
                    host.client.remove_container(instance.name)
                    remove_task.update(status="Removed {}".format(instance.name))
                remove_task.finish(status="Done", status_flavor=Task.FLAVOR_GOOD)

            volume_task = Task("(Re)creating volume {}".format(provides_volume), parent=task)
            # Recreate the volume with the new image ID
            try:
                host.client.remove_volume(provides_volume)
                volume_task.update(status="Removed {}. Recreating".format(provides_volume))
            except NotFound:
                volume_task.update(status="Volume {} not found. Creating")
            volume = host.client.create_volume(provides_volume, labels={'build_id': image_details['Id']})

            # Configure the container
            volume_mountpoints = ["/volume/"]
            volume_binds = {provides_volume: {"bind": "/volume/", "mode": "rw"}}
            container_pointer = host.client.create_container(
                container.image_name,
                detach=False,
                volumes=volume_mountpoints,
                host_config=host.client.create_host_config(
                    binds=volume_binds,
                ),
            )
            # Start it in the foreground so we wait till it exits (detach=False above)
            volume_task.update(status="Extracting")
            host.client.start(container_pointer)
            host.client.wait(container_pointer['Id'])
            host.client.remove_container(container_pointer['Id'])
            volume_task.update(status="Done", status_flavor=Task.FLAVOR_GOOD)
