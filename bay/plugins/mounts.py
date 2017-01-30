from collections import defaultdict
import os

import attr
import click

from .base import BasePlugin
from .run import run_formation
from ..cli.argument_types import ContainerType, HostType, MountType
from ..cli.colors import CYAN, GREEN, PURPLE
from ..cli.tasks import Task
from ..containers.profile import NullProfile, Profile
from ..docker.introspect import FormationIntrospector


@attr.s
class DevModesPlugin(BasePlugin):
    """
    Plugin for managing dev checkouts in a container.
    """

    def load(self):
        self.add_command(mounts)
        self.add_command(mount)
        self.add_command(unmount)


@click.command()
@click.pass_obj
def mounts(app):
    """
    List all current dev mounts.
    """
    dev_mounts = defaultdict(dict)
    for container in app.containers:
        unmounted_devmodes = set(container.devmodes.keys())
        runtime_options = app.containers.options(container)
        if runtime_options:
            devmodes = app.containers.options(container).get('devmodes')
            dev_mounts[container.name]['mounted'] = sorted(devmodes)
            dev_mounts[container.name]['unmounted'] = unmounted_devmodes.difference(devmodes)

    for name, devmodes in dev_mounts.items():
        click.echo('{}: \nMounted: {}\nUnmounted: {}'.format(
            CYAN(name),
            GREEN(', '.join(devmodes['mounted'])),
            PURPLE(', '.join(devmodes['unmounted'])),
        ))


@click.command()
@click.argument('mount', type=MountType())
@click.argument('container', default='all', type=ContainerType(all=True))
@click.option("--host", "-h", type=HostType(), default="default")
@click.pass_obj
def mount(app, mount, container, host):
    """
    Mount a dev checkout in a given container.
    """
    user_profile_path = os.path.join(
        app.config["bay"]["user_profile_home"],
        app.containers.prefix,
        "user_profile.yaml"
    )

    if os.path.isfile(user_profile_path):
        profile = Profile(user_profile_path)
    else:
        profile = NullProfile()
        click.echo("No profile loaded. Please select a profile using `bay profile <profile_name>`")
        return

    if not isinstance(container, list):
        containers = [container]
    else:
        containers = container

    update_required = False

    for con in containers:
        if mount in con.devmodes and mount not in profile.containers.get(con.name, {}).get('devmodes', set()):
            click.echo("Mounting {} to container {}".format(PURPLE(mount), CYAN(con.name)))
            if not profile.containers.get(con.name):
                profile.containers[con.name] = {'devmodes': set([mount])}
            elif not profile.containers[con.name].get('devmodes'):
                profile.containers[con.name]['devmodes'] = set([mount])
            else:
                profile.containers[con.name]['devmodes'].add(mount)
            update_required = True

    if update_required:
        profile.save()
        profile.apply(app.containers)
        # restart all the running containers
        formation = FormationIntrospector(host, app.containers).introspect()
        for con in containers:
            formation.add_container(con, host)

        task = Task("Restarting containers", parent=app.root_task)
        run_formation(app, host, formation, task)


@click.command()
@click.argument('mount', type=MountType())
@click.argument('container', default='all', type=ContainerType(all=True))
@click.option("--host", "-h", type=HostType(), default="default")
@click.pass_obj
def unmount(app, mount, container, host):
    """
    Unmount a dev checkoutin a given container.
    """
    user_profile_path = os.path.join(
        app.config["bay"]["user_profile_home"],
        app.containers.prefix,
        "user_profile.yaml"
    )

    if os.path.isfile(user_profile_path):
        profile = Profile(user_profile_path)
    else:
        profile = NullProfile()
        click.echo("No profile loaded. Please select a profile using `bay profile <profile_name>`")
        return

    if not isinstance(container, list):
        containers = [container]
    else:
        containers = container

    update_required = False
    for con in containers:
        if mount in con.devmodes and mount in profile.containers.get(con.name, {}).get('devmodes', set()):
            click.echo("Unmounting {} from container {}".format(PURPLE(mount), CYAN(con.name)))
            profile.containers[con.name]['devmodes'].remove(mount)
            update_required = True

    if update_required:
        profile.save()
        profile.apply(app.containers)
        # restart all the running containers
        formation = FormationIntrospector(host, app.containers).introspect()
        for con in containers:
            formation.add_container(con, host)

        task = Task("Restarting containers", parent=app.root_task)
        run_formation(app, host, formation, task)
