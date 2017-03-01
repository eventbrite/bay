import attr
import click
from docker.errors import NotFound

from .base import BasePlugin
from ..cli.argument_types import HostType
from ..cli.table import Table
from ..cli.tasks import Task


@attr.s
class VolumePlugin(BasePlugin):
    """
    Plugin for showing information about volumes and deleting them.
    """

    provides = ["volume"]
    requires = ["gc"]

    def load(self):
        self.add_command(volume)


@click.group()
def volume():
    """
    Allows operations on volumes.
    """
    pass


@volume.command()
@click.option("--host", "-h", type=HostType(), default="default")
@click.pass_obj
def list(app, host):
    """
    Lists all available volumes
    """
    # Print containers
    table = Table([
        ("NAME", 40),
        ("CONTAINERS", 50)
    ])
    table.print_header()
    # Collect volume information from containers
    users = {}
    for container in app.containers:
        for _, source in container.named_volumes.items():
            users.setdefault(source, set()).add(container.name)
    # Print volumes
    for details in sorted((host.client.volumes()['Volumes'] or []), key=lambda x: x['Name']):
        table.print_row([
            details['Name'],
            ", ".join(users.get(details['Name'], [])),
        ])


@volume.command()
@click.option("--host", "-h", type=HostType(), default="default")
@click.argument("name")
@click.pass_obj
def destroy(app, host, name):
    """
    Destroys a single volume
    """
    task = Task("Destroying volume {}".format(name))
    # Run GC first to clean up stopped containers
    from .gc import GarbageCollector
    GarbageCollector(host).gc_all(task)
    # Remove the volume
    try:
        host.client.remove_volume(name)
    except NotFound:
        task.add_extra_info("There is no volume called {}".format(name))
        task.finish(status="Not found", status_flavor=Task.FLAVOR_BAD)
    else:
        task.finish(status="Done", status_flavor=Task.FLAVOR_GOOD)
