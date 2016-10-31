# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

logger = logging.getLogger(__name__)

import os
import tarfile
import getpass
import json
import base64

from subprocess import call, Popen, PIPE
from distutils.spawn import find_executable
from ansible.module_utils._text import to_bytes, to_text

import docker
#from docker.client import errors as docker_errors
#from docker.utils import kwargs_from_env
#from compose.cli.command import project_from_options
#from compose.cli import main
from lxdapi import lxd
from yaml import dump as yaml_dump

from ..docker.engine import Engine as DockerEngine

from .. import __version__ as release_version
from ..engine import BaseEngine
from ..utils import *
from .utils import *

def lxc_exec(*cmd):
    lxc_cmd = find_executable('lxc')
    process = Popen((lxc_cmd,) + cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)
    stdout, stderr = process.communicate()
    stdout = to_text(stdout)
    stderr = to_text(stderr)

    print ' '.join(cmd)
    print stdout

    if process.returncode != 0:
        raise Exception(stderr)

    return stdout, stderr


class Engine(DockerEngine):

    engine_name = 'LXD'
    orchestrator_name = 'Ansible with LXD'
    builder_container_img_name = 'ansible-container'
    builder_container_img_tag = 'ansible-container-builder'
    default_registry_url = 'https://us.images.linuxcontainers.org/'
    _client = None
    api_version = ''
    temp_dir = None

    def orchestrate(self, operation, temp_dir, hosts=[], context={}):
        try:
            builder_img_id = self.get_image_id_by_tag(
                self.builder_container_img_tag)
        except NameError:
            image_version = '.'.join(release_version.split('.')[:2])
            builder_img_id = 'ansible/%s:%s' % (
                self.builder_container_img_tag, image_version)

        if operation == 'listhosts':
            lxc_exec(
                'exec',
                'ansible-container',
                '--',
                '/usr/local/bin/builder.sh',
                '/usr/bin/ansible-playbook',
                '-i',
                '/etc/ansible/ansible-container-inventory.py',
                '-c',
                'lxd',
                # We should allow extra ansible options here, i think
                # params.ansible_options,
                '--list-hosts',
                'main.yml',
            )

    def build_buildcontainer_image(self):
        """
        Build in the container engine the builder container

        :return: generator of strings
        """
        assert_initialized(self.base_path)
        client = self.get_client()
        container = None
        for url in client.get('containers').data['metadata']:
            if url.split('/')[-1] == 'ansible-container':
                container = client.get(url)

        if container is None:
            client.post('containers', json={
                'name': 'ansible-container',
                'architecture': 'x86_64',
                'profiles': ['default'],
                'source': {
                    'type': 'image',
                    'alias': 'alpine/3.4/amd64',
                    'server': 'https://images.linuxcontainers.org',
                    'mode': 'pull',
                },
            }).wait()
            container = client.get('containers/ansible-container')

        lxd.container_apply_status(
            client,
            lxd.container_get(client, 'ansible-container'),
            'Running',
        )

        # clear /ansible
        lxc_exec(
            'exec',
            'ansible-container',
            '--',
            'rm',
            '-rf',
            '/ansible',
            '/ansible-tmp',
        )

        # upload ansible to /ansible
        lxc_exec(
            'file',
            'push',
            '--recursive',
            'ansible/',
            'ansible-container/'
        )

        # upload container build script
        lxc_exec(
            'file',
            'push',
            os.path.join(
                os.path.dirname(__file__),
                'ansible-container-build.sh',
            ),
            'ansible-container/tmp/ansible-container-build.sh'
        )

        copy = (
            ('builder.sh', '/usr/local/bin/builder.sh'),
            ('ac_galaxy.py', '/usr/local/bin/ac_galaxy.py'),
            ('wait_on_host.py', '/usr/local/bin/wait_on_host.py'),
            ('ansible-container-inventory.py', '/etc/ansible/ansible-container-inventory.py'),
        )
        for src, dst in copy:
            lxc_exec(
                'file',
                'push',
                os.path.join(
                    os.path.dirname(__file__),
                    '..',
                    'templates',
                    src,
                ),
                'ansible-container/' + dst
            )

        # build container
        stdout, stderr = lxc_exec(
            'exec',
            'ansible-container',
            '--',
            'sh',
            '-x',
            '/tmp/ansible-container-build.sh',
        )

        # publish the container with an image alias
        stdout, stderr = lxc_exec(
            'publish',
            'ansible-container',
            '--alias',
            self.builder_container_img_tag,
        )

        return stdout.split('\n')

    def get_image_id_by_tag(self, name):
        """
        Query the engine to get an image identifier by tag

        :param name: the image name
        :return: the image identifier
        """
        client = self.get_client()
        try:
            return client.get('images/aliases/' + name)
        except lxd.APINotFoundException:
            raise NameError('No image with the name %s' % name)

    def get_container_id_by_name(self, name):
        """
        Query the engine to get a container identifier by name

        :param name: the container name
        :return: the container identifier
        """
        client = self.get_client()
        try:
            return client.get('containers/' + name)
        except lxd.APINotFoundException:
            raise NameError('No container with the name %s' % name)

    def get_client(self):
        if not self._client:
            self._client = lxd.API.factory()
        return self._client
