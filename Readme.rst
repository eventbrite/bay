===
Bay
===

.. image:: https://img.shields.io/pypi/v/Bay.svg
    :target: https://pypi.python.org/pypi/bay/
    :alt: Latest Version

.. image:: https://travis-ci.org/eventbrite/bay.svg?branch=master
    :target: https://travis-ci.org/eventbrite/bay

Bay is a tool for assisting creation and management of Docker_
containers for development use.  It allows you to supplement a ``Dockerfile``
with additional information on how to run and link containers together.

It's currently in beta; documentation and more information is forthcoming.

.. _Docker: https://www.docker.com


Why Bay?
--------

To help support a docker-ized development environment, Bay provides a
number of features to streamline configuring and managing your environment(s).

1. Build Scripts

   Prior to building an image, Bay will run any configured build scripts
   to help configure the necessary environment.  These are often used to copy
   over any required configuration files (like a package manifest such as
   ``requirements.txt``).

2. SSH Tunneling

   Many build steps require authenticated SSH access.  To achieve this in a
   docker container, Bay supports creating an SSH tunnel (using ``socat``)
   for each build run, linking your configured SSH Agent into the container.

3. Runtime Configuration

   While a Dockerfile defines how to a build a container, Bay introduces a
   ``bay.yaml`` configuration for how to run a given container.  This includes
   what other containers it depends on along with volumes, ports, environment
   and other configuration.

4. Dependency Management

   You rarely work with just a single container.  Working out which containers
   to start and in what order is a challenge.  Bay keeps track of these
   dependencies for you, starting, stopping and building the necessary
   containers.

5. Development Profiles

   In large codebases, it helps to compartmentalize your system into distinct
   workflows.  Bay supports development profiles that group and customize
   specified containers for the given task.  Working on the frontend code?
   Then maybe you don't need to start all the backend data systems.

6. Library Overrides

   Unique to development environments is the need to override a given library,
   package or configuration with your local development copy.  Bay
   provides a mechanism (called a Devmode) for configuring and installing
   local copies of libraries for development in the container, similar to
   ``npm link`` command.

7. Automated Troubleshooting

   Bay features a ``doctor`` command for running diagnostics on your
   environment to help identify common issues.  These "doctor exams" are
   configurable and customizable to meet the specifics of your environment.


Philosophy
----------

Bay has a couple of philosophies that distinguish it from other similar
systems.  Much of this was lessons learned migrating an existing complex
architecture on to a docker environment.

1. Separation of Configuration/Deployment from Application Code

   Bay deviates from other systems by keeping your container configuration
   separate from your application code.  While plopping a Dockerfile in your
   code repo makes for an easy integration, more complex systems configure
   their dependencies from a diverse set of sources.

2. Extensibility

   Every development environment has unique requirements.  Bay extends the
   capabilities of the Docker build and run system to provide additional
   configuration to support the complexities of each codebase.

   In addition, Bay itself is built as a lean core of capabilities with an
   extension mechanism for adding additional functionality unique to your
   environment.  Through third party python packaging, developers can add
   additional commands, troubleshooting, build and runtime decorators, and
   custom logging.

License
-------

Copyright 2019 Eventbrite Inc.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this project except in compliance with the License.

You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0,
or included in this repository as the LICENSE file.

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
