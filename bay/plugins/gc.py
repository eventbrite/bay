import attr
import click

from .base import BasePlugin
from ..cli.argument_types import HostType
from ..cli.tasks import Task


@attr.s
class GcPlugin(BasePlugin):
    """
    Does garbage collection on demand.
    """

    provides = ["gc"]

    def load(self):
        self.add_command(gc)


@attr.s
class GarbageCollector:
    """
    Allows garbage collection on a host.
    """

    host = attr.ib()

    def gc_all(self, parent_task):
        task = Task("Running garbage collection", parent=parent_task)
        self.gc_containers(task)
        self.gc_networks(task)
        self.gc_images(task)
        task.finish(status="Done", status_flavor=Task.FLAVOR_GOOD)

    def gc_containers(self, parent_task):
        """
        Remove all stopped containers
        """
        task = Task("Removing all stopped containers", parent=parent_task)
        response = self.host.client.prune_containers()
        task.finish(status="Done, reclaimed {}MB".format(
            response['SpaceReclaimed'] / 1024 / 1024), status_flavor=Task.FLAVOR_GOOD)

    def gc_networks(self, parent_task):
        """
        Remove all networks not used by at least one container
        """
        task = Task("Removing all networks not used by at least one container", parent=parent_task)
        self.host.client.prune_networks()
        task.finish(status="Done", status_flavor=Task.FLAVOR_GOOD)

    def gc_images(self, parent_task):
        """
        Remove all dangling images
        """
        task = Task("Removing all dangling images", parent=parent_task)
        response = self.host.client.prune_images({"dangling": True})
        task.finish(status="Done, reclaimed {}MB".format(
            response['SpaceReclaimed'] / 1024 / 1024), status_flavor=Task.FLAVOR_GOOD)


@click.command()
@click.option('--host', '-h', type=HostType(), default='default')
@click.pass_obj
def gc(app, host):
    """
    Runs the garbage collection manually.
    """
    GarbageCollector(host).gc_all(app.root_task)
