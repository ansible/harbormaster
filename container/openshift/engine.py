# -*- coding: utf-8 -*-
from __future__ import absolute_import

from .deploy import Deploy
from ..k8s.base_engine import K8sBaseEngine

from container import conductor_only

from container.utils.visibility import getLogger
logger = getLogger(__name__)


try:
    from openshift.helper.openshift import OpenShiftObjectHelper, OpenShiftException
except ImportError:
    raise ImportError('Use of this engine requires you "pip install \'openshift\'" first.')


class Engine(K8sBaseEngine):

    display_name = u'OpenShift'

    @property
    def deploy(self):
        if not self._deploy:
            self._deploy = Deploy(self.services, self.project_name,
                                  volumes=self.volumes,
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
        playbook = self._generate_orchestration_playbook(url=url,
                                                         namespace=namespace,
                                                         local_images=local_images,
                                                         state='present',
                                                         **kwargs)
        routes = self.deploy.get_route_tasks()
        if routes:
            playbook[0]['tasks'].extend(routes)
        return playbook
