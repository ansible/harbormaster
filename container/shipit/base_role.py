
# -*- coding: utf-8 -*-
from __future__ import absolute_import

import os
import shlex
import yaml
import re
import subprocess
import select
import logging
import glob

from .constants import SHIPIT_PATH, SHIPIT_PLAYBOOK_PREFIX, SHIPIT_ROLES_DIR
from container.exceptions import AnsibleContainerShipItException
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


def run_command(args):
    '''
    Execute a command, returns rc, stdout, and stderr.

    :param args: Command to execute.
    '''

    if isinstance(args, basestring):
        if isinstance(args, unicode):
            args = args.encode('utf-8')
        args = shlex.split(args)
    else:
        raise AnsibleContainerShipItException("Argument 'args' to run_command must be list or string")

    args = [os.path.expandvars(os.path.expanduser(x)) for x in args if x is not None]

    st_in = None

    # Clean out python paths set by ziploader
    if 'PYTHONPATH' in os.environ:
        pypaths = os.environ['PYTHONPATH'].split(':')
        pypaths = [x for x in pypaths \
                    if not x.endswith('/ansible_modlib.zip') \
                    and not x.endswith('/debug_dir')]
        os.environ['PYTHONPATH'] = ':'.join(pypaths)

    kwargs = dict(
        executable=None,
        shell=False,
        close_fds=True,
        stdin=st_in,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # store the pwd
    prev_dir = os.getcwd()

    try:
        cmd = subprocess.Popen(args, **kwargs)
        stdout = ''
        stderr = ''
        rpipes = [cmd.stdout, cmd.stderr]
        while True:
            rfd, wfd, efd = select.select(rpipes, [], rpipes, 1)
            if cmd.stdout in rfd:
                dat = os.read(cmd.stdout.fileno(), 9000)
                stdout += dat
                if dat == '':
                    rpipes.remove(cmd.stdout)
            if cmd.stderr in rfd:
                dat = os.read(cmd.stderr.fileno(), 9000)
                stderr += dat
                if dat == '':
                    rpipes.remove(cmd.stderr)
            # only break out if no pipes are left to read or
            # the pipes are completely read and
            # the process is terminated
            if (not rpipes or not rfd) and cmd.poll() is not None:
                break
            # No pipes are left to read but process is not yet terminated
            # Only then it is safe to wait for the process to be finished
            # NOTE: Actually cmd.poll() is always None here if rpipes is empty
            elif not rpipes and cmd.poll() is not None:
                cmd.wait()
                # The process is terminated. Since no pipes to read from are
                # left, there is no need to call select() again.
                break
        cmd.stdout.close()
        cmd.stderr.close()
        rc = cmd.returncode
    except Exception:
        raise

    os.chdir(prev_dir)
    return rc, stdout, stderr


class BaseShipItRole(object):

    def __init__(self, config=None, project_name=None, project_dir=None, engine=None):
        self.config = config
        self.project_name = project_name
        self.project_dir = project_dir
        self.engine = engine
        self.role_name =  "%s_%s" % (self.project_name, engine)
        self.roles_path = os.path.join(self.project_dir, SHIPIT_PATH, SHIPIT_ROLES_DIR, self.role_name)

    def _create_path(self, path):
        try:
            os.makedirs(path)
        except OSError:
            pass
        except Exception as exc:
            raise Exception("Error creating %s - %s" % (path, str(exc)))

    def _get_tasks(self):
        '''
        Return tasks for tasks/main.yml

        :return: list of tasks
        '''

        raise NotImplementedError()

    def _copy_modules(self):
        '''
        Copy cloud ansible modules to role library path.
        '''
        cls_dir = os.path.dirname(os.path.realpath(__file__))
        modules_dir = os.path.join(cls_dir, self.engine, 'modules')
        library_path = os.path.join(self.roles_path, 'library')
        self._create_path(library_path)

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

    def create_role(self):
        '''
        Calls ansible-galaxy init to create the role directory structure and defaults.
        Creates tasks/mainy.yml with all the tasks needed to launch the app on the cluster.

        :return: None
        '''

        yaml.SafeDumper.add_representer(OrderedDict,
                                        lambda dumper, value: represent_odict(dumper, u'tag:yaml.org,2002:map', value))

        # Create tasks/main.yml
        output_tasks = []
        tasks = self._get_tasks()
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
        play['name'] = "Deploy %s to  %s" % (self.project_name, self.engine)
        play['hosts'] = 'localhost'
        play['gather_facts'] = False
        play['connection'] = 'local'
        play['vars'] = dict(
            playbook_debug=False
        )
        play['roles'] = [dict(
            role=self.role_name
        )]
        playbook_name = "%s_%s.yml" % (SHIPIT_PLAYBOOK_PREFIX, self.engine)
        playbook_path = os.path.join(self.project_dir, SHIPIT_PATH, playbook_name)
        with open(playbook_path, 'w') as f:
            f.write(yaml.safe_dump([play], default_flow_style=False))

    # def update_config(self):
    #     # Create or update an ansible.cfg file
    #     config_path = os.path.join(self.project_dir, SHIPIT_PATH, 'ansible.cfg')
    #     hosts_path = os.path.join(self.project_dir, SHIPIT_PATH, 'hosts')
    #     config = ConfigParser.ConfigParser()
    #     if os.path.isfile(config_path):
    #         config.read([config_path])
    #     if not config.has_section('defaults'):
    #         config.add_section('defaults')
    #     module_path = os.path.join(os.path.dirname(__file__), 'modules')
    #     if not config.has_option('defaults', 'library'):
    #         config.set('defaults', 'library', module_path)
    #     if not config.has_option('defaults', 'inventory'):
    #         config.set('defaults', 'inventory', hosts_path)
    #     if not config.has_option('defaults', 'nocows'):
    #         config.set('defaults', 'nocows', 1)
    #     with open(config_path, 'w') as f:
    #         config.write(f)

    # def create_inventory(self):
    #     hosts_path = os.path.join(self.project_dir, SHIPIT_PATH, 'hosts')
    #     if not os.path.isfile(hosts_path):
    #         with open(hosts_path, 'w') as f:
    #             f.write("localhost")
