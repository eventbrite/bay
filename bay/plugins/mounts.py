from collections import defaultdict

import attr
import click

from .base import BasePlugin
from ..cli.argument_types import ContainerType, HostType, MountType
from ..cli.colors import CYAN, GREEN, PURPLE
from ..cli.tasks import Task


@attr.s
class DevModesPlugin(BasePlugin):
    """
    Plugin for managing dev checkouts in a container.
    """

    requires = ["up"]

    def load(self):
        self.add_command(mounts)
        self.add_command(mount)
        self.add_command(unmount)
        self.add_alias(unmount, "umount")


@click.command()
@click.option('--profile-only', '-p', default=False, is_flag=True)
@click.option('--mounted', '-m', default=False, is_flag=True)
@click.option('--verbose/--quiet', '-v/-q', default=True)
@click.pass_obj
def mounts(app, profile_only, mounted, verbose):
    """
    List all current dev mounts.
    """
    def to_message(mounted, unmounted):
        return '\n'.join(filter(None, [
            'Mounted: {}'.format(GREEN(', '.join(sorted(mounted)))) if mounted else None,
            'Unmounted: {}'.format(PURPLE(', '.join(sorted(unmounted)))) if unmounted else None,
        ]))

    dev_mounts = defaultdict(dict)

    for container in app.containers:
        mounted_containers = set()
        unmounted_containers = set(container.devmodes.keys())

        runtime_options = app.containers.options(container)
        if runtime_options:
            mounted_containers = app.containers.options(container).get('devmodes')
            unmounted_containers = unmounted_containers.difference(mounted_containers)

        elif profile_only:
            # only containers in profile have runtime_options set, so if profile_only
            # then skip ones with no options altogether regrdless is the have devmodes
            continue

        if mounted:
            unmounted_containers = set()

        if (
            not mounted_containers and
            not unmounted_containers
        ):
            continue

        dev_mounts[container.name] = dict(
            mounted=mounted_containers,
            unmounted=unmounted_containers,
        )

    messages = []

    if verbose:
        for name, devmodes in dev_mounts.items():
            messages.append('{name}: \n{containers}'.format(
                name=CYAN(name),
                containers=to_message(devmodes['mounted'], devmodes['unmounted']),
            ))
    else:
        messages = sorted(set.union(*[
            devmodes['mounted'] | devmodes['unmounted']
            for devmodes
            in dev_mounts.values()
        ]))

    click.echo('\n'.join(messages))


@click.command()
@click.argument('mount', type=MountType())
@click.argument('container', default='all', type=ContainerType(all=True))
@click.option("--host", "-h", type=HostType(), default="default")
@click.option('--up/--no-up', '-u', default=True)
@click.pass_obj
def mount(app, mount, container, host, up):
    """
    Mount a dev checkout in a given container.
    """
    # Check the profile is loaded
    if app.user_profile.file_path is None:
        click.echo("No profile loaded. Please select a profile using `bay profile <profile_name>`")
        return
    # Add the devmode
    mutate_devmounts(app, container, add=[mount])

    if up:
        # Run tug up to apply any changes
        app.invoke("up")


@click.command()
@click.argument('mount', type=MountType())
@click.argument('container', default='all', type=ContainerType(all=True))
@click.option("--host", "-h", type=HostType(), default="default")
@click.option('--up/--no-up', '-u', default=True)
@click.pass_obj
def unmount(app, mount, container, host, up):
    """
    Unmount a dev checkoutin a given container.
    """
    # Check the profile is loaded
    if app.user_profile.file_path is None:
        click.echo("No profile loaded. Please select a profile using `bay profile <profile_name>`")
        return
    # Remove the devmode
    mutate_devmounts(app, container, remove=[mount])

    if up:
        # Run tug up to apply any changes
        app.invoke("up")


def mutate_devmounts(app, containers, add=None, remove=None):
    """
    Applies devmount changes to a set of containers in a profile.
    """
    # Give add/remove good defaults
    add = add or []
    remove = remove or []

    # Convert any single instance of a container into a singleton list
    if not isinstance(containers, list):
        containers = [containers]
    else:
        containers = containers

    # For each provided container, try mounting
    profile = app.user_profile
    changed_containers = set()
    # Mounts to add
    for mount in add:
        task = Task("Mounting {}".format(mount), parent=app.root_task)
        for con in sorted(containers, key=lambda c: c.name):
            if mount in con.devmodes and mount not in profile.containers.get(con.name, {}).get('devmodes', set()):
                subtask = Task(con.name, parent=task)
                if not profile.containers.get(con.name):
                    profile.containers[con.name] = {}
                if not profile.containers[con.name].get('devmodes'):
                    profile.containers[con.name]['devmodes'] = set()
                profile.containers[con.name]['devmodes'].add(mount)
                changed_containers.add(con)
                subtask.finish(status="Done", status_flavor=Task.FLAVOR_GOOD)
    # Mounts to remove
    for mount in remove:
        task = Task("Unmounting {}".format(mount), parent=app.root_task)
        for con in sorted(containers, key=lambda c: c.name):
            if mount in con.devmodes and mount in profile.containers.get(con.name, {}).get('devmodes', set()):
                subtask = Task(con.name, parent=task)
                profile.containers[con.name]['devmodes'].remove(mount)
                changed_containers.add(con)
                subtask.finish(status="Done", status_flavor=Task.FLAVOR_GOOD)

    if changed_containers:
        profile.save()
        profile.apply(app.containers)
