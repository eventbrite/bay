import sys
import click

from .base import BasePlugin
from ..cli.argument_types import HostType, ContainerType
from ..cli.colors import RED


class TailPlugin(BasePlugin):
    """
    Plugin to let you view container output.
    """

    provides = ["tail", "logs"]

    def load(self):
        self.add_command(tail)
        self.add_command(logs)


@click.command()
@click.option("--host", "-h", type=HostType(), default="default")
@click.option('--follow/--no-follow', '-f', default=False, help="Follow log output")
@click.option("--all/--no-all", default=False, help="Show the whole log")
@click.argument("container", type=ContainerType())
@click.argument("lines", default="10")
@click.pass_obj
def tail(app, host, container, lines, all=False, follow=False):
    """
    Tail the logs of a container. Optional second argument specifies a number of lines to print.
    """
    if all:
        tail = "all"
    else:
        tail = lines
    _logs(app, host, container, tail, follow)


@click.command()
@click.option("--host", "-h", type=HostType(), default="default")
@click.option('--follow/--no-follow', '-f', default=False, help="Follow log output")
@click.argument("container", type=ContainerType())
@click.option("--tail", default="all", help="Number of lines to show from the end of the logs (default \"all\")")
@click.pass_obj
def logs(app, host, container, tail, follow=False):
    """
    Fetch the logs of a container
    """
    _logs(app, host, container, tail, follow)


def _logs(app, host, container, tail, follow=False):
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
    if tail != "all":
        try:
            tail = int(tail)
        except Exception as ex:
            click.echo(RED("Invalid number of lines: {}".format(tail)))
            sys.exit(1)
    if follow:
        for line in host.client.logs(container_name, tail=tail, stream=True):
            click.echo(line, nl=False)
    else:
        click.echo(host.client.logs(container_name, tail=tail))
