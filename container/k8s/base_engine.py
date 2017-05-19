# -*- coding: utf-8 -*-
from __future__ import absolute_import

import os
import re
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from six import add_metaclass

from abc import ABCMeta, abstractproperty, abstractmethod

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

    def __init__(self, project_name, services, debug=False, selinux=True, **kwargs):
        k8s_namespace = kwargs.pop('k8s_namespace', {})
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

    @log_runs
    @host_only
    @abstractmethod
    def run_conductor(self, command, config, base_path, params, engine_name=None, volumes=None):
        volumes = {}
        k8s_auth = config.get('settings', {}).get('k8s_auth', {})
        if not k8s_auth.get('config_file') and os.path.isfile(self.k8s_config_path):
            # mount default config file
            volumes[self.k8s_config_path] = {'bind': '/root/.kube/config', 'mode': 'ro'}
        if k8s_auth:
            # check if we need to mount any other paths
            path_params = ['config_file', 'ssl_ca_cert', 'cert_file', 'key_file']
            for param in path_params:
                if k8s_auth.get(param, None) is not None:
                    volumes[k8s_auth[param]] = {'bind': k8s_auth[param], 'mode': 'ro'}

        return super(K8sBaseEngine, self).run_conductor(command, config, base_path, params,
                                                        engine_name=engine_name,
                                                        volumes=volumes)

    @conductor_only
    def generate_orchestration_playbook(self, url=None, namespace=None, **kwargs):
        """
        Generate an Ansible playbook to orchestrate services.
        :param url: registry URL where images will be pulled from
        :param namespace: registry namespace
        :return: playbook dict
        """
        for service_name, service_config in self.services.iteritems():
            if service_config.get('roles'):
                if url and namespace:
                    # Reference previously pushed image
                    self.services[service_name][u'image'] = '{}/{}/{}'.format(re.sub(r'/$', '', url), namespace,
                                                                              self.image_name_for_service(service_name))
                else:
                    # We're using a local image, so check that the image was built
                    image = self.get_latest_image_for_service(service_name)
                    if image is None:
                        raise exceptions.AnsibleContainerConductorException(
                            u"No image found for service {}, make sure you've run `ansible-container "
                            u"build`".format(service_name)
                        )
                    self.services[service_name][u'image'] = image.tags[0]
            else:
                # Not a built image
                self.services[service_name][u'image'] = service_config['from']

        if kwargs.get('k8s_auth'):
            self.k8s_client.set_authorization(kwargs['auth'])

        play = CommentedMap()
        play['name'] = u'Manage the lifecycle of {} on {}'.format(self.project_name, self.display_name)
        play['hosts'] = 'localhost'
        play['gather_facts'] = 'no'
        play['connection'] = 'local'
        play['roles'] = CommentedSeq()
        play['tasks'] = CommentedSeq()
        role = CommentedMap([
            ('role', 'kubernetes-modules')
        ])
        play['roles'].append(role)
        play.yaml_set_comment_before_after_key(
            'roles', before='Include Ansible Kubernetes and OpenShift modules', indent=4)
        play.yaml_set_comment_before_after_key('tasks', before='Tasks for setting the application state. '
                                               'Valid tags include: start, stop, restart, destroy', indent=4)
        play['tasks'].append(self.deploy.get_namespace_task(state='present', tags=['start']))
        play['tasks'].append(self.deploy.get_namespace_task(state='absent', tags=['destroy']))
        play['tasks'].extend(self.deploy.get_service_tasks(tags=['start']))
        play['tasks'].extend(self.deploy.get_deployment_tasks(engine_state='stop', tags=['stop', 'restart']))
        play['tasks'].extend(self.deploy.get_deployment_tasks(tags=['start', 'restart']))
        play['tasks'].extend(self.deploy.get_pvc_tasks(tags=['start']))

        playbook = CommentedSeq()
        playbook.append(play)

        logger.debug(u'Created playbook to run project', playbook=playbook)
        return playbook
