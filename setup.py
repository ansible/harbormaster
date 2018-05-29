import os
import sys
import shlex
import shutil
import distutils.cmd
import distutils.log
from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand
from setuptools.command.sdist import sdist as SDistCommand
try: # for pip >= 10
    from pip._internal.req import parse_requirements
except ImportError: # for pip <= 9.0.3
    from pip.req import parse_requirements
import container

class PlaybookAsTests(TestCommand):
    user_options = [('ansible-args=', None, "Extra ansible arguments")]

    def initialize_options(self):
        self.ansible_args = u''
        TestCommand.initialize_options(self)

    def run(self):
        if sys.platform == 'darwin':
            # Docker for Mac exports certain paths into the virtual machine
            # actually running Docker. The default tempdir isn't one of them,
            # but /tmp is.
            os.environ['TMPDIR'] = '/tmp'
        return TestCommand.run(self)

    def run_tests(self):
        import subprocess
        p = subprocess.Popen(
            ['ansible-playbook'] +
            shlex.split(self.ansible_args) +
            ['run_tests.yml'],
            cwd=os.path.join(os.getcwd(), 'test'),
        )
        rc = p.wait()
        sys.exit(rc)

class BundleConductorFiles(SDistCommand):
    def run(self):
        shutil.copyfile('./setup.py', 'container/docker/files/setup.py')
        shutil.copyfile('./conductor-requirements.txt',
                        'container/docker/files/conductor-requirements.txt')
        shutil.copyfile('./conductor-requirements.yml',
                        'container/docker/files/conductor-requirements.yml')
        return SDistCommand.run(self)

class PrebakeConductors(distutils.cmd.Command):
    description = 'Pre-bake Conductor base images'
    user_options = [
        # The format is (long option, short option, description).
        ('debug', None, 'Enable debug output'),
        ('no-cache', None, 'Cache me offline, how bout dat?'),
        ('ignore-errors', None, 'Ignore build failures and continue building other distros'),
        ('distros=', None, 'Only pre-bake certain supported distros. Comma-separated.')
    ]

    def initialize_options(self):
        """Set default values for options."""
        # Each user option must be listed here with their default value.
        self.debug = False
        self.ignore_errors = False
        self.distros = ''

    def finalize_options(self):
        self.distros = self.distros.strip().split(',') if self.distros else []
        self.cache = not getattr(self, 'no_cache', False)

    def run(self):
        """Run command."""
        from container.cli import LOGGING
        from logging import config
        from container import core
        if self.debug:
            LOGGING['loggers']['container']['level'] = 'DEBUG'
        config.dictConfig(LOGGING)
        core.hostcmd_prebake(self.distros, debug=self.debug, cache=self.cache,
                             ignore_errors=self.ignore_errors)

if container.ENV == 'host':
    install_reqs = parse_requirements('requirements.txt', session=False)
    setup_kwargs = dict(
        install_requires=[str(ir.req) for ir in install_reqs if ir.match_markers()],
        tests_require=[
            'ansible>=2.3.0',
            'pytest>=3',
            'docker>=2.4.0,<3.0',
            'jmespath>=0.9'
        ],
        extras_require={
            'docker': ['docker>=2.4.0,<3.0'],
            'docbuild': ['Sphinx>=1.5.0'],
            'openshift': ['openshift==0.3.4'],
            'k8s': ['openshift==0.3.4']
        },
        #dependency_links=[
        #    'https://github.com/ansible/ansible/archive/devel.tar.gz#egg=ansible-2.4.0',
        #],
        cmdclass={'test': PlaybookAsTests,
                  'sdist': BundleConductorFiles,
                  'prebake': PrebakeConductors},
        entry_points={
            'console_scripts': [
                'ansible-container = container.cli:host_commandline']
        }
    )
else:
    setup_kwargs = dict(
        entry_points={
            'console_scripts': ['conductor = container.cli:conductor_commandline']
        },
    )


setup(
    name='ansible-container',
    version=container.__version__,
    packages=find_packages(include='container.*'),
    include_package_data=True,
    zip_safe=False,
    url='https://github.com/ansible/ansible-container',
    license='LGPLv3 (See LICENSE file for terms)',
    author='Joshua "jag" Ginsberg, Chris Houseknecht, and others (See AUTHORS file for contributors)',
    author_email='jag@ansible.com',
    description=('Ansible Container empowers you to orchestrate, build, run, and ship '
                 'Docker images built from Ansible playbooks.'),
    **setup_kwargs
)
