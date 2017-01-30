import attr

from ..exceptions import BadConfigError
from ..utils.sorting import dependency_sort


@attr.s
class ContainerFormation:
    """
    Represents a desired or current layout of containers on a single host,
    including their links, image versions, environment etc.

    Formations have a network, which is how we identify which containers might
    be part of a formation or not (e.g. if a container is launched on an
    "eventbrite" network but the formation does not contain it, it should be
    shut down).

    Cross-network linking is done via use of "proxy containers", which get
    put in as a link alias with the right name and forward all connections
    on the appropriate ports to a remote endpoint. Formations are only scoped
    to the host; higher-level management of a set of different hosts is done
    elsewhere.
    """
    graph = attr.ib()
    network = attr.ib(default=None)  # a string network name, defaults to graph.prefix
    _instances = attr.ib(default=attr.Factory(list))
    container_instances = attr.ib(default=attr.Factory(dict), init=False)

    def __attrs_post_init__(self):
        if self.network is None:
            self.network = self.graph.prefix

        for instance in self._instances:
            self.add_instance(instance)

    def add_instance(self, instance):
        """
        Adds an existing instance into the formation.
        """
        assert instance.formation is None
        self.container_instances[instance.name] = instance
        instance.formation = self

    def remove_instance(self, instance):
        """
        Removes an instance from the formation
        """
        assert instance.formation is self
        del self.container_instances[instance.name]
        instance.formation = None

    def add_container(self, container):
        """
        Adds a container to run inside the formation along with all dependencies.
        Returns the Instance that was created for the container.
        """
        # Get the list of all dependencies and dependency-ancestors in topological order
        # (this also makes sure there are no cycles as a nice side effect)
        devmodes = self.graph.options(container).get('devmodes')
        dependency_ancestry = dependency_sort([container], self.graph.dependencies)[:-1]
        direct_dependencies = self.graph.dependencies(container)
        # Make sure all its dependencies are in the formation
        links = {}
        for dependency in dependency_ancestry:
            # Find the container to satisfy the dependency
            for instance in self:
                if instance.container == dependency:
                    break
            else:
                # OK, we need to make one
                instance = self.add_container(dependency)
            if dependency in direct_dependencies:
                links[dependency.name] = instance
        # Make the instance
        instance = ContainerInstance(
            name="{}.{}.1".format(self.graph.prefix, container.name),
            container=container,
            image=container.image_name,
            image_tag="latest",
            links=links,
            devmodes=devmodes,
        )
        self.add_instance(instance)
        return instance

    def clone(self):
        """
        Clones the formation into a new copy entirely unlinked from this one,
        including new Instances.
        """
        new = self.__class__(self.graph, self.network)
        for instance in self:
            new.add_instance(instance.clone())
        return new

    def __getitem__(self, key):
        return self.container_instances[key]

    def __contains__(self, key):
        return key.name in self.container_instances

    def __iter__(self):
        return iter(self.container_instances.values())


@attr.s
class ContainerInstance:
    """
    Represents a single container as part of an overall ContainerFormation
    request.

    :name: The runtime name of the container, like "eventbrite.core-frontend.1"
    :container: The Container instance that's backing this container
    :image: The image name/hash to use for the container
    :links: A dictionary of {alias_str: ContainerInstance} that maps other containers to links
    :devmodes: A set of enabled devmode strings as defined on the Container
    :ports: Exposed ports as {external_port: container_port}
    :environment: Extra environment variables to set in the container
    :command: A custom command override (as a list of string arguments, like subprocess.call takes)
    :foreground: If True, the container is launched in the foreground and a TTY attached
    """

    name = attr.ib()
    container = attr.ib()
    image = attr.ib()
    image_tag = attr.ib()
    links = attr.ib(default=attr.Factory(dict))
    devmodes = attr.ib(default=attr.Factory(set))
    ports = attr.ib(default=attr.Factory(dict))
    environment = attr.ib(default=attr.Factory(dict))
    command = attr.ib(default=None)
    foreground = attr.ib(default=None)
    formation = attr.ib(default=None, init=False)

    def __attrs_post_init__(self):
        self.ports.update(dict(self.container.ports.items()))
        self.validate()

    def validate(self):
        """
        Cross-checks the settings we have against the options the Container has
        """
        # Verify all link targets are possible
        for alias, target in self.links.items():
            if target.container not in self.container.graph.dependencies(self.container):
                raise BadConfigError("It is not possible to link %s to %s as %s" % (target, self.container, alias))
        # Verify devmodes exist
        for devmode in self.devmodes:
            if devmode not in self.container.devmodes:
                raise BadConfigError("Invalid devmode %s" % devmode)

    def clone(self):
        """
        Returns a safely mutable clone of this Instance
        """
        return self.__class__(
            name=self.name,
            container=self.container,
            image=self.image,
            links=self.links,
            devmodes=self.devmodes,
            ports=self.ports,
            environment=self.environment,
            command=self.command,
            foreground=self.foreground,
        )

    def different_from(self, other):
        """
        Returns if the other instance is different from this one at all
        (i.e. we need to stop it and start us)
        """
        return (
            self.name != other.name or
            self.container != other.container or
            self.image != other.image or
            self.links != other.links or
            self.devmodes != other.devmodes or
            self.ports != other.ports or
            self.environment != other.environment or
            self.command != other.command or
            other.foreground or
            self.foreground
        )

    def __eq__(self, other):
        return self.name == other.name

    def __ne__(self, other):
        return not (self == other)

    def __hash__(self):
        return hash(self.name)

    def __repr__(self):
        return "<ContainerInstance {} ({})>".format(self.name, self.container.name)
