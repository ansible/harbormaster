import shutil
import tempfile
from os import path
import unittest
import os
import yaml
import json

import container
from container.config import AnsibleContainerConfig, AnsibleContainerConductorConfig
from container.exceptions import AnsibleContainerConfigException
from ansible.vars import Templar

if 'PROJECT_PATH' not in os.environ:
    raise ImportError('PROJECT_PATH must be in the environment. You '
                      'probably want to run this via "python setup.py test"')


class TestAnsibleContainerConfig(unittest.TestCase):

    def setUp(self):
        self.project_path = os.environ['PROJECT_PATH']
        self.var_file = os.path.join(self.project_path, 'vars.yml')
        container.ENV = 'host'
        container.config.Templar = Templar
        self.config = AnsibleContainerConfig(self.project_path, var_file=None, engine_name='docker')

    def tearDown(self):
        pass

    def test_should_instantiate(self):
        self.assertEqual(len(self.config._config['services'].keys()), 1,
                         'Failed to load container.yml {}'.format(json.dumps(self.config._config, indent=4)))

    # def test_should_remove_defaults_section(self):
    #     self.assertEqual(self.config.get('defaults', None), None, 'Failed to remove defaults.')

    def test_should_parse_defaults(self):
        defaults = self.config._config.get('defaults')
        self.assertEqual(defaults['foo'], 'bar')
        self.assertEqual(defaults['debug'], 0)
        self.assertEqual(defaults['web_image'], 'apache:latest')

    def test_should_parse_yaml_file(self):
        self.config.var_file = self.var_file
        result = {}
        for key, value in self.config._get_variables_from_file():
            result[key] = value
        self.assertEqual(result['debug'], 1, 'Failed to parse devel.yml - checked debug')
        self.assertEqual(result['web_image'], "python:2.7", "Failed to parse devel.yml - web_image")

    def test_should_parse_json_file(self):
        self.config.var_file = os.path.join(self.project_path, 'vars.txt')
        result = {}
        for key, value in self.config._get_variables_from_file():
            result[key] = value
        self.assertEqual(result['debug'], 1, 'Failed to parse devel.txt - checked debug')
        self.assertEqual(result['web_image'], "python:2.7", "Failed to parse devel.txt - web_image")

    def test_should_raise_file_not_found_error(self):
        self.config.var_file = os.path.join(self.project_path, 'foo')
        with self.assertRaises(AnsibleContainerConfigException) as exc:
             self.config._get_variables_from_file()
        self.assertIn('not found', exc.exception.args[0])

    def test_should_read_environment_vars(self):
         os.environ.update({u'AC_DEBUG': '2'})
         new_vars = self.config._get_environment_variables()
         self.assertDictContainsSubset({u'debug': '2'}, new_vars)

    def test_should_give_precedence_to_env_vars(self):
        # If an environment var exists, it should get precedence.
        os.environ.update({u'AC_FOO': 'cats'})
        self.config.var_file = self.var_file
        self.config.set_env('prod')
        container.ENV = 'conductor'
        conductor_config = AnsibleContainerConductorConfig(self.config._config)
        self.assertEqual(conductor_config['services']['web']['foo'], 'cats')

    def test_should_give_precedence_to_file_vars(self):
        # If no environment var, then var defined in var_file should get precedence.
        if os.environ.get('AC_FOO'):
            del os.environ['AC_FOO']
        self.config.var_file = self.var_file
        self.config.set_env('prod')
        container.ENV = 'conductor'
        conductor_config = AnsibleContainerConductorConfig(self.config._config)
        self.assertEqual(conductor_config['services']['web']['foo'], 'baz')

    def test_should_give_precedence_to_default_vars(self):
        # If no environment var and no var_file, then the default value should be used.
        if os.environ.get('AC_FOO'):
            del os.environ['AC_FOO']
        self.config.var_file = None
        self.config.set_env('prod')
        container.ENV = 'conductor'
        conductor_config = AnsibleContainerConductorConfig(self.config._config)
        self.assertEqual(conductor_config['services']['web']['foo'], 'bar')

    def test_should_replace_pwd_in_volumes(self):
        self.config.var_file = self.var_file
        self.config.set_env('prod')
        container.ENV = 'conductor'
        conductor_config = AnsibleContainerConductorConfig(self.config._config)
        self.assertIn(self.project_path, conductor_config.services['web']['volumes'][0],
                      '{} not in volume[0]: {}'.format(self.project_path,
                                                       json.dumps(conductor_config.services, indent=4)))

    def test_should_resolve_lookup(self):
        self.config.var_file = self.var_file
        self.config.set_env('prod')
        container.ENV = 'conductor'
        conductor_config = AnsibleContainerConductorConfig(self.config._config)
        self.assertIn(self.project_path, conductor_config['services']['web']['environment'][0])

    def test_should_use_dev_overrides(self):
        self.config.var_file = self.var_file
        self.config.set_env('dev')
        container.ENV = 'conductor'
        conductor_config = AnsibleContainerConductorConfig(self.config._config)
        self.assertIn('DEBUG', conductor_config['services']['web']['environment'][0])

    # def test_should_resolve_filter(self):
    #     self.config.var_file = 'devel.yml'
    #     self.config.set_env('dev')
    #     self.assertEqual(self.config._config['services']['web']['environment'][2], 'VERSION={0}'.format(__version__))


