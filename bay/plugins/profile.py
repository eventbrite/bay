import os

import attr
import click

from .base import BasePlugin
from .run import run_formation
from ..cli.argument_types import HostType
from ..cli.colors import CYAN, RED
from ..cli.table import Table
from ..cli.tasks import Task
from ..containers.profile import Profile, NullProfile
from ..docker.introspect import FormationIntrospector


@attr.s
class ProfilesPlugin(BasePlugin):
    """
    Plugin for managing and switching profiles.
    """

    provides = ["up"]

    def load(self):
        self.add_command(profile)
        self.add_command(up)
        self.add_command(list_profiles)


@click.command()
@click.argument('name', required=False)
@click.option("--host", "-h", type=HostType(), default="default")
@click.pass_obj
def profile(app, name, host):
    """
    Switch to a different profile, or list the active profile's name.
    """
    if name is None:
        # if no profile is provided, print current profile stack and exit
        if len(app.profiles) > 1:
            for i, parent_profile in enumerate(app.profiles[1:]):
                if i:
                    click.echo("%s↳ %s" % ("  " * i, parent_profile.name))
                else:
                    click.echo(parent_profile.name)
        else:
            click.echo(RED("No profile selected."))
        return

    # Find the profile they named on the command line
    parent_profile_path = os.path.join(
        app.config["bay"]["home"],
        "profiles",
        "{}.yaml".format(name)
    )
    if not os.path.isfile(parent_profile_path):
        click.echo(RED("Invalid profile name!"))
        return
    parent_profile = Profile(parent_profile_path)

    click.echo("Switching to profile %s" % CYAN(name))

    # Set it in the user profile, making a new user profile if needed
    if isinstance(app.user_profile, NullProfile):
        app.user_profile = Profile(app.user_profile_path, load_immediately=False)
    app.user_profile.parent_profile = name
    app.user_profile.save()


@click.command()
@click.option("--host", "-h", type=HostType(), default="default")
@click.pass_obj
def up(app, host):
    """
    Start up a profile by booting the default containers.
    Leaves any other containers that are running (shell, ssh-agent, etc.) alone.
    """
    # Do removal loop first so we don't step on adding containers later
    formation = FormationIntrospector(host, app.containers).introspect()
    for instance in list(formation):
        # We remove all non-system containers, so that means ssh-agent and similar
        # containers will survive the process.
        if not instance.container.system and instance.formation:
            formation.remove_instance(instance)

    # Now add in containers
    for container in app.containers:
        if app.containers.options(container).get('default_boot'):
            formation.add_container(container, host)

    task = Task("Restarting containers", parent=app.root_task)
    run_formation(app, host, formation, task)


@click.command()
@click.option('--verbose/--quiet', '-v/-q', default=False)
@click.pass_obj
def list_profiles(app, verbose):
    """
    List all available profiles.
    """
    # the path where all profiles can be found
    profiles_home_dir = os.path.join(
        app.config['bay']['home'],
        "profiles",
    )
    corrupted_profiles = []
    if verbose:
        table = Table([
            ("PROFILE", 30),
            ("DESCRIPTION", 50),
        ])
        table.print_header()

    for filename in os.listdir(profiles_home_dir):
        if filename.endswith('.yaml'):
            profile_name = filename.split('.')[0]
            try:
                profile = Profile(os.path.join(profiles_home_dir, filename))
            except:
                # the profile is corrupted, the specifics of the error do not
                # matter in this case, where we are only trying to list
                # available profiles.
                corrupted_profiles.append(profile_name)
            else:
                if verbose:
                    table.print_row([
                        profile_name,
                        profile.description
                    ])
                else:
                    click.echo(profile_name)

    if corrupted_profiles:
        click.echo(
            "These profiles are defined but corrupted and cannot be loaded:"
        )
        click.echo(corrupted_profiles)
