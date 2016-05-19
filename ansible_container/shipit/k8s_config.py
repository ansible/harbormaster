# -*- coding: utf-8 -*-

from __future__ import absolute_import

import logging
import os
import json

from .constants import SHIPIT_CONFIG_PATH
from .k8s_service import K8SService
from .k8s_deployment import K8SDeployment
from .k8s_route import K8SRoute
from .exceptions import ShipItException

logger = logging.getLogger(__name__)


class K8SConfig(object):

    def __init__(self, config=None, project_name=None, project_dir=None):
        self.config = config
        self.project_name = project_name
        self.project_dir = project_dir

    def create_config(self):
        dest_path = os.path.join(self.project_dir, SHIPIT_CONFIG_PATH)
        logger.debug("create config path: %s" % dest_path)
        self.create_path(dest_path)

        templates = K8SService(config=self.config, project_name=self.project_name).get_template()
        for template in templates:
            name = "%s-service.json" % template['metadata']['name']
            with open(os.path.join(dest_path, name), 'w') as f:
                f.write(json.dumps(template, indent=4))

        templates = K8SRoute(config=self.config, project_name=self.project_name).get_template()
        for template in templates:
            name = "%s.json" % template['metadata']['name']
            with open(os.path.join(dest_path, name), 'w') as f:
                f.write(json.dumps(template, indent=4))

        templates = K8SDeployment(config=self.config, project_name=self.project_name).get_template()
        for template in templates:
            name = "%s-deployment.json" % template['metadata']['name']
            with open(os.path.join(dest_path, name), 'w') as f:
                f.write(json.dumps(template, indent=4))

    @staticmethod
    def create_path(path):
        try:
            os.makedirs(path)
        except OSError:
            # ignore if path already exists
            pass
        except Exception as exc:
            raise ShipItException("Error creating %s - %s" % (path, str(exc)))




