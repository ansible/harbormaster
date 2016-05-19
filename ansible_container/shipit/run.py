# -*- coding: utf-8 -*-

from __future__ import absolute_import

import logging

from .k8s_playbook import K8SPlaybook
from .k8s_config import K8SConfig

logger = logging.getLogger(__name__)


def run_shipit(type=None, config=None, project_name=None, project_dir=None, hosts="localhost", connection="local",
               gather_facts=False, create_templates=False):

    #TODO - Create other things besides OpenShift.

    playbook = K8SPlaybook(config=config, project_name=project_name, project_dir=project_dir)
    playbook.write_deployment(hosts=hosts, connection=connection, gather_facts=gather_facts)
    playbook.update_config()
    playbook.create_inventory()

    if create_templates:
        K8SConfig(config=config, project_name=project_name, project_dir=project_dir).create_config()
