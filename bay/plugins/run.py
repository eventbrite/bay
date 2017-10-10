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

    requires = ["tail"]

    def load(self):
        self.add_command(run)
        self.add_alias(run, "start")
        self.add_command(shell)
        self.add_command(stop)
        self.add_command(restart)
        self.add_alias(restart, "hup")
        self.add_alias(restart, "reload")


@click.command()
@click.argument("containers", type=ContainerType(), nargs=-1)
@click.option("--host", "-h", type=HostType(), default="default")
@click.option("--tail/--notail", "-t", default=False)
@click.pass_obj
def run(app, containers, host, tail):
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
            # If it's the container we're trying to add directly, have one error -
            # otherwise, say it's a link
            if e.image == container.image_name:
                click.echo(RED(
                    "This container ({name}) does not have a built image. Try `bay build {name}` first.".format(
                        name=container.name,
                    )
                ))
                sys.exit(1)
            elif hasattr(e, "container"):
                click.echo(RED("No image for linked container {name} - try `bay build {name}` first.".format(
                    name=e.container.name,
                )))
                sys.exit(1)
            else:
                click.echo(RED("No image for linked container %s!" % e.image))
                sys.exit(1)
    # Run that change
    task = Task("Starting containers", parent=app.root_task)
    run_formation(app, host, formation, task)
    # If they asked to tail, then run tail
    if tail:
        if len(containers) != 1:
            click.echo(RED("You cannot tail more than one container!"))
            sys.exit(1)
        app.invoke("tail", host=host, container=containers[0], follow=True)


@click.command()
@click.argument("container", type=ContainerType())
@click.option("--host", "-h", type=HostType(), default="default")
@click.argument("command", nargs=-1, default=None)
@click.pass_obj
def shell(app, container, host, command):
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
    if command:
        instance.command = ['/bin/bash -lc "{}"'.format(' '.join(command))]
    else:
        instance.command = ["/bin/bash -l"]
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
        if instance.container in containers or (not containers and not instance.container.system):
            # Make sure that it was not removed already as a dependent
            if instance.formation:
                formation.remove_instance(instance)
    # Run the change
    task = Task("Stopping containers", parent=app.root_task)
    run_formation(app, host, formation, task)


@click.command()
@click.argument("containers", type=ContainerType(), nargs=-1)
@click.option("--host", "-h", type=HostType(), default="default")
@click.pass_obj
def restart(app, containers, host):
    """
    Stops and then starts containers.
    """
    app.invoke("stop", containers=containers, host=host)
    if containers:
        app.invoke("run", containers=containers, host=host)
    else:
        app.invoke("up", host=host)


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
