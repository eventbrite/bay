import sys
import click

from .base import BasePlugin
from ..cli.argument_types import HostType, ContainerType
from ..cli.colors import RED


class TailPlugin(BasePlugin):
    """
    Plugin to let you view container output.
    """

    provides = ["tail"]

    def load(self):
        self.add_command(tail)


@click.command()
@click.option("--host", "-h", type=HostType(), default="default")
@click.option('--follow/--no-follow', '-f', default=False)
@click.argument("container", type=ContainerType())
@click.pass_obj
def tail(app, host, container, follow=False):
    """
    Shows logs from a container
    """
    # We don't use formation here as it doesn't include stopped containers;
    # instead, we manually go through the list.
    for docker_container in host.client.containers(all=True):
        if docker_container['Labels'].get('com.eventbrite.bay.container', None) == container.name:
            # We found it!
            container_name = docker_container['Names'][0]
            break
    else:
        click.echo(RED("Cannot find instance of {} to print logs for.".format(container.name)))
        sys.exit(1)
    # Either stream or just print directly
    if follow:
        for line in host.client.logs(container_name, stream=True):
            click.echo(line, nl=False)
    else:
        click.echo(host.client.logs(container_name))
