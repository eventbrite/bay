import attr
import json

from docker.errors import NotFound

from ..cli.tasks import Task
from ..exceptions import ImageNotFoundException, ImagePullFailure


@attr.s
class ImageRepository:
    """
    A repository of available images for containers.

    Recommended use is internal-only by the plugins, do not use directly.
    """
    host = attr.ib()
    images = attr.ib(default=attr.Factory(dict))

    def list_images(self):
        """
        List all available images.
        """
        raise NotImplementedError()

    def add_image(self, image_name, version, image_hash):
        """
        Add a hash for a given image_name and version.

        This will update any existing hash for an image that was previously
        added to the image repository instance.
        """
        raise NotImplementedError()

    def image_versions(self, image_name):
        """
        Returns a dictionary of version name mapped to the image hash for a
        given image name. May return empty dictionary if there are no images.
        """
        # TODO: Expand to read all tags locally, not just a fixed list
        try:
            return {"latest": self.image_version(image_name, "latest")}
        except ImageNotFoundException:
            return {}

    def pull_image_version(self, image_name, image_tag, parent_task, fail_silently=False):
        """
        Pulls the most recent version of the given image tag from remote
        docker registry.
        """
        task = None
        registry_url = 'localhost:5000'

        # The string "local" has a special meaning which means the most recent
        # local image of that name, so we skip the remote call/check.
        if image_tag == "local":
            return None

        remote_name = "{registry_url}/{image_name}".format(
            registry_url=registry_url,
            image_name=image_name,
        )

        stream = self.host.client.pull(remote_name, tag=image_tag, stream=True)
        layer_status = {}
        current = 1
        total = 1
        for line in stream:
            if isinstance(line, bytes):
                line = line.decode("ascii")
            data = json.loads(line)
            if 'error' in data:
                if fail_silently:
                    return
                else:
                    raise ImagePullFailure(
                        data['error'],
                        remote_name=remote_name,
                        image_tag=image_tag
                    )
            elif 'id' in data:
                if data['status'].lower() == "downloading":
                    if task is None:
                        task = Task("Pulling remote image {}".format(image_name), parent=parent_task)
                    layer_status[data['id']] = data['progressDetail']

                elif "complete" in data['status'].lower() and data['id'] in layer_status:
                    layer_status[data['id']]['current'] = layer_status[data['id']]['total']

                if layer_status:
                    statuses = [x for x in layer_status.values()
                                if "current" in x and "total" in x]
                    current = sum(x['current'] for x in statuses)
                    total = sum(x['total'] for x in statuses)

                if task is not None:
                    task.update(progress=(current, total))

        if task is not None:
            task.finish(status="Done", status_flavor=Task.FLAVOR_GOOD)

        # Tag the remote image as the right name
        try:
            self.host.client.tag(
                remote_name + ":" + image_tag,
                image_name,
                tag=image_tag,
                force=True
            )
        except NotFound:
            if fail_silently:
                return
            else:
                raise ImagePullFailure(
                    'Failed to tag {}:{}'.format(remote_name, image_name),
                    remote_name=remote_name,
                    image_tag=image_tag
                )

    def image_version(self, image_name, image_tag):
        """
        Returns the Docker image hash of the requested image and tag, or
        raises ImageNotFoundException if it's not available on the host.
        """
        try:
            docker_info = self.host.client.inspect_image("{}:{}".format(image_name, image_tag))
            return docker_info['Id']
        except NotFound:
            # TODO: Maybe auto-build if we can?
            raise ImageNotFoundException(
                "Cannot find image {}:{}".format(image_name, image_tag),
                image=image_name,
                image_tag=image_tag,
            )
