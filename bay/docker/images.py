import attr

from docker.errors import NotFound
from ..exceptions import ImageNotFoundException


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
        raise NotImplementedError()

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
