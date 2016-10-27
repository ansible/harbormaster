# -*- coding: utf-8 -*-

from __future__ import absolute_import

from compose.cli.command import project_from_options
from compose.cli import main
import logging
import os.path
import yaml

from ..base_engine import BaseShipItEngine
from .deployment import Deployment
from .route import Route
from .service import Service
from ..utils import create_path
from ..constants import SHIPIT_PATH, SHIPIT_CONFIG_PATH
from ...utils import jinja_render_to_temp
from ...temp import MakeTempDir as make_temp_dir
from ...docker.engine import Engine

logger = logging.getLogger(__name__)


class ShipItEngine(BaseShipItEngine):
    name = u'openshift'
    builder_container_img = 'ansible-container-builder'
    builder_container_img_tag = '0.2-kompose-v0.1.0'

    def add_options(self, subparser):
        super(ShipItEngine, self).add_options(subparser)

    def run(self):
        tasks = []
        tasks += Service(config=self.config, project_name=self.project_name).get_task()
        tasks += Route(config=self.config, project_name=self.project_name).get_task()
        tasks += Deployment(config=self.config, project_name=self.project_name).get_task()
        self.init_role()
        self.create_role(tasks)
        self.create_playbook()

    def save_config(self):
        dest_path = os.path.join(self.base_path, SHIPIT_PATH, SHIPIT_CONFIG_PATH, self.name)
        create_path(dest_path)

        with make_temp_dir() as temp_dir:
            with open(os.path.join(temp_dir, 'docker-compose.yml'), 'w') as f:
                f.write(yaml.safe_dump(self.config.get('services')))

            jinja_render_to_temp('shipit-kompose-docker-compose.j2.yml',
                                 temp_dir,
                                 'shipit-kompose-compose.yml',
                                 builder_img_id="containscafeine/{}:{}".format(
                                     self.builder_container_img,
                                     self.builder_container_img_tag),
                                 host_dir=temp_dir,
                                 is_openshift=True)

            options = Engine.DEFAULT_COMPOSE_OPTIONS.copy()

            options.update({
                u'--file': [
                    os.path.join(temp_dir,
                                 'shipit-kompose-compose.yml')],
                u'--project-name': 'ansible',
            })

            command_options = Engine.DEFAULT_COMPOSE_UP_OPTIONS.copy()

            project = project_from_options(self.base_path + '/ansible', options)
            command = main.TopLevelCommand(project)

            options.update({u'COMMAND': 'up'})

            command.up(command_options)

            with open(os.path.join(temp_dir, 'artifacts.yml'), 'r') as f:
                artifacts = f.read()

            with open(os.path.join(dest_path, 'deployment_artifacts.yml'),
                      'w') as f:
                f.write(artifacts)

        return dest_path



