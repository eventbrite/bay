import time

from docker.errors import NotFound


class Towline(object):
    """
    Process communication helper that can monitor the boot process and
    provide information about what's happening.
    """

    # Number of seconds till we conclude the container doesn't have towline support
    NO_TOWLINE_TIMEOUT = 2

    def __init__(self, host, container_name):
        self.host = host
        self.container_name = container_name
        self._first_try = None

    def _read_file(self, path, default=None):
        """
        Helper to read the contents of a file inside a container
        """
        try:
            contents = self.host.client.copy(self.container_name, path).strip()
            return contents or default
        except NotFound:
            # Ignore missing containers or other errors
            return default

    @property
    def status(self):
        """
        Returns the container's current status as a (finished, message) tuple.
        Finished is True for successful boot, False for unsuccessful boot, and
        None if boot is still occuring.
        """
        # The container should exist by now
        if not self.host.container_exists(self.container_name):
            return (False, "Container does not exist")
        # If it's dead, that's a failed boot
        if not self.host.container_running(self.container_name):
            return (False, "Container died during boot")
        # See if we can read a status from it
        if self._first_try is None:
            self._first_try = time.time()
        container_status = self._read_file("/tugboat/boot_status")
        # If there's no status and the timeout has passed, they're not towline compatible
        if container_status is None and time.time() - self._first_try > self.NO_TOWLINE_TIMEOUT:
            return (True, "Non-towline boot complete")
        # See if boot is complete
        if self._read_file("/tugboat/boot_complete"):
            return (True, "Towline boot complete")
        else:
            return (None, container_status)
