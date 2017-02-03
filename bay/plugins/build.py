import attr
import click
import datetime
import sys

from .base import BasePlugin
from ..cli.colors import CYAN, GREEN, RED, remove_ansi
from ..cli.argument_types import ContainerType, HostType
from ..cli.tasks import Task
from ..docker.build import Builder
from ..exceptions import BuildFailureError, ImagePullFailure
from ..utils.sorting import dependency_sort


@attr.s
class BuildPlugin(BasePlugin):
    """
    Plugin for showing information about containers
    """

    provides = ["build"]

    def load(self):
        self.add_command(build)


@click.command()
@click.argument('containers', type=ContainerType(profile=True), nargs=-1)
@click.option('--host', '-h', type=HostType(), default='default')
@click.option('--cache/--no-cache', default=True)
@click.option('--recursive/--one', '-r/-1', default=True)
@click.option('--verbose/--quiet', '-v/-q', default=True)
# TODO: Add a proper requires_docker check
# TODO: Add build profile
@click.pass_obj
def build(app, containers, host, cache, recursive, verbose):
    """
    Build container images, along with its build dependencies.
    """
    logfile_name = app.config.get_logging_path('bay', 'build_log_path', app.containers.prefix)
    containers_to_pull = []
    containers_to_build = []
    pulled_containers = set()

    task = Task("Building", parent=app.root_task)
    start_time = datetime.datetime.now().replace(microsecond=0)

    # Try to fetch the images for the original set of containers from the
    # docker registry. If successful, don't build that container
    for container in containers:
        if container is ContainerType.Profile:
            for con in app.containers:
                if app.containers.options(con).get('default_boot'):
                    containers_to_pull.append(con)
        else:
            containers_to_build.append(container)

    containers_to_pull = dependency_sort(containers_to_pull, app.containers.dependencies)

    for container in containers_to_pull:
        try:
            host.images.pull_image_version(
                container.image_name,
                "latest",
                fail_silently=False,
            )
        except ImagePullFailure:
            containers_to_build.append(container)
        else:
            pulled_containers.add(container)

    ancestors_to_build = [container]
    # Run the build for each container
    for container in containers_to_build:
        ancestors_to_build.append(container)
        if recursive:
            ancestry = dependency_sort(containers_to_build,
                                       lambda x: [app.containers.build_parent(x)])[:-1]
            for ancestor in reversed(ancestry):
                try:
                    if ancestor not in pulled_containers:
                        host.images.pull_image_version(
                            container.image_name,
                            "latest",
                            fail_silently=False,
                        )
                except ImagePullFailure:
                    ancestors_to_build.insert(0, ancestor)
                else:
                    pulled_containers.add(ancestor)
                    break

    ancestors_to_build = dependency_sort(ancestors_to_build,
                                         lambda x: [app.containers.build_parent(x)])
    ancestors_to_build = [container
                          for container in ancestors_to_build
                          if container not in pulled_containers]

    task.add_extra_info(
        "Order: {order}".format(
            order=CYAN(", ".join([container.name for container in ancestors_to_build])),
        ),
    )

    for container in ancestors_to_build:
        image_builder = Builder(
            host,
            container,
            app,
            parent_task=task,
            logfile_name=logfile_name,
            docker_cache=cache,
            verbose=verbose,
        )
        try:
            image_builder.build()
        except BuildFailureError:
            click.echo(RED("Build failed! Last 15 lines of log:"))
            # TODO: More efficient tailing
            lines = []
            with open(logfile_name, "r") as fh:
                for line in fh:
                    lines = lines[-14:] + [line]
            for line in lines:
                click.echo("  " + remove_ansi(line).rstrip())
            click.echo("See full build log at {log}".format(log=click.format_filename(logfile_name)), err=True)
            sys.exit(1)
    click.echo()

    # Show total build time metric after everything is complete
    end_time = datetime.datetime.now().replace(microsecond=0)
    time_delta_str = str(end_time - start_time)
    if time_delta_str.startswith('0:'):
        # no point in showing hours, unless it runs for more than one hour
        time_delta_str = time_delta_str[2:]
    click.echo("Total build time [{}]".format(GREEN(time_delta_str)))
