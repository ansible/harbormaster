# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

logger = logging.getLogger(__name__)

import os
import json

from ruamel import yaml

if 'TO_AC' not in os.environ or 'DISTRO_DATA' not in os.environ:
    raise ImportError('TO_AC and DISTRO_DATA must be in the environment. You '
                      'probably want to run this via "python setup.py test"')

distro_vars = json.loads(os.environ['DISTRO_DATA'])

role_defaults = yaml.round_trip_load(
    open(os.path.join(os.environ['TO_AC'], 'roles', distro_vars['name'],
                      'defaults', 'main.yml'))
)

role_meta = yaml.round_trip_load(
    open(os.path.join(os.environ['TO_AC'], 'roles', distro_vars['name'],
                      'meta', 'container.yml'))
)

role_tasks = yaml.round_trip_load(
    open(os.path.join(os.environ['TO_AC'], 'roles', distro_vars['name'],
                      'tasks', 'main.yml'))
)

def test_from():
    assert role_meta['from'] == distro_vars['base_image']

def test_environment():
    assert role_meta['environment']['APACHE_PORT'] == '{{ apache_port }}'

def test_labels():
    for k, v in [
        ('a', '1'),
        ('b', '2'),
        ('c', '3'),
        ('the bird', 'the word'),
        ('foo', 'bar'),
        ('baz', 'buzz')
    ]:
        assert role_meta['labels'][k] == v

# ROLE METADATA TESTS

def test_command():
    assert role_meta['command'] == [distro_vars['template']['httpd_bin'], '-DFOREGROUND']

def test_entrypoint():
    assert role_meta['entrypoint'] == ['/usr/sbin/dumb-init']

def test_ports():
    assert role_meta['ports'] == ['{{ apache_port }}']

def test_user():
    assert role_meta['user'] == distro_vars['template']['httpd_user']

def test_volumes():
    assert role_meta['volumes'] == ['/vol']

def test_working_dir():
    assert role_meta['working_dir'] == '/tmp'

def test_shell():
    assert u' '.join(role_meta['shell']) == u'/bin/sh -c'

# ROLE TASK TESTS

def test_add_from_url():
    url = 'https://github.com/Yelp/dumb-init/releases/download/v1.2.0/dumb-init_1.2.0_amd64'
    target = '/usr/sbin/dumb-init'
    assert any(
        [task.get('get_url') == {'url': url, 'dest': target, 'mode': 0o600, 'validate_certs': 'no'}
         for task in role_tasks]
    )

def test_add_from_tarball():
    assert any(
        [task.get('unarchive') == {'src': 'html.tar.gz',
                                   'dest': distro_vars['template']['httpd_pageroot']}
         for task in role_tasks]
    )

def test_add_from_file():
    assert any(
        [task.get('copy') == {'src': distro_vars['template']['httpd_conf_src'],
                              'dest': distro_vars['template']['httpd_conf_dest']}
         for task in role_tasks]
    )

def test_copy_from_dir():
    assert any(
        [task.get('synchronize') == {'src': "foo",
                                     'dest': '/',
                                     'recursive': 'yes'}
         for task in role_tasks]
    )

def test_run_as_command():
    assert any(
        [task.get('command') == 'chmod 755 /usr/sbin/dumb-init'
         for task in role_tasks]
    )

def test_run_as_shell():
    assert any(
        [task.get('shell') == distro_vars['template']['package_update_command']
         for task in role_tasks]
    )

def test_run_with_newline():
    assert any(
        [task.get('shell') == distro_vars['template']['httpd_install_command']
         for task in role_tasks]
    )

# def test_run_picks_up_shell_user_and_cwd():
#     task = [task for task in role_tasks
#             if task.get('shell') == '/bin/true'][0]
#     assert task['remote_user'] == distro_vars['httpd_user']
#     assert task['args']['executable'] == '/bin/sh -c'
#     assert task['args']['chdir'] == '/tmp'

# ROLE DEFAULTS

def test_apache_port_in_defaults():
    assert role_defaults['apache_port'] == '8000'
