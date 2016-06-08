# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

logger = logging.getLogger(__name__)

import os
import tarfile
import getpass
import json
import base64

import docker
from docker.utils import kwargs_from_env

from ..exceptions import AnsibleContainerNotInitializedException, \
    AnsibleContainerNoAuthenticationProvided
from ..engine import BaseEngine
from ..utils import *
from .utils import *

class Engine(BaseEngine):

    engine_name = 'Docker'
    orchestrator_name = 'Docker Compose'
    builder_container_img_name = 'ansible-container'
    builder_container_img_tag = 'ansible-container-builder'
    default_registry_url = 'https://index.docker.io/v1/'
    _client = None

    def all_hosts_in_orchestration(self):
        """
        List all hosts being orchestrated by the compose engine.

        :return: list of strings
        """
        compose_data = parse_compose_file(self.base_path)
        if compose_format_version(self.base_path, compose_data) == 2:
            services = compose_data.pop('services', {})
        else:
            services = compose_data
        return [key for key in services.keys() if key != self.builder_container_img_name]

    def hosts_touched_by_playbook(self):
        """
        List all hosts touched by the execution of the build playbook.

        :return: list of strings
        """
        compose_data = parse_compose_file(self.base_path)
        if compose_format_version(self.base_path, compose_data) == 2:
            services = compose_data.pop('services', {})
        else:
            services = compose_data
        ansible_args = services.get(self.builder_container_img_name,
                                    {}).get('command', [])
        if not ansible_args:
            logger.warning(
                'No ansible playbook arguments found in container.yml')
            return []
        builder_img_id = self.get_image_id_by_tag(self.builder_container_img_tag)
        with teed_stdout() as stdout, make_temp_dir() as temp_dir:
            launch_docker_compose(self.base_path, self.project_name,
                                  temp_dir, 'listhosts',
                                  services=[self.builder_container_img_name],
                                  no_color=True,
                                  which_docker=which_docker(),
                                  builder_img_id=builder_img_id)
            # We need to cleverly extract the host names from the output...
            lines = stdout.getvalue().split('\r\n')
            lines_minus_builder_host = [line.rsplit('|', 1)[1] for line
                                        in lines if '|' in line]
            host_lines = [line for line in lines_minus_builder_host
                          if line.startswith('       ')]
            hosts = list(set([line.strip() for line in host_lines]))
        return hosts

    def build_buildcontainer_image(self):
        """
        Build in the container engine the builder container

        :return: generator of strings
        """
        assert_initialized(self.base_path)
        client = self.get_client()
        with make_temp_dir() as temp_dir:
            logger.info('Building Docker Engine context...')
            tarball_path = os.path.join(temp_dir, 'context.tar')
            tarball_file = open(tarball_path, 'wb')
            tarball = tarfile.TarFile(fileobj=tarball_file,
                                      mode='w')
            container_dir = os.path.normpath(os.path.join(self.base_path,
                                                          'ansible'))
            try:
                tarball.add(container_dir, arcname='ansible')
            except OSError:
                raise AnsibleContainerNotInitializedException()
            jinja_render_to_temp('ansible-dockerfile.j2', temp_dir,
                                 'Dockerfile')
            tarball.add(os.path.join(temp_dir, 'Dockerfile'),
                        arcname='Dockerfile')
            jinja_render_to_temp('hosts.j2', temp_dir, 'hosts',
                                 hosts=extract_hosts_from_docker_compose(
                                     self.base_path))
            tarball.add(os.path.join(temp_dir, 'hosts'), arcname='hosts')
            tarball.close()
            tarball_file.close()
            tarball_file = open(tarball_path, 'rb')
            logger.info('Starting Docker build of Ansible Container image...')
            return [streamline for streamline in
                    client.build(fileobj=tarball_file,
                                 rm=True,
                                 custom_context=True,
                                 pull=True,
                                 forcerm=True,
                                 tag=self.builder_container_img_tag)]

    def get_image_id_by_tag(self, name):
        """
        Query the engine to get an image identifier by tag

        :param name: the image name
        :return: the image identifier
        """
        client = self.get_client()
        try:
            return client.images(name=name, quiet=True)[0]
        except IndexError:
            raise NameError('No image with the name %s' % name)

    def get_container_id_by_name(self, name):
        """
        Query the engine to get a container identifier by name

        :param name: the container name
        :return: the container identifier
        """
        client = self.get_client()
        try:
            return client.containers(
                filters={'name': name},
                limit=1, all=True, quiet=True)[0]
        except IndexError:
            raise NameError('No container with the name %s' % name)

    def remove_container_by_name(self, name):
        """
        Remove a container from the engine given its name

        :param name: the name of the container to remove
        :return: None
        """
        client = self.get_client()
        container_id, = client.containers(
            filters={'name': 'ansible_%s_1' % name},
            limit=1, all=True, quiet=True
        )
        self.remove_container_by_id(container_id)

    def remove_container_by_id(self, id):
        """
        Remove a container from the engine given its identifier

        :param id: container identifier
        :return: None
        """
        client = self.get_client()
        client.remove_container(id)

    def get_builder_image_id(self):
        """
        Query the enginer to get the builder image identifier

        :return: the image identifier
        """
        return self.get_image_id_by_tag(self.builder_container_img_tag)

    def get_builder_container_id(self):
        """
        Query the enginer to get the builder container identifier

        :return: the container identifier
        """
        return self.get_container_id_by_name(self.builder_container_img_name)

    def build_was_successful(self):
        """
        After the build was complete, did the build run successfully?

        :return: bool
        """
        client = self.get_client()
        build_container_info, = client.containers(
            filters={'name': 'ansible_ansible-container_1'},
            limit=1, all=True
        )
        # Not the best way to test for success or failure, but it works.
        exit_status = build_container_info['Status']
        return '(0)' in exit_status

    def orchestrate(self, operation, temp_dir, hosts=[], context={}):
        """
        Execute the compose engine.

        :param operation: One of build, run, or listhosts
        :param temp_dir: A temporary directory usable as workspace
        :param hosts: (optional) A list of hosts to limit orchestration to
        :return: The exit status of the builder container (None if it wasn't run)
        """
        builder_img_id = self.get_image_id_by_tag(
            self.builder_container_img_tag)
        extra_options = getattr(self, 'orchestrate_%s_extra_args' % operation)()
        launch_docker_compose(self.base_path, self.project_name,
                              temp_dir, operation,
                              which_docker=which_docker(),
                              services=hosts,
                              builder_img_id=builder_img_id,
                              extra_command_options=extra_options,
                              **context)

    def orchestrate_build_extra_args(self):
        """
        Provide extra arguments to provide the orchestrator during build.

        :return: dictionary
        """
        return {'--abort-on-container-exit': True}

    def orchestrate_run_extra_args(self):
        """
        Provide extra arguments to provide the orchestrator during run.

        :return: dictionary
        """
        return {}

    def orchestrate_listhosts_args(self):
        """
        Provide extra arguments to provide the orchestrator during listhosts.

        :return: dictionary
        """
        return {}

    def post_build(self, host, version, flatten=True, purge_last=True):
        client = self.get_client()
        container_id, = client.containers(
            filters={'name': 'ansible_%s_1' % host},
            limit=1, all=True, quiet=True
        )
        previous_image_id, previous_image_buildstamp = get_latest_image_for(
            self.project_name, host, client
        )
        if flatten:
            logger.info('Flattening image...')
            exported = client.export(container_id)
            client.import_image_from_data(
                exported.read(),
                repository='%s-%s' % (self.project_name, host),
                tag=version)
        else:
            logger.info('Committing image...')
            client.commit(container_id,
                          repository='%s-%s' % (self.project_name, host),
                          tag=version,
                          message='Built using Ansible Container'
                          )
        image_id, = client.images(
            '%s-%s:%s' % (self.project_name, host, version),
            quiet=True
        )
        logger.info('Exported %s-%s with image ID %s', self.project_name, host,
                    image_id)
        client.tag(image_id, '%s-%s' % (self.project_name, host), tag='latest',
                   force=True)
        logger.info('Cleaning up %s build container...', host)
        client.remove_container(container_id)
        if purge_last and previous_image_id:
            logger.info('Removing previous image...')
            client.remove_image(previous_image_id, force=True)

    def registry_login(self, username=None, password=None, email=None, url=None):
        """
        Logs into registry for this engine

        :param username: Username to login with
        :param password: Password to login with - None to prompt user
        :param email: Email address to login with
        :param url: URL of registry - default defined per backend
        :return: None
        """
        client = self.get_client()
        if not url:
            url = self.default_registry_url
        if username and email:
            # We assume if no username was given, the docker config file
            # suffices
            while not password:
                password = getpass.getpass(u'Enter password for %s at %s: ' % (
                    username, url
                ))
            client.login(username=username, password=password, email=email,
                         registry=url)
        username, email = self.currently_logged_in_registry_user(url)
        if not username:
            raise AnsibleContainerNoAuthenticationProvided(
                u'Please provide login '
                u'credentials for this registry.')
        return username

    DOCKER_CONFIG_FILEPATH_CASCADE = [
        os.environ.get('DOCKER_CONFIG', ''),
        os.path.join(os.environ.get('HOME', ''), '.docker', 'config.json'),
        os.path.join(os.environ.get('HOME', ''), '.dockercfg')
    ]

    def currently_logged_in_registry_user(self, url):
        """
        Gets logged in user from configuration for a URL for the registry for
        this engine.

        :param url: URL
        :return: (username, email) tuple
        """

        for docker_config_filepath in self.DOCKER_CONFIG_FILEPATH_CASCADE:
            if docker_config_filepath and os.path.exists(
                    docker_config_filepath):
                docker_config = json.load(open(docker_config_filepath))
                break
        if 'auths' in docker_config:
            docker_config = docker_config['auths']
        auth_key = docker_config.get(url, {}).get('auth', '')
        email = docker_config.get(url, {}).get('email', '')
        if auth_key:
            username, password = base64.decodestring(auth_key).split(':', 1)
            return username, email

    def push_latest_image(self, host, username):
        """
        Push the latest built image for a host to a registry

        :param host: The host in the container.yml to push
        :param username: The username to own the pushed image
        :return: None
        """
        client = self.get_client()
        image_id, image_buildstamp = get_latest_image_for(self.project_name,
                                                          host, client)
        client.tag(image_id,
                   '%s/%s-%s' % (username, self.project_name, host),
                   tag=image_buildstamp)
        logger.info('Pushing %s-%s:%s...', self.project_name, host, image_buildstamp)
        status = client.push('%s/%s-%s' % (username, self.project_name, host),
                             tag=image_buildstamp,
                             stream=True)
        last_status = None
        for line in status:
            line = json.loads(line)
            if type(line) is dict and 'error' in line:
                logger.error(line['error'])
            elif type(line) is dict and 'status' in line:
                if line['status'] != last_status:
                    logger.info(line['status'])
                last_status = line['status']
            else:
                logger.debug(line)

    def get_client(self):
        if not self._client:
            # To ensure version compatibility, we have to generate the kwargs ourselves
            client_kwargs = kwargs_from_env(assert_hostname=False)
            self._client = docker.AutoVersionClient(**client_kwargs)
        return self._client

    def get_config(self):
        '''
        Return the complete compose config less the ansible build host.

        :return: dict of compose config
        '''
        compose_data = parse_compose_file(self.base_path)
        version = compose_format_version(self.base_path, compose_data)
        if version == 2:
            services = compose_data.get('services', {})
        else:
            services = compose_data
        # remove the ansible build host
        if services.get(self.builder_container_img_name):
            services.pop(self.builder_container_img_name)
        # give each service a name attribute
        for service in services:
            services[service]['name'] = service
        if version == 2:
            config = compose_data.copy()
        else:
            config = dict(services=services.copy())
        return config
