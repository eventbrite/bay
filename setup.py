from setuptools import setup
from bay import __version__

setup(
    name='bay',
    version=__version__,
    author='Eventbrite, Inc.',
    description='Docker-based development workflow tooling',
    long_description=(
        'Bay is a tool for assisting creation and management of Docker ' +
        'containers for development use.  It allows you to supplement a ' +
        'Dockerfile with additional information on how to run and link ' +
        'containers together. \n\nFor more, see http://github.com/eventbrite/bay/'
    ),
    packages=[
        "bay",
        "bay.cli",
        "bay.containers",
        "bay.docker",
        "bay.plugins",
        "bay.utils",
    ],
    include_package_data=True,
    install_requires=[
        'attrs',
        'Click>=6.6',
        'PyYAML',
        'docker~=2.3',
        'dockerpty==0.4.1',
        'scandir',
        'requests<2.11.0',
    ],
    extras_require={
        'spell': ['pylev'],
    },
    test_suite="tests",
    setup_requires=['pytest-runner'],
    tests_require=['pytest'],
    entry_points='''
        [console_scripts]
        bay = bay.cli:cli
        tug = bay.cli:cli

        [bay.plugins]
        attach = bay.plugins.attach:AttachPlugin
        boot = bay.plugins.boot:BootPlugin
        build = bay.plugins.build:BuildPlugin
        build_scripts = bay.plugins.build_scripts:BuildScriptsPlugin
        build_volumes = bay.plugins.build_volumes:BuildVolumesPlugin
        container = bay.plugins.container:ContainerPlugin
        doctor = bay.plugins.doctor:DoctorPlugin
        gc = bay.plugins.gc:GcPlugin
        help = bay.plugins.help:HelpPlugin
        hosts = bay.plugins.hosts:HostsPlugin
        images = bay.plugins.images:ImagesPlugin
        legacy_env = bay.plugins.legacy_env:LegacyEnvPlugin
        mounts = bay.plugins.mounts:DevModesPlugin
        profile = bay.plugins.profile:ProfilesPlugin
        ps = bay.plugins.ps:PsPlugin
        run = bay.plugins.run:RunPlugin
        ssh_agent = bay.plugins.ssh_agent:SSHAgentPlugin
        tail = bay.plugins.tail:TailPlugin
        volume = bay.plugins.volume:VolumePlugin
        waits = bay.plugins.waits:WaitsPlugin
    ''',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: Software Development',
    ],
)
