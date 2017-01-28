import os
import logging
import subprocess

from .base import BasePlugin
from ..cli.tasks import Task
from ..constants import PluginHook
from ..exceptions import BuildFailureError


class BuildScriptsPlugin(BasePlugin):

    def load(self):
        self.add_hook(PluginHook.PRE_BUILD, self.run_pre_build_script)
        self.add_hook(PluginHook.POST_BUILD, self.run_post_build_script)

    def run_pre_build_script(self, host, container, task):
        """
        Runs the pre build scripts.
        """
        self.run_script("pre-build.sh", container, task)

    def run_post_build_script(self, host, container, task):
        """
        Runs the post build scriipts.
        """
        self.run_script("post-build.sh", container, task)

    def run_script(self, name, container, task):
        """
        Runs a script, logs its output, and errors if it breaks.
        """
        script_path = os.path.join(container.path, name)
        if os.path.exists(script_path):
            # Make a build directory, removing any old one if it exists
            build_dir = os.path.join(container.path, "build")
            if os.path.isdir(build_dir):
                subprocess.call(["rm", "-rf", build_dir])
            os.mkdir(build_dir)
            # Run the script
            script_task = Task("Running {}".format(name), parent=task)
            logger = logging.getLogger('build_logger')
            process = subprocess.Popen(
                ['bash', script_path],
                cwd=container.path,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            )
            while True:
                line = process.stdout.readline()
                logger.info(line.rstrip().decode("utf8"))
                if not line and process.poll() is not None:
                    break
            exit_code = process.wait()
            if exit_code:
                script_task.finish(status="Failed", status_flavor=Task.FLAVOR_BAD)
                raise BuildFailureError("Script {} failed".format(name))
            else:
                script_task.finish(status="Done", status_flavor=Task.FLAVOR_GOOD)
