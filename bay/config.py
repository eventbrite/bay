import os
import yaml

from .exceptions import BadConfigError


class Config(object):
    """
    Main config manager. Dumb key-value store that just loads config files
    from various places plus a default and presents a combined view of them.

    This does not handle container configuration or info, just global settings.
    A schema is used to inform how to merge/override values.
    """

    # {section_name: {key: type}}
    schema = {
        "hosts": {
            "*": dict,
        },
        "bay": {
            "home": str,
            "build_log_path": str,
            "user_data_path": str,
            "user_profile_home": str,
            "ssh_agent_container": str,
            "port_proxy_container": str,
        }
    }

    defaults = {
        "hosts": {
            "unix://localhost": {},
        },
        "bay": {
            "home": os.path.expanduser(os.environ.get("BAY_HOME", ".")),
            "build_log_path": os.path.expanduser('~/.bay/{prefix}/build.log'),
            "user_data_path": os.path.expanduser('~/.bay/{prefix}'),
            "user_profile_home": os.path.expanduser('~/.bay'),
            "ssh_agent_container": "tugboat/ssh-agent",
            "port_proxy_container": "tugboat/port-proxy",
        },
    }

    def __init__(self, file_paths):
        self.file_paths = file_paths
        self.load()

    def load(self):
        """
        Loads data from the files.
        """
        self.data = {}
        self.add_config(self.defaults, "<defaults>")
        for file_path in self.file_paths:
            # Load YAML into memory
            with open(file_path, "r") as fh:
                file_data = yaml.safe_load(fh.read())
                self.add_config(file_data, file_path)

    def add_config(self, data, filename):
        """
        Adds the given config on top of the existing ones. Used during load
        and directly for CLI options.
        """
        # Check top level type
        if not isinstance(data, dict):
            raise BadConfigError("Config %s is not a dict at the top level." % filename)
        # Iterate through sections, check type
        for section, items in data.items():
            if not isinstance(items, dict):
                raise BadConfigError("Section %s in %s is not a dict" % (section, filename))
            if section not in self.schema:
                raise BadConfigError("Section %s in %s not in schema" % (section, filename))
            # Iterate through keys, check type
            for key, value in items.items():
                if key not in self.schema[section] and "*" not in self.schema[section]:
                    raise BadConfigError("%s.%s in %s not in schema" % (key, section, filename))
                valid_type = self.schema[section].get(key, self.schema[section].get("*", None))
                assert valid_type is not None
                if not isinstance(value, valid_type):
                    raise BadConfigError("%s.%s in %s is not %s" % (key, section, valid_type))
                # Save value
                self.data.setdefault(section, {})[key] = value

    def __getitem__(self, key):
        return self.data[key]

    def get_path(self, section, key, app):
        """
        Returns the given configuration value, but substituting {prefix} with the
        passed prefix, and making any parent directories. Must be used for file paths.
        """
        value = self.data[section][key].replace("{prefix}", app.containers.prefix)
        dirname = os.path.dirname(value)
        if not os.path.isdir(dirname):
            os.makedirs(dirname)
        return value
