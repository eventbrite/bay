Commands
========

Bay's default set of plugins provides a range of commands for building, running
and cleaning up images.


attach
------

``attach`` allows you to get a shell into a running container. If the container
isn't running, this will exit with an error.

You can optionally pass in a command to run in that interactive session rather
than running the default ``bash``.


build
-----

Builds containers, and all containers in their build ancestry (parents) by name.
Invoke it either with names of individual containers::

    bay build www postgres

Or, with the special name ``profile``, which will build all containers needed
to run your current profile::

    bay build profile

Other options you can pass:

* ``--no-cache``, which instructs Docker to not use the build cache and start
  from scratch.
* ``-1 / --one``, which tells Bay to just build the image you requested rather
  than checking if it needs to build all of the parents in the chain.


container
---------

Called without arguments, presents a list of containers available. Called with
arguments, gives detailed information about that container::

    $ bay container varnish
    Name: varnish
    Build ancestry: bay-base, base
    Depends on: (nothing)
    Depended on by: (nothing)
    Named volumes:
    Bind-mounted volumes:
      /srv/core: /home/user/work/core
    Mounts (devmodes):


doctor
------

Runs any configured diagnosis plugins and gives the user output to help them
self-service any problems. Bay does not ship with any diagnosis plugins by
default, but example output might be::

    Time checks: OK
      Testing docker clock sync: OK
      Testing local clock sync: OK
    Connectivity checks: OK
      Eventbrite Github access: OK
      Testing Github connectivity: OK


gc
--

Runs garbage collection on docker images and containers to clean up ones which
are no longer needed. Invoke it manually if you wish to
try and free up some disk space and speed up Docker slightly.


help
----

Shows help about bay or, if you type ``help command``, the command in question.


hosts
-----

Shows available hosts and how they are configured. All commands that operate
on Docker take an optional ``-h``/``--host`` argument that takes one of the
host aliases given here.


image
-----

Allows operations on images.


list_profiles
-------------

List all available profiles.


logs
----

Fetch the logs of a container.

mount
-----

Mount a dev checkout in a given container.


mounts
------

List all current dev mounts.


profile
-------

Switch to a different profile, or list the active profile's name.


ps
--

Shows details about all containers currently running.


push
----

Pushes an image up to a registry.


registry
--------

Allows operations on registries.


restart
-------

Stops and then starts containers.


run
---

Runs containers by name, including any dependencies needed.


shell
--------

Runs a single container with foreground enabled and overridden to use bash.


stop
----

Stops containers and ones that depend on them.


tail
----

Tail the logs of a container.


unmount
-------

Unmount a dev checkoutin a given container.

up
---

Start up a profile by booting the default containers. Leaves any other containers that are running (shell, ssh-agent, etc.) alone.


volume
------

Allows operations on volumes.
