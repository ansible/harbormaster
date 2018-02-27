# -*- coding: utf-8 -*-
from __future__ import absolute_import

from .deploy import Deploy
from .base_engine import K8sBaseEngine
import container

from container.utils.visibility import getLogger
logger = getLogger(__name__)


try:
    from openshift.helper.kubernetes import KubernetesObjectHelper, KubernetesException
except ImportError:
    raise ImportError(
        u'You must install Ansible Container with Kubernetes support. '
        u'Try:\npip install ansible-container[k8s]==%s' % (
        container.__version__
    ))


class Engine(K8sBaseEngine):

    @property
    def deploy(self):
        if not self._deploy:
            self._deploy = Deploy(self.services, self.project_name, namespace_name=self.namespace_name,
                                  volumes=self.volumes, secrets=self.secrets)
        return self._deploy

    @property
    def k8s_client(self):
        if not self._k8s_client:
            self._k8s_client = self._client = KubernetesObjectHelper()
        return self._k8s_client

    def run_conductor(self, command, config, base_path, params, engine_name=None, volumes=None):
        engine_name = __name__.rsplit('.', 2)[-2]
        return super(Engine, self).run_conductor(command, config, base_path, params, engine_name=engine_name)

