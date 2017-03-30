import attr
import click
from docker.errors import NotFound, APIError
from io import BytesIO
import tarfile

from .base import BasePlugin
from ..cli.argument_types import HostType
from ..cli.table import Table
from ..cli.tasks import Task
from ..docker.introspect import FormationIntrospector


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


@volume.command()
@click.option("--host", "-h", type=HostType(), default="default")
@click.argument("src")
@click.argument("container_name")
@click.argument("volume_name")
@click.pass_obj
def copy_to_docker(app, host, src, container_name, volume_name):
    """
    Copy a local file into docker volumes.
    """
    task = Task("Copying {} to {}:{}".format(src, container_name, volume_name))
    formation = FormationIntrospector(host, app.containers).introspect()

    instance = formation.get_container_instance(container_name)

    # Get the mount path of the volume
    path = instance.container.get_named_volume_path(volume_name)

    # Create a tar stream of the file
    tar_stream = BytesIO()
    with tarfile.open(fileobj=tar_stream, mode="w") as tar:
        tar.add(src)
    tar_stream.seek(0)

    try:
        host.client.put_archive(container=instance.name,
                                path=path,
                                data=tar_stream)
    except APIError as e:
        task.finish(status="Failed to copy", status_flavor=Task.FLAVOR_BAD)

    else:
        task.finish(status="Done", status_flavor=Task.FLAVOR_GOOD)
