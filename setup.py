from setuptools import setup, find_packages
from bay import __version__

setup(
    name='bay',
    version=__version__,
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'attrs',
        'Click>=6.6',
        'PyYAML',
        'docker-py>=1.6',
        'dockerpty==0.4.1',
        'scandir',
        'requests<2.11.0',
    ],
    extras_require={
        'spell': ['pylev'],
    },
    test_suite="tests",
    entry_points='''
        [console_scripts]
        bay = bay.cli:cli
        tug = bay.cli:cli

        [bay.plugins]
        container = bay.plugins.container:ContainerPlugin
        hosts = bay.plugins.hosts:HostsPlugin
        build = bay.plugins.build:BuildPlugin
        run = bay.plugins.run:RunPlugin
        ps = bay.plugins.ps:PsPlugin
        tail = bay.plugins.tail:TailPlugin
        legacy_env = bay.plugins.legacy_env:LegacyEnvPlugin
        build_scripts = bay.plugins.build_scripts:BuildScriptsPlugin
        mounts = bay.plugins.mounts:DevModesPlugin
        boot = bay.plugins.boot:BootPlugin
        ssh_agent = bay.plugins.ssh_agent:SSHAgentPlugin
        waits = bay.plugins.waits:WaitsPlugin
        attach = bay.plugins.attach:AttachPlugin
        profile = bay.plugins.profile:ProfilesPlugin
        build_volumes = bay.plugins.build_volumes:BuildVolumesPlugin
        gc = bay.plugins.gc:GcPlugin
    ''',
)
