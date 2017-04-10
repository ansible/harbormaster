# -*- coding: utf-8 -*-
from __future__ import absolute_import

from .deploy import Deploy
from ..k8s.base_engine import K8sBaseEngine

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
        logger.debug('HERE!!')
        if not self._deploy:
            self._deploy = Deploy(self.services, self.project_name,
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
        super(Engine, self).run_conductor(command, config, base_path, params, engine_name=engine_name)
