import attr
from docker.errors import NotFound

from .base import BasePlugin
from ..cli.tasks import Task
from ..constants import PluginHook
from ..docker.build import Builder


@attr.s
class BuildVolumesPlugin(BasePlugin):
    """
    Plugin for showing information about containers
    """

    requires = ["build"]

    def load(self):
        self.add_hook(PluginHook.PRE_START, self.pre_start)
        self.add_hook(PluginHook.POST_BUILD, self.post_build)

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
        providers = {}
        for container in self.app.containers:
            provides_volume = container.extra_data.get("provides-volume", None)
            if provides_volume:
                providers[provides_volume] = container
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

    def post_build(self, host, container, task):
        """
        Intercepts builds of volume-providing containers and unpacks them.
        """
        provides_volume = container.extra_data.get("provides-volume", None)
        if provides_volume:
            volume_task = Task("Extracting into volume {}".format(provides_volume), parent=task)
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
