Theory & Data Model
===================


Container Graph
---------------

The set of available containers are arranged in a datastructure called a
*container graph*, which both includes the containers and their build-time and
runtime dependencies on each other.

The graph can be mutated by profiles to change the available links.


Buildable Volumes
-----------------

Sometimes it's necessary to build a volume rather than a container - for instance,
if there are a lot of large files that need to be shared between different containers.

Since we still want to use the container build system, this means it needs to build
as a container, but then somehow be available for use as a volume later on when it
comes time to mount the data.

What we do is define a standard, where a volume-building container unpacks itself
into a /volume/ directory on boot and then exits. This allows the container building
and caching to work correctly, along with image pulls, and then the built container
to be unpacked into a volume when required (after any successful build or pull).
