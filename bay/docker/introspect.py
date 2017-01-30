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
                self.add_container(container)
        return self.formation

    def add_container(self, container_details):
        """
        Adds a container based on its Docker JSON information.
        """
        # Find the container name in the graph
        try:
            container_name = container_details['Labels']['com.eventbrite.bay.container']
            container = self.graph[container_name]
        except KeyError:
            raise DockerRuntimeError(
                "Cannot find local container for running container {}".format(container_details['Names'])
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
        # Make a formation instance
        instance = ContainerInstance(
            name=container_details['Names'][0].lstrip("/"),
            container=container,
            image_id=image_id,
        )
        # Set extra attributes because it's running
        instance.ip_address = container_details['NetworkSettings']['Networks']['eventbrite']['IPAddress']
        self.formation.add_instance(instance)
