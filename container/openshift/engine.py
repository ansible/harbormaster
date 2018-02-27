# -*- coding: utf-8 -*-
from __future__ import absolute_import

from .deploy import Deploy
from ..k8s.base_engine import K8sBaseEngine

from container import conductor_only, __version__

from container.utils.visibility import getLogger
logger = getLogger(__name__)


try:
    from openshift.helper.openshift import OpenShiftObjectHelper, OpenShiftException
except ImportError:
    raise ImportError(
        u'You must install Ansible Container with OpenShift support. '
        u'Try:\npip install ansible-container[openshift]==%s' % (
        __version__
    ))

class Engine(K8sBaseEngine):

    display_name = u'OpenShift\u2122'

    @property
    def deploy(self):
        if not self._deploy:
            self._deploy = Deploy(self.services, self.project_name,
                                  volumes=self.volumes,
                                  secrets=self.secrets,
                                  namespace_name=self.namespace_name,
                                  namespace_description=self.namespace_description,
                                  namespace_display_name=self.namespace_display_name)
        return self._deploy

    @property
    def k8s_client(self):
        if not self._k8s_client:
            self._k8s_client = self._client = OpenShiftObjectHelper()
        return self._k8s_client

    def run_conductor(self, command, config, base_path, params, engine_name=None, volumes=None):
        engine_name = __name__.rsplit('.', 2)[-2]
        return super(Engine, self).run_conductor(command, config, base_path, params, engine_name=engine_name)

    @conductor_only
    def generate_orchestration_playbook(self, url=None, namespace=None, local_images=True, **kwargs):
        playbook = super(Engine, self).generate_orchestration_playbook(url=url,
                                                                       namespace=namespace,
                                                                       local_images=local_images,
                                                                       **kwargs)
        routes = self.deploy.get_route_tasks(tags=['start'])
        if routes:
            playbook[0]['tasks'].extend(routes)
        return playbook
