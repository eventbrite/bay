import attr
import click
from docker.errors import APIError
from io import BytesIO
import tarfile

from .base import BasePlugin
from ..cli.argument_types import ContainerType, HostType
from ..cli.colors import CYAN
from ..cli.table import Table
from ..cli.tasks import Task
from ..docker.introspect import FormationIntrospector
from ..exceptions import FailedCommandException


@attr.s
class ContainerPlugin(BasePlugin):
    """
    Plugin for showing information about containers
    """

    def load(self):
        self.add_command(container)
        self.add_command(copy_to_docker)


@click.command()
@click.argument("container", type=ContainerType(), required=False)
@click.pass_obj
def container(app, container=None):
    """
    Shows details on containers
    """
    if container is None:
        # Print containers
        table = Table([
            ("NAME", 30),
        ])
        table.print_header()
        for container in sorted(app.containers, key=lambda c: c.name):
            table.print_row([
                container.name,
            ])
    else:
        # Container name
        click.echo(CYAN("Name: ") + container.name)
        # Build parent
        click.echo(
            CYAN("Build ancestry: ") +
            ", ".join(other.name for other in app.containers.build_ancestry(container))
        )
        # Runtime dependencies
        dependencies = app.containers.dependencies(container)
        if dependencies:
            click.echo(CYAN("Depends on: ") + ", ".join(sorted(other.name for other in dependencies)))
        else:
            click.echo(CYAN("Depends on: ") + "(nothing)")
        # Dependents
        dependents = app.containers.dependents(container)
        if dependents:
            click.echo(CYAN("Depended on by: ") + ", ".join(sorted(other.name for other in dependents)))
        else:
            click.echo(CYAN("Depended on by: ") + "(nothing)")
        # Volumes
        click.echo(CYAN("Named volumes:"))
        for mount_point, source in container.named_volumes.items():
            click.echo("  {}: {}".format(mount_point, source))
        click.echo(CYAN("Bind-mounted volumes:"))
        for mount_point, source in container.bound_volumes.items():
            click.echo("  {}: {}".format(mount_point, source))
        # Devmodes
        click.echo(CYAN("Mounts (devmodes):"))
        for name, mounts in container.devmodes.items():
            click.echo("  {}:".format(name))
            for mount_point, source in mounts.items():
                click.echo("    {}: {}".format(mount_point, source))


@click.command()
@click.option("--host", "-h", type=HostType(), default="default")
@click.argument("src")
@click.argument("container", type=ContainerType())
@click.option("--path", "-p", default='/tmp')
@click.option("--volume", "-v")
@click.pass_obj
def copy_to_docker(app, host, src, container, path, volume):
    """
    Copy a local file into a docker container.

    Use -p to specify a path on the container's filesystem.
    Use -v to specify a volume name on the container.

    If both path and volume options are provided, the file will be copied to
    the volume. If neither path or volume are provided, the file will be copied
    to the container's `/tmp`.
    """
    formation = FormationIntrospector(host, app.containers).introspect()

    instance = formation.get_container_instance(container.name)

    if volume:
        # Get the mount path of the volume
        path = instance.container.get_named_volume_path(volume)
    else:
        NotImplementedError(
            "Copy to a custom path needs investigation. The file vanishes despite a 200."
        )

    task = Task("Copying {} to {}:{}".format(src, container.name, path))

    # Create a tar stream of the file
    tar_stream = BytesIO()
    with tarfile.open(fileobj=tar_stream, mode="w") as tar:
        tar.add(src)
    tar_stream.seek(0)

    try:
        host.client.put_archive(container=instance.name,
                                path=path,
                                data=tar_stream)
    except APIError:
        task.finish(status="Failed to copy", status_flavor=Task.FLAVOR_BAD)

    else:
        task.finish(status="Done", status_flavor=Task.FLAVOR_GOOD)
