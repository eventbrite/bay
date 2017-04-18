Project Layout
==============

Bay works on "projects", which is a collection of containers defined in a single
repository or directory. Each container is named and in its own folder, and the
whole project has a unique name that's used for settings called the "prefix".

An example project might look like this::

    example/
        bay.yaml  # Top-level project config, including prefix name
        www/
            Dockerfile     # Normal dockerfile for the container
            bay.yaml       # Describes links and other container information
            pre-build.sh   # Scripting to pull in code from other folders
            build/         # Temporary build directory (managed by Bay)
        db/
            Dockerfile     # Only the dockerfile is required.
        profiles/
            profile-1.yaml


Top-level config
----------------

The top-level ``bay.yaml`` file contains basic configuration for the project;
the only key it's required to contain is the ``prefix`` key, which will be used
to:

* Name the Docker network the containers are placed on
* Prefix container image names (e.g. a prefix of ``example`` results in the name ``example/www`` above)
* Name the subdirectory user config is stored in (e.g. ``~/.bay/example/``)

It can also contain information about where to pull container images from
under the ``registry`` key.


Container folder
----------------

Each folder with a ``Dockerfile`` in it is a container folder. Only ``Dockerfile``
is required, but two other important files may be provided: ``bay.yaml`` and
``pre-build.sh``.

Other files may be put in here (configuration, etc.) and will be included in the
build in the same way a normal ``docker build`` works.


Container bay.yaml
------------------

This file contains information about how to run the container; here's a shrunken
example from one of our JavaScript-based containers::

    volumes:
        "/var/babel_cache": "babel_cache"
    devmodes:
        britecharts:
            "/srv/mounted_node_modules/britecharts": "{git@github.com:eventbrite/britecharts.git}"
    links:
        required:
            - graphite
    waits:
        - http: 80
    boot:
        run:
            ssh-agent: required
    fast_kill: true

The exact meaning of each key is discussed elsewhere, but you can see it defines
details like what volumes to mount, the ``devmodes``, which are the possible
live-mount modes to work on code, ``waits``, which are how we tell the container
has finished booting, and what it depends on to boot, both as ``links``, where
the other container will be started and the hostname passed to us, and as ``boot``
options, which bring up containers that exist outside of the container network
that provide support functions (we call these *system containers*).


Container pre-build
-------------------

This is a shell or Python script that is run before the main ``docker build`` is
run that allows us to bring in files from outside the directory. A ``build``
directory is provided for this purpose by ``bay`` that you can copy files into
from other source trees or checkouts.


Profiles
--------

Profiles live in a special directory named ``profiles``. Each one is a YAML
file that specifies a set of containers to run and the options to apply to them
(e.g. adding or removing links, exposing ports).
