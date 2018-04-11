import attr
import click
import subprocess

from .base import BasePlugin
from ..cli.argument_types import HostType
from ..cli.tasks import Task
from ..cli.colors import YELLOW


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

        click.echo(YELLOW('INFO: Run bay up first if you don\'t want to remove all your containers.'))

        subprocess.run(["docker", "system", "prune"])

        task.finish(status="Done", status_flavor=Task.FLAVOR_GOOD)


@click.command()
@click.option('--host', '-h', type=HostType(), default='default')
@click.pass_obj
def gc(app, host):
    """
    Runs the garbage collection manually.
    """
    GarbageCollector(host).gc_all(app.root_task)
