import attr
import click

from .base import BasePlugin
from ..cli.argument_types import HostType
from ..cli.table import Table
from ..docker.introspect import FormationIntrospector


@attr.s
class PsPlugin(BasePlugin):
    """
    Plugin to see what's running right now.
    """

    def load(self):
        self.add_command(ps)


@click.command()
@click.option("--host", "-h", type=HostType(), default="default")
@click.pass_obj
def ps(app, host):
    """
    Shows details about all containers currently running
    """
    # Run the introspector to get the details
    formation = FormationIntrospector(host, app.containers).introspect()
    # Print formation details
    table = Table([("NAME", 30), ("DOCKER NAME", 30), ("IMAGE", 30)])
    table.print_header()
    for instance in sorted(formation, key=lambda i: i.name):
        table.print_row([
            instance.container.name,
            instance.name,
            instance.image_id,
        ])
