Introduction to Bay
===================

Bay is a Docker container orchestrator, but with a difference; unlike most, it
is developed specifically for the task of developing against large systems,
rather than running contaniers in production.

Most Docker-based solutions are designed to be inflexible and keep to certain
promises; Bay, instead, is designed to allow developers to heavily mutate the
set of containers they are working with on an hourly basis, while trying to keep
a working site going as a result.

It was born from the engineering department at Eventbrite, where we have a site
that is complicated enough that it's very hard to run it all on a single laptop
(due to RAM constraints), but where different teams all need to work on a
different part of that same site at the same time, and where we didn't want to
just give every developer a series of machines in the cloud to run their code on.

Bay allows you to declare a system from a series of small containers, linking
them together to declare dependencies on each other and allowing you to build
and run any sensible subset of the dependency tree that has all its links
satisfied.

In addition, it also supports using local SSH keys for building, live-mounting
developer code into containers for immediate feedback, built-in diagnosis tools
for problems, and support for sourcing commonly-used container images
from a central source. It was also built around the concept of running some
containers remotely, shared between developers, so that the load on individual
developer machines is lower.


Why write your own thing?
-------------------------

First, we were convinced we had to move to containers; until around 2014, we
had been using a single Vagrant machine to run the entire site, but this was
quickly becoming untenable (and taking up to 8 hours to build from our remote
offices). The only solution to not running the entire site was to split it up,
and containers provided us the perfect abstraction for that.

Given this, we first turned to tools like ``docker-compose``, but they are
designed for small-scale development; in particular, we needed:

* The ability to pass in local SSH keys from developer machines to build with.
  For security reasons, we don't allow a single global checkout key, and most
  Docker build tools assume that you have one.

* The ability to link and unlink parts of the site dynamically, without making
  people edit a YAML file, and for building only the images needed by the currently
  live part.

* The ability to host our entire collection of docker images and configuration
  in a single repository, and version and release them together.

* To be able to live-mount parts of the codebase into their relevant containers
  as they were being worked on rather than having to rebuild every time.

From these needs, ``tugboat``, the predecessor to Bay, was born. Over time, we
built out and refined it, culminating in a near-rewrite to produce what is now
Bay.


Future Plans
------------

Our two main pushes for the near future are:

* Support for prebuilt image management for key base images (ones that, in our
  case, can take 20 minutes plus to build). Not only is this knowing that images
  but can be pulled, but also tooling that allows people to maintain built images
  and see what has changed since they were built.

* Running some containers remotely and shared between developers, allowing us to
  offload a lot of the common infrastructure underlying a big site to a central
  location, and allowing our teams to run only what they are actively working on
  in their local environment.
