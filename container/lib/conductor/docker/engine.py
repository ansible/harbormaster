# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging
plainLogger = logging.getLogger(__name__)

from container.common.visibility import getLogger
logger = getLogger(__name__)

import base64
import datetime
import json
import os
import re

try:
    import httplib as StatusCodes
except ImportError:
    from http import HTTPStatus as StatusCodes

from ..engine import BaseEngine
from .. import utils
from container.common import exceptions, logmux
from container.common.docker import DockerEngineUtilityMixin
from container.common.utils import log_runs

try:
    import docker
    from docker import errors as docker_errors
    from docker.utils.ports import build_port_bindings
except ImportError:
    raise ImportError('Use of this engine requires you "pip install \'docker>=2.1\'" first.')

DOCKER_DEFAULT_CONFIG_PATH = os.path.join(os.environ.get('HOME', ''), '.docker', 'config.json')

DOCKER_CONFIG_FILEPATH_CASCADE = [
    os.environ.get('DOCKER_CONFIG', ''),
    DOCKER_DEFAULT_CONFIG_PATH,
    os.path.join(os.environ.get('HOME', ''), '.dockercfg')
]

REMOVE_HTTP = re.compile('^https?://')


class Engine(DockerEngineUtilityMixin, BaseEngine):

    CAP_BUILD_CONDUCTOR = True
    CAP_BUILD = True
    CAP_DEPLOY = True
    CAP_IMPORT = True
    CAP_LOGIN = True
    CAP_PUSH = True
    CAP_RUN = True

    @property
    def ansible_args(self):
        """Additional commandline arguments necessary for ansible-playbook runs."""
        return u'-c docker'

    @property
    def default_registry_url(self):
        return u'https://index.docker.io/v1/'

    @property
    def default_registry_name(self):
        return u'Docker Hub'

    @property
    def auth_config_path(self):
        result = DOCKER_DEFAULT_CONFIG_PATH
        for path in DOCKER_CONFIG_FILEPATH_CASCADE:
            if path and os.path.exists(path):
                result = os.path.normpath(os.path.expanduser(path))
                break
        return result

    def run_kwargs_for_service(self, service_name):
        to_return = self.services[service_name].copy()
        for key in ['from', 'roles', 'shell']:
            try:
                to_return.pop(key)
            except KeyError:
                pass
        if to_return.get('ports'):
            # convert ports from a list to a dict that docker-py likes
            new_ports = build_port_bindings(to_return.get('ports'))
            to_return['ports'] = new_ports
        return to_return

    @log_runs
    def run_container(self, image_id, service_name, **kwargs):
        """Run a particular container. The kwargs argument contains individual
        parameter overrides from the service definition."""
        run_kwargs = self.run_kwargs_for_service(service_name)
        run_kwargs.update(kwargs, relax=True)
        logger.debug('Running container in docker', image=image_id, params=run_kwargs)

        container_obj = self.client.containers.run(
            image=image_id,
            detach=True,
            **run_kwargs
        )

        log_iter = container_obj.logs(stdout=True, stderr=True, stream=True)
        mux = logmux.LogMultiplexer()
        mux.add_iterator(log_iter, plainLogger)
        return container_obj.id

    @log_runs
    def commit_role_as_layer(self,
                             container_id,
                             service_name,
                             fingerprint,
                             metadata,
                             with_name=False):
        container = self.client.containers.get(container_id)
        image_name = self.image_name_for_service(service_name)
        image_version = datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')
        image_config = utils.metadata_to_image_config(metadata)
        image_config.setdefault('Labels', {})[self.FINGERPRINT_LABEL_KEY] = fingerprint
        commit_data = dict(repository=image_name if with_name else None,
            tag=image_version if with_name else None,
            message=self.LAYER_COMMENT,
            conf=image_config)
        logger.debug('Committing new layer', params=commit_data)
        return container.commit(**commit_data).id

    def tag_image_as_latest(self, service_name, image_id):
        image_obj = self.client.images.get(image_id)
        image_obj.tag(self.image_name_for_service(service_name), 'latest')

    def generate_orchestration_playbook(self, repository_data=None):
        """If repository_data is specified, presume to pull images from that
        repository. If not, presume the images are already present."""
        munged_services = {}

        for service_name, service in self.services.items():
            image = self.get_latest_image_for_service(service_name)
            runit = {
                'image': image.tags[0],
            }
            logger.debug('Adding new service to definition',
                service=service_name, definition=runit)
            munged_services[service_name] = runit

        playbook = [{
            'hosts': 'localhost',
            'gather_facts': False,
            'tasks': [
                {
                    'docker_service': {
                        'project_name': self.project_name,
                        'state': state,
                        'definition': {
                            'version': '2',
                            'services': munged_services,
                        }
                    }
                } for state in ('absent', 'present')
            ]
        }]
        logger.debug('Created playbook to run project', playbook=playbook)
        return playbook

    def push(self, image_id, service_name, repository_data):
        """
        Puse an image to a remote registry.
        """
        tag = repository_data.get('tag')
        namespace = repository_data.get('namespace')
        url = repository_data.get('url')
        auth_config = {
            'username': repository_data.get('username'),
            'password': repository_data.get('password')
        }

        build_stamp = self.get_build_stamp_for_image(image_id)
        tag = tag or build_stamp

        repository = "%s/%s-%s" % (namespace, self.project_name, service_name)
        if url != self.default_registry_url:
            url = REMOVE_HTTP.sub('', url)
            repository = "%s/%s" % (re.sub('/$', '', url), repository)

        logger.info('Tagging %s' % repository)
        self.api_client.tag(image_id, repository, tag=tag)

        logger.info('Pushing %s:%s...' % (repository, tag))
        stream = self.api_client.push(repository, tag=tag, stream=True, auth_config=auth_config)

        last_status = None
        for data in stream:
            data = data.splitlines()
            for line in data:
                line = json.loads(line)
                if type(line) is dict and 'error' in line:
                    plainLogger.error(line['error'])
                if type(line) is dict and 'status' in line:
                    if line['status'] != last_status:
                        plainLogger.info(line['status'])
                    last_status = line['status']
                else:
                    plainLogger.debug(line)

    def get_runtime_volume_id(self):
        try:
            container_data = self.client.api.inspect_container(
                self.container_name_for_service('conductor')
            )
        except docker_errors.APIError:
            raise ValueError('Conductor container not found.')
        mounts = container_data['Mounts']
        try:
            usr_mount, = [mount for mount in mounts if mount['Destination'] == '/usr']
        except ValueError:
            raise ValueError('Runtime volume not found on Conductor')
        return usr_mount['Name']


    def login(self, username, password, email, url, config_path):
        """
        If username and password are provided, authenticate with the registry.
        Otherwise, check the config file for existing authentication data.
        """
        if username and password:
            try:
                self.client.login(username=username, password=password, email=email,
                                  registry=url, reauth=True)
            except docker_errors.APIError as exc:
                raise exceptions.AnsibleContainerConductorException(
                    u"Error logging into registry: {}".format(exc)
                )
            except Exception:
                raise

            self.update_config_file(username, password, email, url, config_path)

        username, password = self.get_registry_auth(url, config_path)
        if not username:
            raise exceptions.AnsibleContainerConductorException(
                u'Please provide login credentials for registry {}.'.format(url))
        return username, password

    @staticmethod
    def update_config_file(username, password, email, url, config_path):
        """Update the config file with the authorization."""
        try:
            # read the existing config
            config = json.load(open(config_path, "r"))
        except ValueError:
            config = dict()

        if not config.get('auths'):
            config['auths'] = dict()

        if not config['auths'].get(url):
            config['auths'][url] = dict()
        encoded_credentials = dict(
            auth=base64.b64encode(username + b':' + password),
            email=email
        )
        config['auths'][url] = encoded_credentials
        try:
            json.dump(config, open(config_path, "w"), indent=5, sort_keys=True)
        except Exception as exc:
            raise exceptions.AnsibleContainerConductorException(
                u"Failed to write registry config to {0} - {1}".format(config_path, exc)
            )

    @staticmethod
    def get_registry_auth(registry_url, config_path):
        """
        Retrieve from the config file the current authentication for a given URL, and
        return the username, password
        """
        username = None
        password = None
        try:
            docker_config = json.load(open(config_path))
        except ValueError:
            # The configuration file is empty
            return username, password
        if docker_config.get('auths'):
            docker_config = docker_config['auths']
        auth_key = docker_config.get(registry_url, {}).get('auth', None)
        if auth_key:
            username, password = base64.decodestring(auth_key).split(':', 1)
        return username, password
