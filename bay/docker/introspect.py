import attr
from ..containers.formation import ContainerFormation, ContainerInstance
from ..exceptions import DockerRuntimeError


@attr.s
class FormationIntrospector:
    """
    Given a docker host, introspects it to work out what Formation it is
    currently running and returns that for use/comparison with a desired new
    Formation.
    """
    host = attr.ib()
    graph = attr.ib()
    network = attr.ib(default=None)
    formation = attr.ib(init=False)

    def __attrs_post_init__(self):
        if self.network is None:
            self.network = self.graph.prefix

    def introspect(self):
        """
        Runs the introspection and returns a ContainerFormation.
        """
        # Make the formation
        self.formation = ContainerFormation(self.graph, self.network)
        # Go through all containers on the remote host that are running and on the right network
        for container in self.host.client.containers(all=False):
            if self.network in container['NetworkSettings']['Networks']:
                self.add_container(container['Names'][0].lstrip("/"))
        # As a second phase, go through and resolve links
        for instance in self.formation:
            instance.resolve_links()
        return self.formation

    def introspect_single_container(self, name):
        """
        Returns a single container introspected directly.
        """
        # Inspect image and list images have different formats, so we use list with filter here to match the other code
        details = self.host.client.containers(filters={"name": name})
        if not details:
            raise DockerRuntimeError("Cannot introspect single container {}".format(name))
        return self._create_container(details[0])

    def add_container(self, container_details):
        instance = self._create_container(container_details)
        self.formation.add_instance(instance)

    def _create_container(self, container_name):
        """
        Returns a container build from introspected information
        """
        container_details = self.host.client.inspect_container(container_name)
        # Find the container name in the graph
        try:
            labels = container_details['Config']['Labels']
            # Use the bay-specific (not eventbrite-specific, just named uniquely as per the docker label spec) label
            # to work out what container name this was.
            container = self.graph[labels['com.eventbrite.bay.container']]
        except KeyError:
            raise DockerRuntimeError(
                "Cannot find local container for running container {}".format(container_name)
            )
        # Get the image hash
        image = container_details['Image']
        assert ":" in image
        if image.startswith("sha256:"):
            image_id = image
        else:
            # It's a string name of a image
            # CONVERT IMAGE NAME INTO HASH USING REPO
            name, tag = image.split(":", 1)
            image_id = self.host.images.image_version(name, tag)
        # Work out links
        links = {}
        for link in (container_details['NetworkSettings']['Networks'][self.network].get('Links', None) or []):
            linked_container_name, link_alias = link.split(":", 1)
            links[link_alias] = linked_container_name
        # Work out devmodes
        mounted_targets = set()
        devmodes = set()
        for mount in container_details['Mounts']:
            mounted_targets.add(mount['Destination'])
        for devmode, mounts in container.devmodes.items():
            if all((destination in mounted_targets) for destination in mounts.keys()):
                devmodes.add(devmode)
        # Make a formation instance
        instance = ContainerInstance(
            name=container_name,
            container=container,
            image_id=image_id,
            links=links,
            devmodes=devmodes,
        )
        # Set extra networking attributes because it's running
        instance.ip_address = container_details['NetworkSettings']['Networks'][self.network]['IPAddress']
        instance.port_mapping = {}
        for container_port, host_details in container_details['NetworkSettings'].get('Ports', {}).items():
            if host_details:
                private_port = int(container_port.split("/", 1)[0])
                public_port = int(host_details[0]['HostPort'])
                instance.port_mapping[private_port] = public_port
        return instance
