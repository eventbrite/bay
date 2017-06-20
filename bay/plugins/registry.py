import attr
import click

from .base import BasePlugin
from ..cli.argument_types import HostType, ContainerType
from ..exceptions import RegistryRequiresLogin


@attr.s
class RegistryPlugin(BasePlugin):
    """
    Plugin for fetching and uploading images
    """

    def load(self):
        self.add_command(registry)
        self.add_command(push)


@click.group()
def registry():
    """
    Allows operations on registries.
    """
    pass


@registry.command()
@click.option("--host", "-h", type=HostType(), default="default")
@click.pass_obj
def status(app, host):
    """
    Gives registry status
    """
    registry_instance = host.images.get_registry(app)
    if registry_instance is None:
        click.echo("No registry is configured on this project.")
        return
    try:
        url = registry_instance.url(host)
    except RegistryRequiresLogin:
        click.echo("Registry requires login. Run `bay registry login` to do so.")
    else:
        click.echo("Registry configured, docker URL: %s" % url)


@registry.command()
@click.option("--host", "-h", type=HostType(), default="default")
@click.pass_obj
def login(app, host):
    """
    Logs into a registry
    """
    registry_instance = host.images.get_registry(app)
    registry_instance.login(host, app.root_task)


@click.command()
@click.option("--host", "-h", type=HostType(), default="default")
@click.argument("container", type=ContainerType())
@click.argument("tag")
@click.pass_obj
def push(app, host, container, tag):
    """
    Pushes an image up to a registry
    """
    host.images.push_image_version(app, container.image_name, tag, app.root_task)
