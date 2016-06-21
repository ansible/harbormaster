# -*- coding: utf-8 -*-

from __future__ import absolute_import

import logging
import os.path
import json

from ..base_engine import BaseShipItEngine
from .deployment import Deployment
from .service import Service
from ..utils import create_path
from ..constants import SHIPIT_PATH, SHIPIT_CONFIG_PATH

logger = logging.getLogger(__name__)


class ShipItEngine(BaseShipItEngine):
    name = u'kubernetes'

    def add_options(self, subparser):
        super(ShipItEngine, self).add_options(subparser)

    def run(self):
        tasks = []
        tasks += Service(config=self.config, project_name=self.project_name).get_task()
        tasks += Deployment(config=self.config, project_name=self.project_name).get_task()
        self.create_role(tasks)
        self.create_playbook()

    def save_config(self):
        dest_path = os.path.join(self.base_path, SHIPIT_PATH, SHIPIT_CONFIG_PATH, self.name)
        create_path(dest_path)

        templates = Service(config=self.config, project_name=self.project_name).get_template()
        for template in templates:
            name = "%s-service.json" % template['metadata']['name']
            with open(os.path.join(dest_path, name), 'w') as f:
                f.write(json.dumps(template, indent=4))

        templates = Deployment(config=self.config, project_name=self.project_name).get_template()
        for template in templates:
            name = "%s-deployment.json" % template['metadata']['name']
            with open(os.path.join(dest_path, name), 'w') as f:
                f.write(json.dumps(template, indent=4))

        return dest_path



