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
        self.add_catalog_type("registry")


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
    logfile_name = app.config.get_path('bay', 'build_log_path', app)
    containers_to_pull = []
    containers_to_build = []
    pulled_containers = set()
    failed_pulls = set()

    task = Task("Building", parent=app.root_task)
    start_time = datetime.datetime.now().replace(microsecond=0)

    # Go through the containers, expanding "ContainerType.Profile" into a list
    # of default boot containers in the profile.
    for container in containers:
        if container is ContainerType.Profile:
            for con in app.containers:
                if app.containers.options(con).get('in_profile'):
                    containers_to_pull.append(con)
        else:
            containers_to_build.append(container)

    # Expand containers_to_pull (At this point just the default boot containers
    # from profile) to include runtime dependencies.
    containers_to_pull = dependency_sort(containers_to_pull, app.containers.dependencies)

    # Try pulling each container to pull, and add it to containers_to_build if
    # it fails. If it works, remember we pulled it, so we don't have to pull it
    # again later.
    for container in containers_to_pull:
        try:
            host.images.pull_image_version(
                app,
                container.image_name,
                container.image_tag,
                parent_task=task,
                fail_silently=False,
            )
        except ImagePullFailure:
            failed_pulls.add(container)
            containers_to_build.append(container)
        else:
            pulled_containers.add(container)

    ancestors_to_build = []
    # For each container to build, find its ancestry, trying to pull each
    # ancestor and stopping short if it works.
    for container in containers_to_build:
        # Always add `container` to final build list, even if recursive is
        # False.
        ancestors_to_build.append(container)
        if recursive:
            # We need to look at the ancestry starting from the oldest, up to
            # and not including the `container`
            ancestry = dependency_sort(containers_to_build,
                                       lambda x: [app.containers.build_parent(x)])[:-1]
            for ancestor in reversed(ancestry):
                try:
                    # If we've already attempted to pull it and failed, short
                    # circuit to failure block.
                    if ancestor in failed_pulls:
                        raise ImagePullFailure("We've already attempted to pull this image, and failed.")
                    # Check if we've pulled it already
                    if ancestor not in pulled_containers:
                        host.images.pull_image_version(
                            app,
                            ancestor.image_name,
                            ancestor.image_tag,
                            parent_task=task,
                            fail_silently=False,
                        )
                except ImagePullFailure:
                    failed_pulls.add(ancestor)
                    ancestors_to_build.insert(0, ancestor)
                else:
                    # We've pulled the current ancestor successfully, so skip
                    # all the older ancestors.
                    pulled_containers.add(ancestor)
                    break

    # Sort ancestors so we build the most depended on first.
    sorted_ancestors_to_build = dependency_sort(ancestors_to_build, lambda x: [app.containers.build_parent(x)])

    # dependency_sort would insert back the pulled containers into the ancestry
    # chain, so we only include ones that were in the list before
    ancestors_to_build = [
        container
        for container in sorted_ancestors_to_build
        if container in ancestors_to_build
    ]

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

    task.finish(status="Done", status_flavor=Task.FLAVOR_GOOD)

    # Show total build time metric after everything is complete
    end_time = datetime.datetime.now().replace(microsecond=0)
    time_delta_str = str(end_time - start_time)
    if time_delta_str.startswith('0:'):
        # no point in showing hours, unless it runs for more than one hour
        time_delta_str = time_delta_str[2:]
    click.echo("Total build time [{}]".format(GREEN(time_delta_str)))
