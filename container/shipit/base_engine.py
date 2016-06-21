# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging
logger = logging.getLogger(__name__)

import os
import yaml
import re
import glob

from ..config import represent_odict
from .constants import SHIPIT_PATH, SHIPIT_PLAYBOOK_PREFIX, SHIPIT_ROLES_DIR
from collections import OrderedDict
from .utils import create_path


class BaseShipItEngine(object):
    name = None

    def __init__(self, base_path=None, project_name=None, config=None):
        self.base_path = base_path
        self.project_name = project_name
        self.config = config
        self.role_name = "%s_%s" % (self.project_name, self.name)
        self.roles_path = os.path.join(self.base_path, SHIPIT_PATH, SHIPIT_ROLES_DIR, self.role_name)

    def add_options(self, subparser):
        """
        Given an argument subparser, add to it the arguments and options
        this engine allows.

        https://docs.python.org/2/library/argparse.html#sub-commands

        :param subparser: An argparse.ArgumentSubparser
        :return: None
        """
        subparser.add_argument('--save-config', action='store_true',
                               help=u'Generate and save the %s configuration files.' % self.name,
                               dest='save_config', default=False)

        subparser.add_argument('--pull-from', action='store',
                               help=u'Name of a registry defined in container.yml from which %s should '
                                    u'pull images' % self.name,
                               dest='pull_from', default=None)

    def run(self):
        """
        Generate an Ansible role and sample playbook to deploy to the target cloud provider.

        :return:
        """
        raise NotImplementedError()

    def save_config(self):
        """
        Called when --save-config option True. Generate configuration templates and write to filesystem.

        :return: string: name of directory where config was saved
        """
        raise NotImplementedError()

    def _copy_modules(self):
        '''
        Copy cloud ansible modules to role library path.
        '''
        cls_dir = os.path.dirname(os.path.realpath(__file__))
        modules_dir = os.path.join(cls_dir, self.name, 'modules')
        library_path = os.path.join(self.roles_path, 'library')
        create_path(library_path)

        include_files = []
        for mod in glob.glob(modules_dir + '/*.py'):
            with open(mod, 'r') as mod_file:
                for line in mod_file:
                    match = re.search('#include--> ?(\w+.py)', line)
                    if match and match.groups():
                        include_files += list(match.groups())

        include_files = list(set(include_files))
        for mod in glob.glob(modules_dir + '/*.py'):
            base_file = os.path.basename(mod)
            if base_file not in include_files:
                with open(os.path.join(library_path, base_file), 'w') as new_file:
                    with open(mod, 'r') as mod_file:
                        for line in mod_file:
                            match = re.search('#include--> ?(\w+.py)', line)
                            if match and match.groups():
                                with open(os.path.join(modules_dir, match.group(1)), 'r') as inc:
                                    inc_contents = inc.read()
                                new_file.write('\n')
                                new_file.write(inc_contents)
                            else:
                                new_file.write(line)

    def create_role(self, tasks):
        '''
        Calls ansible-galaxy init to create the role directory structure and defaults.
        Creates tasks/mainy.yml with all the tasks needed to launch the app on the cluster.

        :return: None
        '''

        yaml.SafeDumper.add_representer(OrderedDict,
                                        lambda dumper, value: represent_odict(dumper, u'tag:yaml.org,2002:map', value))

        # Create tasks/main.yml
        output_tasks = []
        for task in tasks:
            task['register'] = "output"
            output_tasks.append(task)
            output_tasks.append(dict(
                debug="var=output",
                when="playbook_debug"
            ))
        stream = yaml.safe_dump(output_tasks, default_flow_style=False)
        with open(os.path.join(self.roles_path, 'tasks', 'main.yml'), 'w') as f:
            f.write(re.sub(r'^-', u'\n-', stream, flags=re.M))

        self._copy_modules()

    def create_playbook(self):
        '''
        Create a simple playbook to execute the role.

        :return: None
        '''
        play = OrderedDict()
        play['name'] = "Deploy %s to  %s" % (self.project_name, self.name)
        play['hosts'] = 'localhost'
        play['gather_facts'] = False
        play['connection'] = 'local'
        play['vars'] = dict(
            playbook_debug=False
        )
        play['roles'] = [dict(
            role=self.role_name
        )]
        playbook_name = "%s_%s.yml" % (SHIPIT_PLAYBOOK_PREFIX, self.name)
        playbook_path = os.path.join(self.base_path, SHIPIT_PATH, playbook_name)
        with open(playbook_path, 'w') as f:
            f.write(yaml.safe_dump([play], default_flow_style=False))

