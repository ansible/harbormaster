# -*- coding: utf-8 -*-
from __future__ import absolute_import

from container.utils.visibility import getLogger
logger = getLogger(__name__)

import os
from container import exceptions, __version__ as container_version
from ruamel.yaml.comments import CommentedMap
from six import iteritems

try:
    from docker import errors as docker_errors
except ImportError:
    raise ImportError(
        u'You must install Ansible Container with Docker(tm) support. '
        u'Try:\npip install ansible-container==%s[docker]' % container_version)


class DockerSecretsMixin(object):
    """
    Methods needed to simulate external secrets in Docker. Docker Compose does not currently support external secrets.
    We're using the *docker_service* module, which relies on Compose, to launch services, and so it too does not support
    external secrets. Thus the need for these methods until the docker and/or compose Python modules add support for
    secrets of the external variety.
    """

    @property
    def secrets_volume_name(self):
        return "{}_secrets".format(self.project_name)

    def get_secret_volume(self):
        result = None
        try:
            for vol in self.client.volumes.list(filters={'name': self.secrets_volume_name}):
                if vol.name == self.secrets_volume_name:
                    result = vol
                    break
        except docker_errors.APIError as exc:
            raise exceptions.AnsibleContainerException(
                "Error fetching volume {}: {}".format(self.secrets_volume_name, str(exc))
            )
        return result

    def create_secret_volume(self):
        volume_obj = self.get_secret_volume()
        if not volume_obj:
            labels = {
                'created_by': 'ansible-container'
            }
            try:
                volume_obj = self.client.volumes.create(name=self.secrets_volume_name, labels=labels)
            except docker_errors.APIError as exc:
                raise exceptions.AnsibleContainerException(
                    "Error creating secrets volume: {}".format(str(exc))
                )
            logger.debug("Created Docker volume", volume_id=volume_obj.id)
        return volume_obj.id

    def generate_secrets_play(self, vault_files=None):
        secrets_to_disk = {}
        play = None

        if self.secrets:
            # Get the top-level secret definitions
            for secret_name, secret in iteritems(self.secrets):
                if isinstance(secret, dict):
                    for key, value in iteritems(secret):
                        full_name = "{}_{}".format(secret_name, key)
                        secrets_to_disk[full_name] = {
                            'subdir': os.path.join(self.secrets_mount_path, secret_name),
                            'variable': value,
                            'paths': [os.path.join(self.secrets_mount_path, secret_name, key)]
                        }
                else:
                    raise exceptions.AnsibleContainerException(
                        "Error: expecting top-level secrets in container.yml to be a dictionary."
                    )

        if self.services:
            # Add possible bind targets from each service
            for service_name, service in iteritems(self.services):
                if service.get('secrets', {}).get('docker'):
                    for docker_secret in service['secrets']['docker']:
                        if isinstance(docker_secret, dict):
                            if docker_secret.get('source') and docker_secret.get('target'):
                                secrets_to_disk[docker_secret['source']]['paths'].append(
                                    os.path.join(self.secrets_mount_path, docker_secret['target']))

        if secrets_to_disk:
            tasks = []
            logger.debug("SECRETS TO DISK", secrets=secrets_to_disk)
            for secret_name, secret in iteritems(secrets_to_disk):
                for path in secret['paths']:
                    tasks.append({
                        'name': 'Write secret to Docker volume',
                        'shell': "mkdir -p " + secret['subdir'] + " && echo '{{ " + secret['variable'] + " }}' >" +
                                 path,
                        'tags': ['start', 'restart', 'stop']
                    })

            play = CommentedMap([
                ('name', 'Create secrets'),
                ('hosts', 'localhost'),
                ('gather_facts', False)
            ])

            if vault_files:
                play['vars_files'] = [os.path.normpath(os.path.abspath(v)) for v in vault_files]
            play['tasks'] = tasks

        logger.debug("Generated secrets play", play=play)
        return play

    def generate_remove_volume_play(self):
        tasks = [{
            'name': 'Remove secrets volume',
            'docker_volume': {
                'name': self.secrets_volume_name,
                'state': 'absent'
            },
            'tags': ['destroy']
        }]
        play = CommentedMap([
            ('name', 'Remove secrets volume'),
            ('hosts', 'localhost'),
            ('gather_facts', False),
            ('tasks', tasks)
        ])
        return play
