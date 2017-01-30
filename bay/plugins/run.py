import attr
import click
import sys

from .base import BasePlugin
from ..cli.argument_types import ContainerType, HostType
from ..cli.colors import RED
from ..cli.tasks import Task
from ..docker.introspect import FormationIntrospector
from ..docker.runner import FormationRunner
from ..exceptions import DockerRuntimeError, ImageNotFoundException


@attr.s
class RunPlugin(BasePlugin):
    """
    Plugin for running containers.
    """

    def load(self):
        self.add_command(run)
        self.add_command(shell)
        self.add_command(stop)


@click.command()
@click.argument("containers", type=ContainerType(), nargs=-1)
@click.option("--host", "-h", type=HostType(), default="default")
@click.pass_obj
def run(app, containers, host):
    """
    Runs containers by name, including any dependencies needed
    """
    # Get the current formation
    formation = FormationIntrospector(host, app.containers).introspect()
    # Make a Formation that represents what we want to do by taking the existing
    # state and adding in the containers we want
    for container in containers:
        try:
            formation.add_container(container, host)
        except ImageNotFoundException as e:
            click.echo(RED(str(e)))
            sys.exit(1)
    # Run that change
    task = Task("Starting containers", parent=app.root_task)
    run_formation(app, host, formation, task)


@click.command()
@click.argument("container", type=ContainerType())
@click.option("--host", "-h", type=HostType(), default="default")
@click.pass_obj
def shell(app, container, host):
    """
    Runs a single container with foreground enabled and overridden to use bash.
    """
    # Get the current formation
    formation = FormationIntrospector(host, app.containers).introspect()
    # Make a Formation with that container launched with bash in foreground
    try:
        instance = formation.add_container(container, host)
    except ImageNotFoundException as e:
        click.echo(RED(str(e)))
        sys.exit(1)
    instance.foreground = True
    instance.command = ["/bin/bash"]
    # Run that change
    task = Task("Shelling into {}".format(container.name), parent=app.root_task)
    run_formation(app, host, formation, task)


@click.command()
@click.argument("containers", type=ContainerType(), nargs=-1)
@click.option("--host", "-h", type=HostType(), default="default")
@click.pass_obj
def stop(app, containers, host):
    """
    Stops containers and ones that depend on them
    """
    formation = FormationIntrospector(host, app.containers).introspect()
    # Look through the formation and remove the containers matching the name
    for instance in list(formation):
        # If there are no names, then we remove everything
        if instance.container in containers or not containers:
            formation.remove_instance(instance)
    # Run the change
    task = Task("Stopping containers", parent=app.root_task)
    run_formation(app, host, formation, task)


def run_formation(app, host, formation, task):
    """
    Common function to run a formation change.
    """
    try:
        FormationRunner(app, host, formation, task).run()
    # General docker/runner error
    except DockerRuntimeError as e:
        click.echo(RED(str(e)))
        if e.code == "BOOT_FAIL":
            click.echo(RED("You can see its output with `bay tail {}`.".format(e.instance.container.name)))
    # An image was not found
    except ImageNotFoundException as e:
        click.echo(RED("Missing image for {} - cannot continue boot.".format(e.container.name)))
    else:
        task.finish(status="Done", status_flavor=Task.FLAVOR_GOOD)
