# -*- coding: utf-8 -*-

from __future__ import absolute_import

import logging
import os.path
import json

from ..base_engine import BaseShipItEngine
from .deployment import Deployment
from .role import ShipItRole
from .service import Service
from ..utils import create_config_output_path

logger = logging.getLogger(__name__)


class ShipItEngine(BaseShipItEngine):

    def add_options(self, subparser):
        subparser.add_argument('--save-config', action='store_true',
                               help=u'Generate and save the Kubernetes configuration files.',
                               dest='save_config', default=False)

    def run(self, **kwargs):
        config = kwargs.pop('config')
        project_name = kwargs.pop('project_name')
        project_dir = kwargs.pop('project_dir')

        role = ShipItRole(config=config, project_name=project_name, project_dir=project_dir, engine='openshift')
        role.create_role()
        role.create_playbook()

    def save_config(self, **kwargs):
        config = kwargs.pop('config')
        project_name = kwargs.pop('project_name')
        project_dir = kwargs.pop('project_dir')
        dest_path = create_config_output_path(project_dir)

        templates = Service(config=config, project_name=project_name).get_template()
        for template in templates:
            name = "%s-service.json" % template['metadata']['name']
            with open(os.path.join(dest_path, name), 'w') as f:
                f.write(json.dumps(template, indent=4))

        templates = Route(config=config, project_name=project_name).get_template()
        for template in templates:
            name = "%s.json" % template['metadata']['name']
            with open(os.path.join(dest_path, name), 'w') as f:
                f.write(json.dumps(template, indent=4))

        templates = Deployment(config=config, project_name=project_name).get_template()
        for template in templates:
            name = "%s-deployment.json" % template['metadata']['name']
            with open(os.path.join(dest_path, name), 'w') as f:
                f.write(json.dumps(template, indent=4))



