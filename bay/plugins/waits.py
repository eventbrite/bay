import attr
import http.client
import socket
import time

from .base import BasePlugin


class WaitsPlugin(BasePlugin):
    """
    Contains the basic, standard waits. Waits' .check is called repeatedly and should return True if the condition is
    met or False if it is not.
    """

    def load(self):
        self.add_wait("http", HttpWait)
        self.add_wait("https", HttpsWait)
        self.add_wait("tcp", TcpWait)
        self.add_wait("time", TimeWait)


@attr.s
class HttpWait:
    """
    Checks that a HTTP endpoint exists and returns a good value.
    """

    instance = attr.ib()
    port = attr.ib(default=80)
    path = attr.ib(default="/")
    timeout = attr.ib(default=1)
    method = attr.ib(default="GET")
    headers = attr.ib(default=attr.Factory(dict))
    expected_codes = attr.ib(default=attr.Factory(lambda: range(200, 400)))

    connection_class = http.client.HTTPConnection

    def ready(self):
        conn = self.connection_class(self.instance.ip_address, self.port, timeout=self.timeout)
        # Run wait
        try:
            conn.request(self.method, self.path, headers=self.headers)
            response = conn.getresponse()
            if response.status in self.expected_codes:
                return True
        except:
            return False
        finally:
            conn.close()

    def description(self):
        return "HTTP on port {}".format(self.port)


class HttpsWait(HttpWait):
    """
    HTTPS variant of the HTTP wait
    """
    connection_class = http.client.HTTPSConnection

    def description(self):
        return "HTTPS on port {}".format(self.port)


@attr.s
class TcpWait:
    """
    Checks that a TCP port is open
    """

    instance = attr.ib()
    port = attr.ib(default=80)
    timeout = attr.ib(default=1)

    def ready(self):
        try:
            conn_kwargs = {}
            if self.timeout:
                conn_kwargs['timeout'] = self.timeout
            conn = socket.create_connection((self.instance.ip_address, self.port), **conn_kwargs)
            conn.close()
            return True
        except socket.error:
            return False

    def description(self):
        return "TCP on port {}".format(self.port)


@attr.s
class TimeWait:
    """
    Waits a number of seconds
    """

    # Everything needs instance, alas
    instance = attr.ib()
    seconds = attr.ib()

    def __attrs_post_init__(self):
        self.wait_until = time.time() + int(self.seconds)

    def ready(self):
        return time.time() >= self.wait_until

    def description(self):
        return "{} seconds".format(self.seconds)
