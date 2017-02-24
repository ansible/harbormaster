# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

logger = logging.getLogger(__name__)

import os
import re
import tarfile
import getpass
import json
import base64
import pprint

import docker
from docker.client import errors as docker_errors
from docker.utils import kwargs_from_env
from docker.constants import DEFAULT_TIMEOUT_SECONDS

try:
    from compose.cli.command import project_from_options
    from compose.cli import main
except Exception as exc:
    raise Exception("Error importing Docker compose: {0}".format(exc.message))

from yaml import dump as yaml_dump

from ..exceptions import (AnsibleContainerNotInitializedException,
                          AnsibleContainerNoAuthenticationProvidedException,
                          AnsibleContainerDockerConfigFileException,
                          AnsibleContainerDockerLoginException,
                          AnsibleContainerListHostsException,
                          AnsibleContainerNoMatchingHosts)

from ..engine import BaseEngine, REMOVE_HTTP
from ..utils import *
from .. import __version__ as release_version
from .utils import *

if not os.environ.get('DOCKER_HOST'):
    logger.warning('No DOCKER_HOST environment variable found. Assuming UNIX '
                   'socket at /var/run/docker.sock')


def get_timeout():
    timeout = DEFAULT_TIMEOUT_SECONDS
    source = None
    if os.environ.get('DOCKER_CLIENT_TIMEOUT'):
        timeout_value = os.environ.get('DOCKER_CLIENT_TIMEOUT')
        source = 'DOCKER_CLIENT_TIMEOUT'
    elif os.environ.get('COMPOSE_HTTP_TIMEOUT'):
        timeout_value = os.environ.get('COMPOSE_HTTP_TIMEOUT')
        source = 'COMPOSE_HTTP_TIMEOUT'
    if source:
        try:
            timeout = int(timeout_value)
        except ValueError:
            raise Exception("Error: {0} set to '{1}'. Expected an integer.".format(source, timeout_value))
    logger.debug("Setting Docker client timeout to {0}".format(timeout))
    return timeout


