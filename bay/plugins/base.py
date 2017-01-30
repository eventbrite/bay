import attr


class PluginMetaclass(type):
    """
    Custom plugin metaclass to allow comparison for sorting by memory ID
    """

    def __gt__(self, other):
        return id(self) > id(other)

    def __lt__(self, other):
        return id(self) < id(other)

    def __eq__(self, other):
        return id(self) == id(other)

    def __ne__(self, other):
        return id(self) != id(other)

    def __hash__(self):
        return hash(id(self))


@attr.s
class BasePlugin(object, metaclass=PluginMetaclass):
    """
    Base plugin template.
    """
    app = attr.ib()

    # Simple plugin dependency checking - any strings in requires must be
    # in exactly one other loaded plugin in provides.
    provides = []
    requires = []

    def load(self):
        pass

    def add_command(self, func):
        self.app.cli.add_command(func)

    def add_hook(self, hook_type, func):
        self.app.add_hook(hook_type, func)

    def add_catalog_type(self, name):
        self.app.add_catalog_type(name)

    def add_catalog_item(self, type_name, name, value):
        self.app.add_catalog_item(type_name, name, value)
