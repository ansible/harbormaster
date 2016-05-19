# -*- coding: utf-8 -*-

from __future__ import absolute_import

import logging
import os
import yaml
import ConfigParser
import re

from .constants import SHIPIT_PATH, SHIPIT_PLAYBOOK_NAME
from .k8s_service import K8SService
from .k8s_deployment import K8SDeployment
from .k8s_route import K8SRoute
from .exceptions import ShipItException
from collections import OrderedDict


logger = logging.getLogger(__name__)


def represent_odict(dump, tag, mapping, flow_style=None):
    '''
    https://gist.github.com/miracle2k/3184458
    Like BaseRepresenter.represent_mapping, but does not issue the sort().
    '''
    value = []
    node = yaml.MappingNode(tag, value, flow_style=flow_style)
    if dump.alias_key is not None:
        dump.represented_objects[dump.alias_key] = node
    best_style = True
    if hasattr(mapping, 'items'):
        mapping = mapping.items()
    for item_key, item_value in mapping:
        node_key = dump.represent_data(item_key)
        node_value = dump.represent_data(item_value)
        if not (isinstance(node_key, yaml.ScalarNode) and not node_key.style):
            best_style = False
        if not (isinstance(node_value, yaml.ScalarNode) and not node_value.style):
            best_style = False
        value.append((node_key, node_value))
    if flow_style is None:
        if dump.default_flow_style is not None:
            node.flow_style = dump.default_flow_style
        else:
            node.flow_style = best_style
    return node


class K8SPlaybook(object):

    def __init__(self, config=None, project_name=None, project_dir=None):
        self.config = config
        self.project_name = project_name
        self.project_dir = project_dir

    def get_tasks(self):
        tasks = []
        services = K8SService(config=self.config, project_name=self.project_name).get_task()
        tasks += services

        routes = K8SRoute(config=self.config, project_name=self.project_name).get_task()
        tasks += routes

        deployments = K8SDeployment(config=self.config, project_name=self.project_name).get_task()
        tasks += deployments

        return tasks

    def build_vars(self):
        pass

    def write_deployment(self, hosts="localhost", connection="local", gather_facts=False):
        '''
        Create SHIPIT_PATH within the project dir, and within that add a deployment playbook, roles path
        and a <project_name> role.

        :param hosts: Inventory hosts
        :type hosts: str
        :param connection: Connection type
        :type hosts: str
        :param gather_facts: Control whether or not plays execute setup module.
        :type gather_facts: bool
        :return: None
        '''

        deploy_path = os.path.join(self.project_dir, SHIPIT_PATH)

        self.create_path(deploy_path)

        yaml.SafeDumper.add_representer(OrderedDict,
                                        lambda dumper, value: represent_odict(dumper, u'tag:yaml.org,2002:map', value))

        # Create tasks/main.yml
        tasks = self.get_tasks()

        # Create the playbook
        play = OrderedDict()
        play['name'] = "Deploy %s" % self.project_name
        play['hosts'] = hosts
        play['vars'] = dict(
            playbook_debug=False
        )
        if connection:
            play['connection'] = connection
        if not gather_facts:
            play['gather_facts'] = 'no'

        play['tasks'] = []
        for task in tasks:
            task['register'] = "output"
            play['tasks'].append(task)
            play['tasks'].append(dict(
                debug="var=output",
                when="playbook_debug"
            ))
        stream = yaml.safe_dump([play], default_flow_style=False)
        with open(os.path.join(deploy_path, SHIPIT_PLAYBOOK_NAME), 'w') as f:
            f.write(re.sub(r'^  - ', u'\n  - ', stream, flags=re.M))

    def update_config(self):
        # Create or update an ansible.cfg file
        config_path = os.path.join(self.project_dir, SHIPIT_PATH, 'ansible.cfg')
        hosts_path = os.path.join(self.project_dir, SHIPIT_PATH, 'hosts')
        config = ConfigParser.ConfigParser()
        if os.path.isfile(config_path):
            config.read([config_path])
        if not config.has_section('defaults'):
            config.add_section('defaults')
        module_path = os.path.join(os.path.dirname(__file__), 'modules')
        if not config.has_option('defaults', 'library'):
            config.set('defaults', 'library', module_path)
        if not config.has_option('defaults', 'inventory'):
            config.set('defaults', 'inventory', hosts_path)
        if not config.has_option('defaults', 'nocows'):
            config.set('defaults', 'nocows', 1)
        with open(config_path, 'w') as f:
            config.write(f)

    def create_inventory(self):
        hosts_path = os.path.join(self.project_dir, SHIPIT_PATH, 'hosts')
        if not os.path.isfile(hosts_path):
            with open(hosts_path, 'w') as f:
                f.write("localhost")

    @staticmethod
    def create_path(path):
        try:
            os.makedirs(path)
        except OSError:
            # ignore if path already exists
            pass
        except Exception as exc:
            raise ShipItException("Error creating %s - %s" % (path, str(exc)))