class Engine(BaseEngine):

    engine_name = 'Docker'
    orchestrator_name = 'Docker Compose'
    builder_container_img_name = 'ansible-container'
    builder_container_img_tag = 'ansible-container-builder'
    default_registry_url = 'https://index.docker.io/v1/'
    default_registry_name = 'dockerhub'
    _client = None
    _orchestrated_hosts = None
    api_version = ''
    temp_dir = None

    def all_hosts_in_orchestration(self):
        """
        List all hosts being orchestrated by the compose engine.

        :return: list of strings
        """
        services = self.config.get('services')
        return list(services.keys()) if services else []

    def hosts_touched_by_playbook(self):
        """
        List all hosts touched by the execution of the build playbook.

        :return: frozenset of strings
        """
        if not self._orchestrated_hosts:
            with teed_stdout() as stdout, make_temp_dir() as temp_dir:
                self.orchestrate('listhosts', temp_dir,
                                 hosts=[self.builder_container_img_name])
                logger.info('Cleaning up Ansible Container builder...')
                builder_container_id = self.get_builder_container_id()
                self.remove_container_by_id(builder_container_id)
                # We need to cleverly extract the host names from the output...
                logger.debug('--list-hosts\n%s', stdout.getvalue())
                lines = stdout.getvalue().split('\r\n')
                clean_exit = False
                for line in lines:
                     if "exited with code 0" in line:
                         clean_exit = True
                         break
                if not clean_exit:
                    logger.error("ERROR: encountered the following while attempting to get hosts touched by main.yml:")
                    for line in lines:
                        logger.error(line)
                    raise AnsibleContainerListHostsException("ERROR: unable to get the list of hosts touched by main.yml") 
                lines_minus_builder_host = [line.rsplit('|', 1)[1] for line
                                            in lines if '|' in line]
                host_lines = set(line.strip() for line in lines_minus_builder_host
                              if line.startswith('       '))
                host_lines.discard('')
                self._orchestrated_hosts = frozenset(host_lines)
        return self._orchestrated_hosts

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

            for context_file in ['builder.sh', 'ansible-container-inventory.py',
                                 'ansible.cfg', 'wait_on_host.py', 'ac_galaxy.py']:
                tarball.add(os.path.join(jinja_template_path(), context_file),
                            arcname=context_file)

            tarball.close()
            tarball_file.close()
            tarball_file = open(tarball_path, 'rb')
            logger.info('Starting Docker build of Ansible Container image (please be patient)...')
            return client.build(fileobj=tarball_file,
                                custom_context=True,
                                tag=self.builder_container_img_tag,
                                nocache=True,
                                rm=True)

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

    def get_images_by_name(self, name):
        client = self.get_client()
        try:
            return client.images(name=name, quiet=True)
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

    def get_config_for_shipit(self, pull_from=None, url=None, namespace=None, tag=None):
        '''
        Retrieve the configuration needed to run the shipit command

        :param pull_from: the exact registry URL to use
        :param url: registry url. required, if pull_from not provided.
        :param namespace: path to append to the url. required if pull_from not provided.
        :return: config dict
        '''
        config = get_config(self.base_path, var_file=self.var_file)
        client = self.get_client()
        image_path = None
        if self.params.get('local_images'):
            logger.info("Using local images")
        else:
            if pull_from:
                image_path = re.sub(r'/$', '', REMOVE_HTTP.sub('', pull_from))
            else:
                image_path = namespace
                if url != self.default_registry_url:
                    url = REMOVE_HTTP.sub('', url)
                    image_path = "%s/%s" % (re.sub(r'/$', '', url), image_path)

            logger.info("Images will be pulled from %s" % image_path)
        orchestrated_hosts = self.hosts_touched_by_playbook()
        for host, service_config in config.get('services', {}).items():
            if host in orchestrated_hosts:
                image_id, image_buildstamp = get_latest_image_for(self.project_name, host, client)
                image = '{0}-{1}:{2}'.format(self.project_name, host, tag or image_buildstamp)
                if image_path:
                    image = '{0}/{1}'.format(image_path, image)
                service_config.update({u'image':  image})
        return config

    # Docker-compose uses docopt, which outputs things like the below
    # So I'm starting with the defaults and then updating them.
    # One structure for the global options and one for the command specific

    DEFAULT_COMPOSE_OPTIONS = {
        u'--help': False,
        u'--host': None,
        u'--project-name': None,
        u'--skip-hostname-check': False,
        u'--tls': False,
        u'--tlscacert': None,
        u'--tlscert': None,
        u'--tlskey': None,
        u'--tlsverify': False,
        u'--verbose': False,
        u'--version': False,
        u'-h': False,
        u'--file': [],
        u'COMMAND': None,
        u'ARGS': []
    }

    DEFAULT_COMPOSE_UP_OPTIONS = {
        u'--abort-on-container-exit': False,
        u'--build': False,
        u'--force-recreate': False,
        u'--no-color': False,
        u'--no-deps': False,
        u'--no-recreate': False,
        u'--no-build': False,
        u'--remove-orphans': False,
        u'--timeout': None,
        u'-d': False,
        u'SERVICE': []
    }

    DEFAULT_COMPOSE_DOWN_OPTIONS = {
        u'--volumes': True,
        u'--remove-orphans': False
    }

    DEFAULT_COMPOSE_STOP_OPTIONS = {
        u'--timeout': None,
        u'SERVICE': []
    }

    DEFAULT_COMPOSE_RESTART_OPTIONS = {
        u'--timeout': None,
        u'SERVICE': []
    }

    def orchestrate(self, operation, temp_dir, hosts=[], context={}):
        """
        Execute the compose engine.

        :param operation: One of build, run, or listhosts
        :param temp_dir: A temporary directory usable as workspace
        :param hosts: (optional) A list of hosts to limit orchestration to
        :return: The exit status of the builder container (None if it wasn't run)
        """
        is_detached = self.params.pop('detached', False)
        try:
            builder_img_id = self.get_image_id_by_tag(
                self.builder_container_img_tag)
        except NameError:
            image_version = '.'.join(release_version.split('.')[:2])
            builder_img_id = 'ansible/%s:%s' % (
                self.builder_container_img_tag, image_version)

        options, command_options, command = self.bootstrap_env(
            temp_dir=temp_dir,
            builder_img_id=builder_img_id,
            behavior='orchestrate',
            compose_option='up',
            operation=operation,
            context=context)

        options.update({
            u'COMMAND': 'up',
            u'ARGS': ['--no-build'] + hosts})

        command_options[u'--no-build'] = True
        command_options[u'SERVICE'] = hosts
        command_options[u'--remove-orphans'] = self.params.get(
            'remove_orphans', False)

        if is_detached:
            logger.info('Deploying application in detached mode')
            command_options[u'-d'] = True

        command.up(command_options)

    def orchestrate_build_extra_args(self):
        """
        Provide extra arguments to provide the orchestrator during build.

        :return: dictionary
        """
        return {'--abort-on-container-exit': True,
                '--force-recreate': True}

    def orchestrate_run_extra_args(self):
        """
        Provide extra arguments to provide the orchestrator during run.

        :return: dictionary
        """
        return {}

    def terminate_stop_extra_args(self):
        """
        Provide extra arguments to provide the orchestrator during stop.

        :return: dictionary
        """
        return {}

    def orchestrate_install_extra_args(self):
        """
        Provide extra arguments to provide the orchestrator during install calls.

        :return: dictionary
        """
        return {}

    def orchestrate_listhosts_extra_args(self):
        """
        Provide extra arguments to provide the orchestrator during listhosts.

        :return: dictionary
        """
        return {'--no-color': True}

    def terminate(self, operation, temp_dir, hosts=[]):
        options, command_options, command = self.bootstrap_env(
            temp_dir=temp_dir,
            behavior='terminate',
            operation=operation,
            compose_option='stop'

        )
        options.update({u'COMMAND': u'stop'})
        command_options[u'SERVICE'] = hosts

        if self.params.get('force'):
            command.kill(command_options)
        else:
            command.stop(command_options)

    def restart(self, operation, temp_dir, hosts=[]):

        options, command_options, command = self.bootstrap_env(
            temp_dir=temp_dir,
            behavior='restart',
            operation=operation,
            compose_option='restart'
        )

        options.update({u'COMMAND': 'restart'})

        command_options[u'SERVICE'] = hosts

        command.restart(command_options)

    def restart_restart_extra_args(self):
        """
        Provide extra arguments to provide the orchestrator during restart.

        :return: dictionary
        """
        return {}

    def get_config_for_restart(self):
        compose_config = config_to_compose(self.config)
        return compose_config

    def _fix_volumes(self, service_name, service_config, compose_version='1', top_level_volumes=dict()):
        # If there are volumes defined for this host, we need to create the
        # volume if one doesn't already exist.
        client = self.get_client()
        project_name = os.path.basename(self.base_path).lower()
        for volume in service_config.get('volumes', []):
            if ':' not in volume:
                # This is an unnamed or anonymous volume. Create the volume with a predictable name.
                volume_name = ('%s-%s-%s' % (project_name, service_name, volume.replace('/', '_'))).replace('-_', '_')
                service_config['volumes'].remove(volume)
                service_config['volumes'].append('%s:%s' % (volume_name, volume))
                if compose_version == '1':
                    try:
                        client.inspect_volume(name=volume_name)
                    except docker_errors.NotFound:
                        # The volume does not exist
                        client.create_volume(name=volume_name, driver='local')
                if volume_name not in top_level_volumes.keys():
                    top_level_volumes[volume_name] = {}

    def get_config_for_build(self):
        compose_config = config_to_compose(self.config)
        version = compose_config.get('version', '1')
        volumes = compose_config.get('volumes', {})
        orchestrated_hosts = self.hosts_touched_by_playbook()
        if self.params.get('service'):
            # only build a subset of the orchestrated hosts
            orchestrated_hosts = orchestrated_hosts.intersection(self.params['service'])
            for host in set(compose_config['services'].keys()) - orchestrated_hosts:
                del compose_config['services'][host]
            if not compose_config['services']:
                raise AnsibleContainerNoMatchingHosts()
        logger.debug('Orchestrated hosts: %s', ', '.join(orchestrated_hosts))

        for service, service_config in compose_config['services'].items():
            if service in orchestrated_hosts:
                logger.debug('Setting %s to sleep', service)
                service_config.update(
                    dict(
                        user='root',
                        working_dir='/',
                        command='sh -c "while true; do sleep 1; done"',
                        entrypoint=[],
                    )
                )
                # Set ANSIBLE_CONTAINER=1 in env
                if service_config.get('environment'):
                    if isinstance(service_config['environment'], list):
                        service_config['environment'].append("ANSIBLE_CONTAINER=1")
                    elif isinstance(service_config['environment'], dict):
                        service_config['environment']['ANSIBLE_CONTAINER'] = 1
                else:
                    service_config['environment'] = dict(ANSIBLE_CONTAINER=1)

            if not self.params['rebuild']:
                tag = '%s-%s:latest' % (self.project_name,
                                        service)
                try:
                    self.get_image_id_by_tag(tag)
                except NameError:
                    logger.info('No image found for tag %s, so building from scratch',
                                '%s-%s:latest' % (self.project_name, service))
                    # have to rebuild this from scratch, as the image doesn't
                    # exist in the engine
                    pass
                else:
                    logger.debug('No NameError raised when searching for tag %s',
                                 '%s-%s:latest' % (self.project_name, service))
                    service_config['image'] = tag
            self._fix_volumes(service, service_config, compose_version=version, top_level_volumes=volumes)

        if volumes:
            compose_config['volumes'] = volumes

        return compose_config

    def get_config_for_run(self):
        if not self.params['production']:
            self.config.set_env('dev')
        compose_config = config_to_compose(self.config)
        version = compose_config.get('version', '1')
        volumes = compose_config.get('volumes', {})
        orchestrated_hosts = self.hosts_touched_by_playbook()
        for service, service_config in compose_config['services'].items():
            if service in orchestrated_hosts:
                service_config.update(
                    dict(
                        image='%s-%s:latest' % (self.project_name, service)
                    )
                )
            self._fix_volumes(service, service_config, compose_version=version, top_level_volumes=volumes)

        if volumes:
            compose_config['volumes'] = volumes

        return compose_config

    def get_config_for_stop(self):
        compose_config = config_to_compose(self.config)
        return compose_config

    def get_config_for_listhosts(self):
        compose_config = config_to_compose(self.config)
        version = compose_config.get('version', '1')
        volumes = compose_config.get('volumes', {})
        for service, service_config in compose_config['services'].items():
            service_config.update(
                dict(
                    user='root',
                    working_dir='/',
                    command='sh -c "while true; do sleep 1; done"',
                    entrypoint=[]
                )
            )
            self._fix_volumes(service, service_config, compose_version=version, top_level_volumes=volumes)

        if volumes:
            compose_config['volumes'] = volumes

        return compose_config

    def get_config_for_install(self):
        compose_config = config_to_compose(self.config)
        return compose_config

    def post_build(self, host, version, flatten=True, purge_last=True):
        client = self.get_client()
        container_id, = client.containers(
            filters={'name': 'ansible_%s_1' % host},
            limit=1, all=True, quiet=True
        )
        previous_image_id, previous_image_buildstamp = get_latest_image_for(
            self.project_name, host, client
        )
        cmd = self.config['services'][host].get('command', '')
        if isinstance(cmd, list):
            cmd = json.dumps(cmd)
        entrypoint = self.config['services'][host].get('entrypoint', '')
        if isinstance(entrypoint, list):
            entrypoint = json.dumps(entrypoint)
        image_config = dict(
            USER=self.config['services'][host].get('user', 'root'),
            LABEL='com.docker.compose.oneoff="" com.docker.compose.project="%s"' % self.project_name,
            ENTRYPOINT=entrypoint,
            CMD=cmd
        )
        # Only add WORKDIR if it does not contain an unexpanded environment var
        workdir = self.config['services'][host].get('working_dir', '/')
        image_config['WORKDIR'] = workdir if not re.search('\$|\{', workdir) else '/' 

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
                          message='Built using Ansible Container',
                          changes=u'\n'.join(
                              [u'%s %s' % (k, v)
                               for k, v in image_config.items()]
                          ))
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

        image_data = client.inspect_image(image_id)
        parent_sha = ''
        if image_data:
            parent_sha = image_data.get('Parent', '')

        if purge_last and previous_image_id and previous_image_id not in parent_sha:
            logger.info('Removing previous image...')
            client.remove_image(previous_image_id, force=True)

    DEFAULT_CONFIG_PATH = '~/.docker/config.json'

    def registry_login(self, username=None, password=None, email=None, url=None, config_path=DEFAULT_CONFIG_PATH):
        """
        Logs into registry for this engine

        :param username: Username to login with
        :param password: Password to login with - None to prompt user
        :param email: Email address to login with
        :param url: URL of registry - default defined per backend
        :param config_path: path to the registry config file
        :return: None
        """

        #TODO Make config_path a command line option?

        client = self.get_client()
        if not url:
            url = self.default_registry_url

        if username:
            # We assume if no username was given, the docker config file
            # suffices
            while not password:
                password = getpass.getpass(u'Enter password for %s at %s: ' % (
                    username, url
                ))
            try:
                client.login(username=username, password=password, email=email,
                             registry=url)
            except Exception as exc:
                raise AnsibleContainerDockerLoginException("Error logging into registry: %s" % str(exc))

            self.update_config_file(username, password, email, url, config_path)

        username, email = self.currently_logged_in_registry_user(url)
        if not username:
            raise AnsibleContainerNoAuthenticationProvidedException(
                u'Please provide login credentials for registry %r.' % url)
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
        username = None
        docker_config = None
        for docker_config_filepath in self.DOCKER_CONFIG_FILEPATH_CASCADE:
            if docker_config_filepath and os.path.exists(docker_config_filepath):
                docker_config = json.load(open(docker_config_filepath))
                break
        if not docker_config:
            raise AnsibleContainerDockerConfigFileException("Unable to read your docker config file. Try providing "
                                                            "login credentials for the registry.")
        if 'auths' in docker_config:
            docker_config = docker_config['auths']
        auth_key = docker_config.get(url, {}).get('auth', '')
        email = docker_config.get(url, {}).get('email', '')
        if auth_key:
            username, password = base64.decodestring(auth_key).split(':', 1)
        return username, email

    def update_config_file(self, username, password, email, url, config_path):
        '''
        Update the config file with the authorization.

        :param username:
        :param password:
        :param email:
        :param url:
        :param config_path
        :return: None
        '''

        path = os.path.expanduser(config_path)
        if not os.path.exists(path):
            # Create an empty config, if none exists
            config_path_dir = os.path.dirname(path)
            if not os.path.exists(config_path_dir):
                try:
                    os.makedirs(config_path_dir)
                except Exception as exc:
                    raise AnsibleContainerDockerConfigFileException("Failed to create file %s - %s" %
                                                                    (config_path_dir, str(exc)))
            self.write_config(path, dict(auths=dict()))

        try:
            # read the existing config
            config = json.load(open(path, "r"))
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
        self.write_config(path, config)

    @staticmethod
    def write_config(path, config):
        try:
            json.dump(config, open(path, "w"), indent=5, sort_keys=True)
        except Exception as exc:
            raise AnsibleContainerDockerConfigFileException("Failed to write docker registry config to %s - %s" %
                                                            (path, str(exc)))

    def push_latest_image(self, host, url=None, namespace=None, tag=None):
        '''
        :param host: The host in the container.yml to push
        :parm url: URL of the registry to which images will be pushed
        :param namespace: namespace to append to the URL
        :return: None
        '''
        client = self.get_client()
        image_id, image_buildstamp = get_latest_image_for(self.project_name,
                                                          host, client)
        tag = tag or image_buildstamp

        repository = "%s/%s-%s" % (namespace, self.project_name, host)
        if url != self.default_registry_url:
            url = REMOVE_HTTP.sub('', url)
            repository = "%s/%s" % (re.sub('/$', '', url), repository)

        logger.info('Tagging %s' % repository)
        client.tag(image_id, repository, tag=tag)

        logger.info('Pushing %s:%s...' % (repository, tag))
        stream = client.push(repository,
                             tag=tag,
                             stream=True)
        last_status = None
        for data in stream:
            data = data.splitlines()
            for line in data:
                line = json.loads(line)
                if type(line) is dict and 'error' in line:
                    logger.error(line['error'])
                if type(line) is dict and 'status' in line:
                    if line['status'] != last_status:
                        logger.info(line['status'])
                    last_status = line['status']
                else:
                    logger.debug(line)

    def get_client(self):
        if not self._client:
            # To ensure version compatibility, we have to generate the kwargs ourselves
            client_kwargs = kwargs_from_env(assert_hostname=False)
            timeout = get_timeout()
            self._client = docker.AutoVersionClient(timeout=timeout, **client_kwargs)
            self.api_version = self._client.version()['ApiVersion']
            # Set the version in the env so it can be used elsewhere
            os.environ['DOCKER_API_VERSION'] = self.api_version
        return self._client

    def print_version_info(self):
        client = self.get_client()
        pprint.pprint(client.info())
        pprint.pprint(client.version())

    def bootstrap_env(self, temp_dir, behavior, operation, compose_option,
                      builder_img_id=None, context=None):
        """
        Build common Docker Compose elements required to execute orchestrate,
        terminate, restart, etc.
        
        :param temp_dir: A temporary directory usable as workspace
        :param behavior: x in x_operation_extra_args
        :param operation: Operation to perform, like, build, run, listhosts, etc
        :param compose_option: x in DEFAULT_COMPOSE_X_OPTIONS
        :param builder_img_id: Ansible Container Builder Image ID
        :param context: extra context to send to jinja_render_to_temp
        :return: options (options to pass to compose),
                 command_options (operation options to pass to compose),
                 command (compose's top level command)
        """

        if context is None:
            context = {}

        self.temp_dir = temp_dir
        extra_options = getattr(self, '{}_{}_extra_args'.format(behavior,
                                                                operation))()
        config = getattr(self, 'get_config_for_%s' % operation)()
        logger.debug('%s' % (config,))
        config_yaml = yaml_dump(config['services']) if config else ''
        logger.debug('Config YAML is')
        logger.debug(config_yaml)
        hosts = self.all_hosts_in_orchestration()
        version = config.get('version', '1')
        volumes_yaml = yaml_dump(config['volumes']) if config and config.get('volumes') else ''
        if operation == 'build' and self.params.get('service'):
            # build operation is limited to a specific list of services
            hosts = list(set(hosts).intersection(self.params['service']))
        if version == '1':
            logger.debug('HERE VERSION 1')
            jinja_render_to_temp('%s-docker-compose.j2.yml' % (operation,),
                                 temp_dir,
                                 'docker-compose.yml',
                                 hosts=hosts,
                                 project_name=self.project_name,
                                 base_path=self.base_path,
                                 params=self.params,
                                 api_version=self.api_version,
                                 builder_img_id=builder_img_id,
                                 config=config_yaml,
                                 env=os.environ,
                                 **context)
        else:
            jinja_render_to_temp('compose_versioned.j2.yml',
                                 temp_dir,
                                 'docker-compose.yml',
                                 template='%s-docker-compose.j2.yml' % (operation,),
                                 hosts=hosts,
                                 project_name=self.project_name,
                                 base_path=self.base_path,
                                 params=self.params,
                                 api_version=self.api_version,
                                 builder_img_id=builder_img_id,
                                 config=config_yaml,
                                 env=os.environ,
                                 version=version,
                                 volumes=volumes_yaml,
                                 **context)
        options = self.DEFAULT_COMPOSE_OPTIONS.copy()

        options.update({
            u'--verbose': self.params['debug'],
            u'--file': [
                os.path.join(temp_dir,
                             'docker-compose.yml')],
            u'--project-name': 'ansible',
        })
        command_options = getattr(self, 'DEFAULT_COMPOSE_{}_OPTIONS'.format(
            compose_option.upper())).copy()
        command_options.update(extra_options)

        project = project_from_options(self.base_path + '/ansible', options)
        command = main.TopLevelCommand(project)

        return options, command_options, command
