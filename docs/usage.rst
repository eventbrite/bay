Usage
=====


To use Bay, you must first have the ``BAY_HOME`` environment variable pointing to
the top-level directory of your container library.


Selecting a profile
-------------------

The first thing to do is to select a profile. To see available profiles, run::

    bay list_profiles

Then, select one::

    bay profile tiny

This will load the profile in as your currently selected one (this information
is persisted in ``~/.bay/``); you can check what is loaded like this::

    $ bay profile
    tiny

Profiles can inherit from each other, in which case bay will show you the full
inheritance tree::

    $ bay profile
    personal-tinier
      ↳ tiny


Building
--------

Once you have your profile selected, you need to make Docker images for everything
mentioned in it. To do this, run::

    bay build profile

This will take some time, depending on how many containers there are to build,
and may opt to pull some prebuilt container images rather than build them locally
if containers have the flag set that says they have an image to pull from
(``image_tag``) and the project has a ``registry`` configured.


Running
-------

Then, you want to boot up the containers. To set things up in the default
arrangement that the profile has specified, just run::

    bay up

Alternatively, you can run a single container (and its dependencies)::

    bay run core-web

Or, you can shell into a fresh copy of a container::

    bay shell core-web

And finally, you can shell into an existing, running container::

    bay attach core-web

To see what containers are running, and how their ports are exposed, use::

    $ bay ps
    core-web           eventbrite.core-web.1         80->80
    redis              eventbrite.redis.1            6379->33397

You can stop containers with ``bay stop``, or restart them with ``bay restart``.

Note that running and stopping containers is done in parallel where possible,
according to the dependencies (links) specified between containers. For example,
if container ``www`` depends on both ``postgres`` and ``redis`` to run, but those
two do not depend on each other, Bay will start ``postgres`` and ``redis`` in
parallel, and once they are both up, then start ``www``.


Volume Mounting
---------------

If you are running under a system where the Docker daemon sees the filesystem
differently to your Bay instance (e.g. it's a remote daemon, or running in a
virtual machine like with Docker for Windows), you can set the
``BAY_VOLUME_HOME`` environment variable to the location that ``BAY_HOME``
would be on that remote system.
