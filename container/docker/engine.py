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
from compose.cli.command import project_from_options
from compose.cli import main
from yaml import dump as yaml_dump

from ..exceptions import (AnsibleContainerNotInitializedException,
                          AnsibleContainerNoAuthenticationProvidedException,
                          AnsibleContainerDockerConfigFileException,
                          AnsibleContainerDockerLoginException)

from ..engine import BaseEngine, REMOVE_HTTP
from ..utils import *
from .. import __version__ as release_version
from .utils import *

if not os.environ.get('DOCKER_HOST'):
    logger.warning('No DOCKER_HOST environment variable found. Assuming UNIX '
                   'socket at /var/run/docker.sock')


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
        return self.config.get('services', {}).keys()

    def hosts_touched_by_playbook(self):
        """
        List all hosts touched by the execution of the build playbook.

        :return: list of strings
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
                lines_minus_builder_host = [line.rsplit('|', 1)[1] for line
                                            in lines if '|' in line]
                host_lines = [line for line in lines_minus_builder_host
                              if line.startswith('       ')]
                self._orchestrated_hosts = list(set([line.strip() for line in host_lines]))
        return self._orchestrated_hosts

    def build_buildcontainer_image(self):
        """
        Build in the container engine the builder container

        :return: generator of strings
        """
        assert_initialized(self.base_path, playbook=self.playbook)
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

            tarball.add(os.path.join(jinja_template_path(), 'builder.sh'),
                        arcname='builder.sh')
            tarball.add(os.path.join(jinja_template_path(), 'ansible-container-inventory.py'),
                        arcname='ansible-container-inventory.py')
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

    def get_config_for_shipit(self, pull_from=None, url=None, namespace=None):
        '''
        Retrieve the configuration needed to run the shipit command

        :param pull_from: the exact registry URL to use
        :param url: registry url. required, if pull_from not provided.
        :param namespace: path to append to the url. required if pull_from not provided.
        :return: config dict
        '''
        config = get_config(self.base_path, var_file=self.var_file)
        client = self.get_client()

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
                service_config.update(
                    dict(
                        image='%s/%s-%s:%s' % (image_path, self.project_name, host, image_buildstamp)
                    )
                )
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

    def orchestrate_galaxy_extra_args(self):
        """
        Provide extra arguments to provide the orchestrator during galaxy calls.

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

        options.update({u'COMMAND': 'stop'})

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

    def _fix_volumes(self, service_name, service_config):
        # If there are volumes defined for this host, we need to create the
        # volume if one doesn't already exist.
        client = self.get_client()
        for volume in service_config.get('volumes', []):
            if ':' not in volume:
                # This is an unnamed volume. We have to handle making this
                # volume with a predictable name.
                volume_name = '%s-%s-%s' % (self.project_name,
                                            service_name,
                                            volume.replace('/', '_'))
                try:
                    client.inspect_volume(name=volume_name)
                except docker_errors.NotFound, e:
                    # We need to create this volume
                    client.create_volume(name=volume_name, driver='local')
                service_config['volumes'].remove(volume)
                service_config['volumes'].append('%s:%s' % (volume_name, volume))

    def get_config_for_build(self):
        compose_config = config_to_compose(self.config)
        orchestrated_hosts = self.hosts_touched_by_playbook()
        logger.debug('Orchestrated hosts: %s', orchestrated_hosts)
        for service, service_config in compose_config.items():
            if service in orchestrated_hosts:
                logger.debug('Setting %s to sleep', service)
                service_config.update(
                    dict(
                        user='root',
                        working_dir='/',
                        command='sh -c "while true; do sleep 1; done"',
                        entrypoint=[]
                    )
                )
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
            self._fix_volumes(service, service_config)
        return compose_config

    def get_config_for_run(self):
        if not self.params['production']:
            self.config.set_env('dev')
        compose_config = config_to_compose(self.config)
        orchestrated_hosts = self.hosts_touched_by_playbook()
        for service, service_config in compose_config.items():
            if service in orchestrated_hosts:
                service_config.update(
                    dict(
                        image='%s-%s:latest' % (self.project_name, service)
                    )
                )
            self._fix_volumes(service, service_config)
        return compose_config

    def get_config_for_stop(self):
        compose_config = config_to_compose(self.config)
        return compose_config

    def get_config_for_listhosts(self):
        compose_config = config_to_compose(self.config)
        for service, service_config in compose_config.items():
            service_config.update(
                dict(
                    user='root',
                    working_dir='/',
                    command='sh -c "while true; do sleep 1; done"',
                    entrypoint=[]
                )
            )
        return compose_config

    def get_config_for_galaxy(self):
        compose_config = config_to_compose(self.config)
        for service, service_config in compose_config.items():
            service_config.update(
                dict(
                    command='echo "Started"'
                )
            )
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
        if isinstance(self.config['services'][host].get('command'), list):
            cmd = ' '.join(self.config['services'][host]['command'])
        image_config = dict(
            USER=self.config['services'][host].get('user', 'root'),
            WORKDIR=self.config['services'][host].get('working_dir', '/'),
            CMD=cmd
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
                          message='Built using Ansible Container',
                          changes=u'\n'.join(
                              [u'%s %s' % (k, unicode(v))
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
                u'Please provide login credentials for registry %s.' % url)
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

        if config['auths'][url] != encoded_credentials:
            config['auths'][url] = encoded_credentials
            self.write_config(path, config)

    @staticmethod
    def write_config(path, config):
        try:
            json.dump(config, open(path, "w"), indent=5, sort_keys=True)
        except Exception as exc:
            raise AnsibleContainerDockerConfigFileException("Failed to write docker registry config to %s - %s" %
                                                            (path, str(exc)))

    def push_latest_image(self, host, url=None, namespace=None):
        '''
        :param host: The host in the container.yml to push
        :parm url: URL of the registry to which images will be pushed
        :param namespace: namespace to append to the URL
        :return: None
        '''
        client = self.get_client()
        image_id, image_buildstamp = get_latest_image_for(self.project_name,
                                                          host, client)

        repository = "%s/%s-%s" % (namespace, self.project_name, host)
        if url != self.default_registry_url:
            url = REMOVE_HTTP.sub('', url)
            repository = "%s/%s" % (re.sub('/$', '', url), repository)

        logger.info('Tagging %s' % repository)
        client.tag(image_id, repository, tag=image_buildstamp)

        logger.info('Pushing %s:%s...' % (repository, image_buildstamp))
        stream = client.push(repository,
                             tag=image_buildstamp,
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
            self._client = docker.AutoVersionClient(**client_kwargs)
            self.api_version = self._client.version()['ApiVersion']
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
        config_yaml = yaml_dump(config)
        logger.debug('Config YAML is')
        logger.debug(config_yaml)
        with_volumes = self.params.get('with_volumes')
        with_variables = self.params.get('with_variables')
        logger.debug("with volumes: {0}\n with_variables: {1}".format(','.join(with_volumes),
                                                                      ','.join(with_variables)))
        jinja_render_to_temp('%s-docker-compose.j2.yml' % (operation,),
                             temp_dir,
                             'docker-compose.yml',
                             hosts=self.all_hosts_in_orchestration(),
                             project_name=self.project_name,
                             base_path=self.base_path,
                             params=self.params,
                             api_version=self.api_version,
                             builder_img_id=builder_img_id,
                             config=config_yaml,
                             env=os.environ,
                             playbook=self.playbook,
                             with_volumes=with_volumes,
                             with_variables=with_variables,
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
