import unittest
import os
import json

import container
from container.config import AnsibleContainerConductorConfig
from container.exceptions import AnsibleContainerConfigException
from container.utils import get_dependencies_for_role, get_config
from ansible.compat.tests.mock import mock_open, patch
from ansible.module_utils.six.moves import builtins
from ansible.playbook.role.include import RoleInclude

try:
    from ansible.vars import VariableManager, Templar
    from ansible.vars.unsafe_proxy import AnsibleUnsafeText
except ImportError:
    from ansible.vars.manager import VariableManager
    from ansible.template import Templar
    from ansible.utils.unsafe_proxy import AnsibleUnsafeText

from ansible.parsing.dataloader import DataLoader

if 'PROJECT_PATH' not in os.environ:
    raise ImportError('PROJECT_PATH must be in the environment. You '
                      'probably want to run this via "python setup.py test"')


class TestAnsibleContainerConfig(unittest.TestCase):

    def setUp(self):
        self.project_path = os.environ['PROJECT_PATH']
        self.vars_files = [os.path.join(self.project_path, 'vars.yml')]
        container.ENV = 'host'
        container.config.Templar = Templar
        container.config.AnsibleUnsafeText = AnsibleUnsafeText
        self.config = get_config(self.project_path, vars_files=None, engine_name='docker', config_file='container.yml')

    def tearDown(self):
        pass

    def test_should_instantiate(self):
        self.assertEqual(len(self.config._config['services'].keys()), 1,
                         'Failed to load container.yml {}'.format(json.dumps(self.config._config, indent=4)))

    def test_should_parse_defaults(self):
        defaults = self.config._config.get('defaults')
        self.assertEqual(defaults['foo'], 'bar')
        self.assertEqual(defaults['debug'], 0)
        self.assertEqual(defaults['web_image'], 'centos:7')

    def test_should_have_project_name_equal_basename(self):
        self.assertEqual(self.config.project_name, os.path.basename(self.project_path))

    def test_should_have_project_name_equal_cli(self):
        config = get_config(self.project_path, vars_files=None, engine_name='docker', project_name='foo', config_file='container.yml')
        self.assertEqual(config.project_name, 'foo')

    def test_should_have_project_name_equal_settings(self):
        self.config._config['settings'] = {'project_name': 'baz'}
        self.assertEqual(self.config.project_name, 'baz')

    def test_should_parse_yaml_file(self):
        result = {}
        for key, value in self.config._get_variables_from_file(self.vars_files[0]):
            result[key] = value
        self.assertEqual(result['debug'], 1, 'Failed to parse devel.yml - checked debug')
        self.assertEqual(result['web_image'], "python:2.7", "Failed to parse devel.yml - web_image")

    def test_should_parse_json_file(self):
        result = {}
        for key, value in self.config._get_variables_from_file(os.path.join(self.project_path, 'vars.txt')):
            result[key] = value
        self.assertEqual(result['debug'], 1, 'Failed to parse devel.txt - checked debug')
        self.assertEqual(result['web_image'], "python:2.7", "Failed to parse devel.txt - web_image")

    def test_should_raise_file_not_found_error(self):
        with self.assertRaises(AnsibleContainerConfigException) as exc:
             self.config._get_variables_from_file(os.path.join(self.project_path, 'foo'))
        self.assertIn('not found', exc.exception.args[0])

    def test_should_read_environment_vars(self):
         os.environ.update({u'AC_DEBUG': '2'})
         new_vars = self.config._get_environment_variables()
         self.assertDictContainsSubset({u'debug': '2'}, new_vars)

    def test_should_give_precedence_to_env_vars(self):
        # If an environment var exists, it should get precedence.
        os.environ.update({u'AC_FOO': 'cats'})
        self.config.cli_vars_files = self.vars_files
        self.config.set_env('prod')
        container.ENV = 'conductor'
        container.utils.DataLoader = DataLoader
        container.utils.VariableManager = VariableManager
        container.utils.RoleInclude = RoleInclude
        conductor_config = AnsibleContainerConductorConfig(self.config._config)
        self.assertEqual(conductor_config['services']['web']['environment'][1], 'foo="cats"')

    def test_should_give_precedence_to_file_vars(self):
        # If no environment var, then var defined in var_file should get precedence.
        if os.environ.get('AC_FOO'):
            del os.environ['AC_FOO']
        self.config.cli_vars_files = self.vars_files
        self.config.set_env('prod')
        container.ENV = 'conductor'
        container.utils.DataLoader = DataLoader
        container.utils.VariableManager = VariableManager
        container.utils.RoleInclude = RoleInclude
        conductor_config = AnsibleContainerConductorConfig(self.config._config)
        self.assertEqual(conductor_config['services']['web']['environment'][1], 'foo="baz"')

    def test_should_give_precedence_to_default_vars(self):
        # If no environment var and no var_file, then the default value should be used.
        if os.environ.get('AC_FOO'):
            del os.environ['AC_FOO']
        self.config.cli_var_file = None
        self.config.set_env('prod')
        container.ENV = 'conductor'
        container.utils.DataLoader = DataLoader
        container.utils.VariableManager = VariableManager
        container.utils.RoleInclude = RoleInclude
        conductor_config = AnsibleContainerConductorConfig(self.config._config)
        self.assertEqual(conductor_config['services']['web']['environment'][1], 'foo="bar"')

    def test_should_replace_pwd_in_volumes(self):
        # test that $PWD gets resolved
        self.config.cli_vars_files = self.vars_files
        self.config.set_env('prod')
        container.ENV = 'conductor'
        container.utils.DataLoader = DataLoader
        container.utils.VariableManager = VariableManager
        container.utils.RoleInclude = RoleInclude
        conductor_config = AnsibleContainerConductorConfig(self.config._config)
        self.assertIn(self.project_path, conductor_config.services['web']['volumes'][0],
                      '{} not in volume[0]: {}'.format(self.project_path,
                                                       json.dumps(conductor_config.services, indent=4)))

    def test_should_also_replace_pwd_in_volumes(self):
        # test that ${PWD} gets resolved
        self.config.cli_vars_files = self.vars_files
        self.config.set_env('prod')
        container.ENV = 'conductor'
        container.utils.DataLoader = DataLoader
        container.utils.VariableManager = VariableManager
        container.utils.RoleInclude = RoleInclude
        conductor_config = AnsibleContainerConductorConfig(self.config._config)
        self.assertIn(self.project_path, conductor_config.services['web']['volumes'][1],
                      '{} not in volume[1]: {}'.format(self.project_path,
                                                       json.dumps(conductor_config.services, indent=4)))

    def test_should_resolve_lookup(self):
        self.config.cli_vars_files = self.vars_files
        self.config.set_env('prod')
        container.ENV = 'conductor'
        container.utils.DataLoader = DataLoader
        container.utils.VariableManager = VariableManager
        container.utils.RoleInclude = RoleInclude
        conductor_config = AnsibleContainerConductorConfig(self.config._config)
        self.assertIn(self.project_path, conductor_config['services']['web']['environment'][0])

    def test_should_use_dev_overrides(self):
        self.config.cli_vars_files = self.vars_files
        self.config.set_env('dev')
        container.ENV = 'conductor'
        container.utils.DataLoader = DataLoader
        container.utils.VariableManager = VariableManager
        container.utils.RoleInclude = RoleInclude
        conductor_config = AnsibleContainerConductorConfig(self.config._config)
        self.assertIn('DEBUG', conductor_config['services']['web']['environment'][0])

    # def test_should_resolve_filter(self):
    #     self.config.cli_var_file = 'devel.yml'
    #     self.config.set_env('dev')
    #     self.assertEqual(self.config._config['services']['web']['environment'][2], 'VERSION={0}'.format(__version__))


    @patch('os.path.exists', lambda x: True)
    def test_get_dependencies_for_role(self):
        with patch.object(builtins, 'open', mock_open(read_data=b'---\n')):
            for x in get_dependencies_for_role('dummy'):
                pass
