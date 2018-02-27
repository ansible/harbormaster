# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

logger = logging.getLogger(__name__)

import os
import json

try:
    from ansible.vars import Templar
except ImportError:
    from ansible.template import Templar

from ruamel import yaml
import docker

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

docker_client = docker.from_env(version='auto')
built_image_name = u'test-%s-%s:latest' % (distro_vars['name'], distro_vars['name'])
built_image_info = docker_client.images.get(built_image_name).attrs
base_image_info = docker_client.images.get(distro_vars['base_image']).attrs
templar = Templar(loader=None, variables=role_defaults)

def test_image_layers():
    assert built_image_info['Parent'] == base_image_info['Id']

def test_image_fingerprint():
    assert 'com.ansible.container.fingerprint' in built_image_info['Config']['Labels']

def test_image_environment():
    if isinstance(role_meta['environment'], dict):
        role_env = [u'='.join([k, templar.template(v)])
                    for (k, v) in role_meta['environment'].items()]
    else:
        role_env = [templar.template(s) for s in role_meta['environment']]
    assert all([item in built_image_info['Config']['Env'] for item in role_env])

def test_image_labels():
    for k, v in role_meta['labels'].items():
        assert built_image_info['Config']['Labels'][k] == v

def test_image_cmd():
    assert built_image_info['Config']['Cmd'] == role_meta['command']

def test_image_entrypoint():
    assert built_image_info['Config']['Entrypoint'] == role_meta['entrypoint']

def test_image_ports():
    assert all([templar.template(port) + '/tcp' in built_image_info['Config']['ExposedPorts']
                for port in role_meta['ports']])

def test_image_user():
    assert built_image_info['Config']['User'] == role_meta['user']

def test_image_volumes():
    assert all([vol in built_image_info['Config']['Volumes']
                for vol in role_meta['volumes']])

def test_image_working_dir():
    assert built_image_info['Config']['WorkingDir'] == role_meta['working_dir']


