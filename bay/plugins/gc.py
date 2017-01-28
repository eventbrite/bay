import attr
import click
import random
from docker.errors import NotFound

from .base import BasePlugin
from ..cli.argument_types import HostType
from ..cli.tasks import Task
from ..constants import PluginHook
from ..exceptions import DockerRuntimeError
from ..utils.sorting import dependency_sort


@attr.s
class GcPlugin(BasePlugin):
    """
    Does garbage collection either on demand or every so often after a build finishes.
    """

    provides = ["gc"]

    def load(self):
        self.add_command(gc)
        self.add_hook(PluginHook.POST_BUILD, self.post_build)

    def post_build(self, host, container, task):
        """
        Occasionally runs garbage collection automatically after a build.
        """
        collector = GarbageCollector(host)
        # Only check one in 10 times
        if random.random() < 0.1:
            # Then decide to GC based on the ratio
            probability = (1 - collector.clean_image_ratio()) * 0.1
            if random.random() < probability:
                collector.gc_all(task)


@attr.s
class GarbageCollector:
    """
    Allows garbage collection on a host.
    """

    host = attr.ib()

    def dead_containers(self):
        """
        Gets all container IDs that are not actually running
        """
        live_containers = set(c['Id'] for c in self.host.client.containers(all=False, trunc=False, quiet=True))
        all_containers = set(c['Id'] for c in self.host.client.containers(all=True, trunc=False, quiet=True))
        return all_containers - live_containers

    def clean_image_ratio(self):
        """
        Returns a rough estimate of the ratio of good images to all images, for
        use in automatic GC decisions.
        """
        return len(self.named_images()) / len(self.host.client.images(all=True))

    def named_images(self):
        """
        Gets all images with a tag from the current set of Docker images.
        We can't use the config as a source as there might be images from
        other projects or docker tools.
        """
        images = set()
        for image in self.host.client.images(all=False):
            repo_tags = [
                tag for tag in (image.get("RepoTags", []) or [])
                if tag != "<none>:<none>" and len(tag.split("/")) < 3
            ]
            if repo_tags:
                images.add(image['Id'])
        return images

    def live_images(self, force=False):
        """
        Gets image IDs (including intermediate layers) that are used by running containers
        """
        live_images = set()
        for container in self.host.client.containers(all=False, trunc=False):
            try:
                result = self.host.client.history(container['Image'])
            except NotFound:
                if force:
                    result = []
                else:
                    raise
            for image in result:
                live_images.add(image['Id'])
        return live_images

    def image_layers(self, named_images, force=False):
        """
        Gets image IDs of all layers used by the named images
        """
        current_images = set()
        for named_image in named_images:
            try:
                result = self.host.client.history(named_image)
            except NotFound:
                if force:
                    result = []
                else:
                    raise
            for image in result:
                current_images.add(image['Id'])
        return current_images

    def all_images(self):
        """
        Returns all the live image IDs on the host sorted in dependency order, with
        the children first and ancestors last.
        """
        image_parents = {}
        for image in self.host.client.images(quiet=False, all=True):
            image_parents[image['Id']] = image['ParentId'] if image['ParentId'] else None
        all_images = dependency_sort(image_parents.keys(), lambda current: [image_parents[current]])
        all_images.reverse()
        return all_images

    def gc_containers(self, parent_task):
        """
        Cleans up containers
        """
        task = Task("Removing dead containers", parent=parent_task)
        dead_containers = self.dead_containers()
        for i, name in enumerate(dead_containers):
            try:
                self.host.client.remove_container(name)
            except NotFound:
                raise DockerRuntimeError("Container {} vanished during gc".format(name))
            task.update(progress=(i + 1, len(dead_containers)))
        task.finish(status="Done", status_flavor=Task.FLAVOR_GOOD)

    def gc_remote_tags(self, parent_task):
        """
        Cleans up images without local tags (only remote tags)
        """
        task = Task("Removing remote tags", parent=parent_task)
        for image in self.host.client.images(all=False):
            for tag in (image.get("RepoTags", []) or []):
                if len(tag.split("/")) > 2:
                    self.host.client.remove_image(tag)
                    continue
        task.finish(status="Done", status_flavor=Task.FLAVOR_GOOD)

    def gc_images(self, parent_task):
        """
        Cleans up old (untagged/non-current images)
        """
        # Clean up images
        task = Task("Removing dead images", parent=parent_task)

        # Get images with names and expand into all their layers
        named_images = self.named_images()
        current_images = self.image_layers(named_images)

        # Get all images used by running containers
        live_images = self.live_images()

        # Subtract all of those from a dependency sorted list of all images
        dead_images = [x for x in self.all_images() if x not in current_images and x not in live_images]

        # Delete those images in the presented (dependency) order
        for i, image_id in enumerate(dead_images):
            try:
                self.host.client.remove_image(image_id, force=True, noprune=True)
            except NotFound:
                raise DockerRuntimeError("Image {} vanished during gc".format(image_id))
            task.update(progress=(i + 1, len(dead_images)))
        task.finish(status="Done", status_flavor=Task.FLAVOR_GOOD)

    def gc_all(self, parent_task):
        task = Task("Running garbage collection", parent=parent_task)
        self.gc_containers(task)
        self.gc_remote_tags(task)
        self.gc_images(task)
        task.finish(status="Done", status_flavor=Task.FLAVOR_GOOD)


@click.command()
@click.option('--host', '-h', type=HostType(), default='default')
@click.pass_obj
def gc(app, host):
    """
    Runs the garbage collection manually.
    """
    GarbageCollector(host).gc_all(app.root_task)
