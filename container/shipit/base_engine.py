# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging
logger = logging.getLogger(__name__)

import os
import yaml
import re
import glob

from datetime import datetime

from .constants import SHIPIT_PATH, SHIPIT_PLAYBOOK_PREFIX, SHIPIT_ROLES_DIR
from collections import OrderedDict
from .utils import create_path, represent_odict
from ..utils import jinja_render_to_temp


class BaseShipItObject(object):
    def __init__(self, config=None, project_name=None):
        self.project_name = project_name
        self.config = config

    def get_template(self):
        return self._get_template_or_task(request_type="config")

    def get_task(self):
        return self._get_template_or_task(request_type="task")

    def _get_template_or_task(self, request_type="task"):
        '''
        Read the container.yml configuration, and for each service create a configuration template or
        playbook task.

        :return: list of configuration templates or playbook tasks
        '''
        raise NotImplementedError()

    def _create(self, name, request_type, service):
        '''
        Generate a configuration template or playbook task.
        :param request_type:
        '''
        raise NotImplementedError()


class BaseShipItEngine(object):
    name = None

    def __init__(self, base_path=None, project_name=None, config=None):
        self.base_path = base_path
        self.project_name = project_name
        self.config = config
        self.role_name = "%s-%s" % (self.project_name, self.name)
        self.roles_path = os.path.join(self.base_path, SHIPIT_PATH, SHIPIT_ROLES_DIR, self.role_name)

    def add_options(self, parser):
        """
        Given an argument subparser, add to it the arguments and options
        this engine allows.

        https://docs.python.org/2/library/argparse.html#sub-commands

        :param subparser: An argparse.ArgumentSubparser
        :return: None
        """
        parser.add_argument('--save-config', action='store_true',
                            help=(u'Generate and save the %s configuration files in '
                                  u'ansible/shipit_config/kubernetes.' % self.name),
                            dest='save_config', default=False)

        parser.add_argument('--tag', action='store',
                            help=(u'Name of a tag to pull down'),
                            dest='tag', default=None)

        egroup = parser.add_mutually_exclusive_group()
        egroup.add_argument('--pull-from', action='store',
                            help=u'Name of a registry defined in container.yml or the actual URL the cluster will '
                                 u'use to pull images. If passing a URL, an example would be: '
                                 u'"registry.example.com:5000/myproject"',
                            dest='pull_from', default=None)

        egroup.add_argument('--local-images', action='store_true',
                            help=u'Images can be accessed from the Docker daemon',
                            dest='local_images', default=False)

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
        logger.debug("Copying modules from %s to %s" % (modules_dir, library_path))
        create_path(library_path)

        include_files = set()
        for mod in glob.glob(modules_dir + '/*.py'):
            with open(mod, 'r') as mod_file:
                for line in mod_file:
                    match = re.search('#include--> ?(\w+.py)', line)
                    if match and match.groups():
                        include_files.update(match.groups())

        for mod in glob.glob(modules_dir + '/*.py'):
            base_file = os.path.basename(mod)
            if base_file not in include_files and not base_file.endswith('__init__.py'):
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

    def init_role(self):
        '''
        If it does not exist, create the role directory and template in the initial files.
        If it does, backup anything that we plan to overwrite.

        :return:
        '''
        # Init the role directory without overwriting any existing files.
        logger.debug("Creating role path %s" % self.roles_path)
        create_path(self.roles_path)

        shipit_role_paths = {
            u'base': [u'README.j2', u'travis.j2.yml'],
            u'defaults': [u'defaults.j2.yml'],
            u'meta': [u'meta.j2.yml'],
            u'test': [u'test.j2.yml', u'travis.j2.yml'],
            u'tasks': [],
        }

        context = {
            u'role_name': self.role_name,
            u'project_name': self.project_name,
            u'shipit_engine_name': self.name
        }

        for path, templates in shipit_role_paths.items():
            role_dir = os.path.join(self.roles_path, path if path != 'base' else '')
            if path != 'base':
                create_path(role_dir)
            for template in templates:
                target_name = template.replace('.j2', '')
                if target_name.startswith('travis'):
                    target_name = '.' + target_name
                if target_name.startswith('defaults') or target_name.startswith('meta'):
                    target_name = 'main.yml'
                if not os.path.exists(os.path.join(role_dir, target_name)):
                    logger.debug("Rendering template for %s/%s" % (path, template))
                    jinja_render_to_temp('shipit_role/%s' % template,
                                         role_dir,
                                         target_name,
                                         **context)

        # if tasks/main.yml exists, back it up
        now = datetime.today().strftime('%y%m%d%H%M%S')
        tasks_file = os.path.join(self.roles_path, 'tasks', 'main.yml')
        new_tasks_file = os.path.join(self.roles_path, 'tasks', 'main_%s.yml' % now)

        if os.path.exists(tasks_file):
            logger.debug("Backing up tasks/main.yml to main_%s.yml" % now)
            os.rename(tasks_file, new_tasks_file)

        #TODO: limit the number of backups?

    def create_role(self, tasks):
        '''
        Creates tasks/main.yml with all the deployment tasks, and copy modules into the library dir.

        :param tasks: dict of playbook tasks to be rendered in yaml
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

        # Copy ansible modules to library path
        self._copy_modules()

    def create_playbook(self):
        '''
        Create a simple playbook to execute the role. Will only create the playbook if one
        does not exist.

        :return: None
        '''
        playbook_name = "%s-%s.yml" % (SHIPIT_PLAYBOOK_PREFIX, self.name)
        playbook_path = os.path.join(self.base_path, SHIPIT_PATH, playbook_name)
        if not os.path.exists(playbook_path):
            logger.debug('Creating the sample playbook')
            play = OrderedDict()
            play['name'] = "Deploy %s to  %s" % (self.project_name, self.name)
            play['hosts'] = 'localhost'
            play['gather_facts'] = False
            play['connection'] = 'local'
            play['roles'] = []
            role = OrderedDict()
            role['role'] = self.role_name
            role['playbook_debug'] = False 
            play['roles'].append(role)
            with open(playbook_path, 'w') as f:
                f.write(yaml.safe_dump([play], default_flow_style=False))

