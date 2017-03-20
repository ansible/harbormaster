import os
import sys
import shlex
from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand
from pip.req import parse_requirements
import container

install_reqs = parse_requirements('requirements.txt', session=False)
reqs = [str(ir.req) for ir in install_reqs]

class PlaybookAsTests(TestCommand):
    user_options = [('ansible-args=', None, "Extra ansible arguments")]

    def initialize_options(self):
        self.ansible_args = u''
        TestCommand.initialize_options(self)

    def run_tests(self):
        import subprocess
        p = subprocess.Popen(
            ['ansible-playbook', '-vv', '-e', '@distros.yml'] +
            shlex.split(self.ansible_args) +
            ['run_tests.yml'],
            cwd=os.path.join(os.getcwd(), 'test'),
        )
        rc = p.wait()
        sys.exit(rc)

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
    entry_points={
        'console_scripts': ['ansible-container = container.cli:commandline']
    },
    install_requires=reqs,
    tests_require=[
        'ansible>=2.3.0',
        'pytest>=3',
        'docker>=2.1'
    ],
    extras_require={
        'docker': ['docker>=2.1'],
    },
    dependency_links=[
        'git+https//github.com/ansible/ansible'
    ],
    cmdclass={'test': PlaybookAsTests}
)
