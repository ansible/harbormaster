# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging
plainLogger = logging.getLogger(__name__)

import os
import subprocess

from abc import ABCMeta, abstractproperty, abstractmethod
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from six import add_metaclass, iteritems

from container import conductor_only, host_only
from container import exceptions
from container.docker.engine import Engine as DockerEngine, log_runs
from container.utils.visibility import getLogger

logger = getLogger(__name__)


@add_metaclass(ABCMeta)
class K8sBaseEngine(DockerEngine):

    # Capabilities of engine implementations
    CAP_BUILD_CONDUCTOR = False
    CAP_BUILD = False
    CAP_DEPLOY = True
    CAP_IMPORT = False
    CAP_INSTALL = False
    CAP_LOGIN = True
    CAP_PUSH = True
    CAP_RUN = True
    CAP_VERSION = False

    display_name = u'K8s'

    _k8s_client = None
    _deploy = None

    def __init__(self, project_name, services, debug=False, selinux=True, settings=None, **kwargs):
        if not settings:
            settings = {}
        k8s_namespace = settings.get('k8s_namespace', {})
        self.namespace_name = k8s_namespace.get('name', None) or project_name
        self.namespace_display_name = k8s_namespace.get('display_name')
        self.namespace_description = k8s_namespace.get('description')
        super(K8sBaseEngine, self).__init__(project_name, services, debug, selinux=selinux, **kwargs)
        logger.debug("k8s namespace", namspace=self.namespace_name, display_name=self.namespace_display_name,
                     description=self.namespace_description)
        logger.debug("Volume for k8s", volumes=self.volumes)

    @property
    @abstractproperty
    def deploy(self):
        pass

    @property
    @abstractproperty
    def k8s_client(self):
        pass

    @property
    def k8s_config_path(self):
        return os.path.normpath(os.path.expanduser('~/.kube/config'))

    @conductor_only
    def pre_deployment_setup(self, project_name, services, deployment_output_path=None, **kwargs):
        # Prior to running the playbook, install the ansible.kubernetes-modules role

        if not os.path.isdir(os.path.join(deployment_output_path, 'roles')):
            # Create roles subdirectory
            os.mkdir(os.path.join(deployment_output_path, 'roles'), 0o777)

        role_path = os.path.join(deployment_output_path, 'roles', 'ansible.kubernetes-modules')
        if deployment_output_path and not os.path.exists(role_path):
            # Install the role, if not already installed
            ansible_cmd = "ansible-galaxy -vvv install -p ./roles ansible.kubernetes-modules"
            logger.debug('Running ansible-galaxy', command=ansible_cmd, cwd=deployment_output_path)
            process = subprocess.Popen(ansible_cmd,
                                       shell=True,
                                       bufsize=1,
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT,
                                       cwd=deployment_output_path,
                                       )
            log_iter = iter(process.stdout.readline, '')
            while process.returncode is None:
                try:
                    plainLogger.info(log_iter.next().rstrip())
                except StopIteration:
                    process.wait()
                finally:
                    process.poll()

            if process.returncode:
                raise exceptions.AnsibleContainerDeployException(u"Failed to install ansible.kubernetes-modules role")

    @log_runs
    @host_only
    @abstractmethod
    def run_conductor(self, command, config, base_path, params, engine_name=None, volumes=None):
        volumes = {}
        k8s_auth = config.get('settings', {}).get('k8s_auth', {})

        # Set a value for config_file
        if not k8s_auth.get('config_file'):
            k8s_auth['config_file'] = self.k8s_config_path
        # Verify the config_file exists
        if not os.path.isfile(k8s_auth['config_file']):
            raise exceptions.AnsibleContainerConfigException("Unable to locate {}".format(k8s_auth['config_file']))
        # Mount the config_file to the conductor
        volumes[k8s_auth['config_file']] = {'bind': '/root/.kube/config', 'mode': 'ro'}

        if k8s_auth:
            # check if we need to mount any other paths
            path_params = ['config_file', 'ssl_ca_cert', 'cert_file', 'key_file']
            for param in path_params:
                if k8s_auth.get(param, None) is not None:
                    volumes[k8s_auth[param]] = {'bind': k8s_auth[param], 'mode': 'ro'}

        # Add k8s_auth settings as environment variables in the conductor
        if not params.get('with_variables'):
            params['with_variables'] = []
        for key in k8s_auth:
            if key == 'config_file':
                params['with_variables'].append("K8S_AUTH_KUBECONFIG={}".format(k8s_auth[key]))
            else:
                params['with_variables'].append("K8S_AUTH_{}={}".format(key.upper(), k8s_auth[key]))
        return super(K8sBaseEngine, self).run_conductor(command, config, base_path, params,
                                                        engine_name=engine_name,
                                                        volumes=volumes)

    @conductor_only
    def generate_orchestration_playbook(self, url=None, namespace=None, settings=None, repository_prefix=None,
                                        pull_from_url=None, tag=None, vault_files=None, **kwargs):
        """
        Generate an Ansible playbook to orchestrate services.
        :param url: registry URL where images were pushed.
        :param namespace: registry namespace
        :param repository_prefix: prefix to use for the image name
        :param settings: settings dict from container.yml
        :param pull_from_url: if url to pull from is different than url
        :return: playbook dict
        """

        def _update_service(service_name, service_config):
            if url and namespace:
                # Reference previously pushed image
                image_id = self.get_latest_image_id_for_service(service_name)
                if not image_id:
                    raise exceptions.AnsibleContainerConductorException(
                        u"Unable to get image ID for service {}. Did you forget to run "
                        u"`ansible-container build`?".format(service_name)
                    )
                image_tag = tag or self.get_build_stamp_for_image(image_id)
                if repository_prefix:
                    image_name = "{}-{}".format(repository_prefix, service_name)
                elif repository_prefix is None:
                    image_name = "{}-{}".format(self.project_name, service_name)
                else:
                    image_name = service_name
                repository = "{}/{}".format(namespace, image_name)
                image_name = "{}:{}".format(repository, image_tag)
                pull_url = pull_from_url if pull_from_url else url
                service_config['image'] = "{}/{}".format(pull_url.rstrip('/'), image_name)
            else:
                # We're using a local image, so check that the image was built
                image = self.get_latest_image_for_service(service_name)
                if image is None:
                    raise exceptions.AnsibleContainerConductorException(
                        u"No image found for service {}, make sure you've run `ansible-container "
                        u"build`".format(service_name)
                    )
                service_config['image'] = image.tags[0]

        for service_name, service in iteritems(self.services):
            # set the image property of each container
            if service.get('containers'):
                for container in service['containers']:
                    if container.get('roles'):
                        container_service_name = "{}-{}".format(service_name, container['container_name'])
                        _update_service(container_service_name, container)
                    else:
                        container['image'] = container['from']
            elif service.get('roles'):
                _update_service(service_name, service)
            else:
                service['image'] = service['from']

        play = CommentedMap()
        play['name'] = u'Manage the lifecycle of {} on {}'.format(self.project_name, self.display_name)
        play['hosts'] = 'localhost'
        play['gather_facts'] = 'no'
        play['connection'] = 'local'
        play['roles'] = CommentedSeq()
        play['vars_files'] = CommentedSeq()
        play['tasks'] = CommentedSeq()
        role = CommentedMap([
            ('role', 'ansible.kubernetes-modules')
        ])
        if vault_files:
            play['vars_files'].extend(vault_files)
        play['roles'].append(role)
        play.yaml_set_comment_before_after_key(
            'roles', before='Include Ansible Kubernetes and OpenShift modules', indent=4)
        play.yaml_set_comment_before_after_key('tasks', before='Tasks for setting the application state. '
                                               'Valid tags include: start, stop, restart, destroy', indent=4)
        play['tasks'].append(self.deploy.get_namespace_task(state='present', tags=['start']))
        play['tasks'].append(self.deploy.get_namespace_task(state='absent', tags=['destroy']))
        play['tasks'].extend(self.deploy.get_secret_tasks(tags=['start']))
        play['tasks'].extend(self.deploy.get_service_tasks(tags=['start']))
        play['tasks'].extend(self.deploy.get_deployment_tasks(engine_state='stop', tags=['stop', 'restart']))
        play['tasks'].extend(self.deploy.get_deployment_tasks(tags=['start', 'restart']))
        play['tasks'].extend(self.deploy.get_pvc_tasks(tags=['start']))

        playbook = CommentedSeq()
        playbook.append(play)

        logger.debug(u'Created playbook to run project', playbook=playbook)
        return playbook
