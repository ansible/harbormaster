# -*- coding: utf-8 -*-
from __future__ import absolute_import

from .deploy import Deploy
from .base_engine import K8sBaseEngine

from container.utils.visibility import getLogger
logger = getLogger(__name__)


try:
    from openshift.helper.kubernetes import KubernetesObjectHelper, KubernetesException
except ImportError:
    raise ImportError('Use of this engine requires you "pip install \'openshift\'" first.')


class Engine(K8sBaseEngine):

    @property
    def deploy(self):
        if not self._deploy:
            self._deploy = Deploy(self.services, self.project_name, namespace_name=self.namespace_name,
                                  volumes=self.volumes)
        return self._deploy

    @property
    def k8s_client(self):
        if not self._k8s_client:
            self._k8s_client = self._client = KubernetesObjectHelper()
        return self._k8s_client

    def run_conductor(self, command, config, base_path, params, engine_name=None, volumes=None):
        engine_name = __name__.rsplit('.', 2)[-2]
        return super(Engine, self).run_conductor(command, config, base_path, params, engine_name=engine_name)

    # def _create_ks8_object(self, api_version, kind, request):
    #     name = request.get('metadata', {}).get('name')
    #     namespace = request.get('metadata', {}).get('namespace')
    #
    #     self.client.set_model(api_version, kind)
    #     k8s_obj = self.client.get_object(name, namespace)
    #     if not k8s_obj:
    #         # create when it doesn't exist
    #         try:
    #             k8s_obj = self.client.create_object(namespace, body=request)
    #         except KubernetesException as exc:
    #             raise exceptions.AnsibleContainerConductorException(
    #                 u"Error creating {0}: {1}".format(request['kind'], exc)
    #             )
    #     else:
    #         # otherwise, replace it. not idempotent, but good enough for now
    #         try:
    #             k8s_obj = self.client.replace_object(name, namespace, body=request)
    #         except KubernetesException as exc:
    #             raise exceptions.AnsibleContainerConductorException(
    #                 u"Error creating {0}: {1}".format(request['kind'], exc)
    #             )
    #     return k8s_obj
