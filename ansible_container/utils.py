# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

logger = logging.getLogger(__name__)

import os
import sys
import tempfile
import shutil
import json
import base64
from functools import wraps
from StringIO import StringIO
from distutils import spawn
from jinja2 import Environment, FileSystemLoader
from yaml import load as yaml_load
from compose.cli.command import project_from_options
from compose.cli import main
from compose.cli.log_printer import LogPrinter, build_log_presenters

from .exceptions import AnsibleContainerNotInitializedException

# Don't try this at home, kids.

# *sigh* Okay, fine. Well...
# We need to tee the stdout to a StringIO buffer as well as to stdout.
# If you've got a better idea, I'm all ears.

class Tee(StringIO):
    def write(self, x):
        StringIO.write(self, x)
        sys.stdout.write(x)

    def flush(self):
        StringIO.flush(self)
        sys.stdout.flush()


def monkeypatch__log_printer_from_project(buffer):
    @wraps(main.log_printer_from_project)
    def __wrapped__(
            project,
            containers,
            monochrome,
            log_args,
            cascade_stop=False,
            event_stream=None,
    ):
        return LogPrinter(
            containers,
            build_log_presenters(project.service_names, monochrome),
            event_stream or project.events(),
            cascade_stop=cascade_stop,
            output=buffer,
            log_args=log_args)

    return __wrapped__


original__log_printer_from_project = main.log_printer_from_project


class TeedStdout(object):
    stdout = None

    def __enter__(self):
        self.stdout = StringIO()
        main.log_printer_from_project = monkeypatch__log_printer_from_project(self.stdout)
        return self.stdout

    def __exit__(self, exc_type, exc_val, exc_tb):
        main.log_printer_from_project = original__log_printer_from_project

teed_stdout = TeedStdout

# Phew. That sucked.

class MakeTempDir(object):
    temp_dir = None

    def __enter__(self):
        self.temp_dir = tempfile.mkdtemp()
        logger.debug('Using temporary directory %s...', self.temp_dir)
        return self.temp_dir

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            logger.debug('Cleaning up temporary directory %s...', self.temp_dir)
            shutil.rmtree(self.temp_dir)
        except Exception, e:
            logger.exception('Failure cleaning up temp space')
            pass

make_temp_dir = MakeTempDir

# Docker-compose uses docopt, which outputs things like the below
# So I'm starting with the defaults and then updating them.
# One structure for the global options and one for the command specific

DEFAULT_COMPOSE_OPTIONS = {
    u'--help': False,
    u'--host': None,
    u'--project-name': None,
    u'--skip-hostname-check': False,
    u'--tls': False,
    u'--tlscacert': None,
    u'--tlscert': None,
    u'--tlskey': None,
    u'--tlsverify': False,
    u'--verbose': False,
    u'--version': False,
    u'-h': False,
    u'--file': [],
    u'COMMAND': None,
    u'ARGS': []
}

DEFAULT_COMPOSE_UP_OPTIONS = {
    u'--abort-on-container-exit': False,
    u'--build': False,
    u'--force-recreate': False,
    u'--no-color': False,
    u'--no-deps': False,
    u'--no-recreate': False,
    u'--no-build': False,
    u'--remove-orphans': False,
    u'--timeout': None,
    u'-d': False,
    u'SERVICE': []
}

def launch_docker_compose(base_path, temp_dir, verb, services=[], no_color=False,
                          extra_command_options=dict(), **context):
    version = compose_format_version(base_path)
    jinja_render_to_temp(('%s-docker-compose.j2.yml' if version == 2
                         else '%s-docker-compose-v1.j2.yml') % (verb,),
                         temp_dir,
                         'docker-compose.yml',
                         hosts=extract_hosts_from_docker_compose(
                             base_path),
                         **context)
    options = DEFAULT_COMPOSE_OPTIONS.copy()
    options.update({
        u'--file': [
            os.path.normpath(
                os.path.join(base_path,
                             'ansible',
                             'container.yml')
            ),
            os.path.join(temp_dir,
                         'docker-compose.yml')],
        u'COMMAND': 'up',
        u'ARGS': ['--no-build'] + services
    })
    command_options = DEFAULT_COMPOSE_UP_OPTIONS.copy()
    command_options[u'--no-build'] = True
    command_options[u'--no-color'] = no_color
    command_options[u'SERVICE'] = services
    command_options.update(extra_command_options)
    os.environ['ANSIBLE_CONTAINER_BASE'] = os.path.realpath(base_path)
    project = project_from_options('.', options)
    command = main.TopLevelCommand(project)
    command.up(command_options)

def extract_hosts_from_docker_compose(base_path):
    compose_data = parse_compose_file(base_path)
    if compose_format_version(base_path, compose_data) == 2:
        services = compose_data.pop('services', {})
    else:
        services = compose_data
    return [key for key in services.keys() if key != 'ansible-container']

def extract_hosts_touched_by_playbook(base_path, builder_img_id):
    compose_data = parse_compose_file(base_path)
    if compose_format_version(base_path, compose_data) == 2:
        services = compose_data.pop('services', {})
    else:
        services = compose_data
    ansible_args = services.get('ansible-container', {}).get('command', [])
    if not ansible_args:
        logger.warning('No ansible playbook arguments found in container.yml')
        return []
    with teed_stdout() as stdout, make_temp_dir() as temp_dir:
        launch_docker_compose(base_path, temp_dir, 'listhosts',
                              services=['ansible-container'], no_color=True,
                              which_docker=which_docker(),
                              builder_img_id=builder_img_id)
        # We need to cleverly extract the host names from the output...
        lines = stdout.getvalue().split('\r\n')
        lines_minus_builder_host = [line.rsplit('|', 1)[1] for line
                                         in lines if '|' in line]
        host_lines = [line for line in lines_minus_builder_host
                      if line.startswith('       ')]
        hosts = list(set([line.strip() for line in host_lines]))
    return hosts

def jinja_template_path():
    return os.path.normpath(
        os.path.join(
            os.path.dirname(__file__),
            'templates'))

def jinja_render_to_temp(template_file, temp_dir, dest_file, **context):
    j2_tmpl_path = jinja_template_path()
    j2_env = Environment(loader=FileSystemLoader(j2_tmpl_path))
    j2_tmpl = j2_env.get_template(template_file)
    dockerfile = j2_tmpl.render(context)
    open(os.path.join(temp_dir, dest_file), 'w').write(
        dockerfile.encode('utf8'))

def which_docker():
    return spawn.find_executable('docker')

def parse_compose_file(base_path):
    compose_file = os.path.normpath(
        os.path.join(
            base_path,
            'ansible',
            'container.yml'
        )
    )
    try:
        ifs = open(compose_file)
    except OSError:
        raise AnsibleContainerNotInitializedException()
    compose_data = yaml_load(ifs)
    ifs.close()
    return compose_data

def compose_format_version(base_path, compose_data=None):
    if not compose_data:
        compose_data = parse_compose_file(base_path)
    return int(compose_data.pop('version', 1))

DOCKER_CONFIG_FILEPATH_CASCADE = [
    os.environ.get('DOCKER_CONFIG', ''),
    os.path.join(os.environ.get('HOME', ''), '.docker', 'config.json'),
    os.path.join(os.environ.get('HOME', ''), '.dockercfg')
]

def get_current_logged_in_user(registry_url):
    for docker_config_filepath in DOCKER_CONFIG_FILEPATH_CASCADE:
        if docker_config_filepath and os.path.exists(docker_config_filepath):
            docker_config = json.load(open(docker_config_filepath))
            break
    if 'auths' in docker_config:
        docker_config = docker_config['auths']
    auth_key = docker_config.get(registry_url, {}).get('auth', '')
    if auth_key:
        username, password = base64.decodestring(auth_key).split(':', 1)
        return username

def assert_initialized(base_path):
    ansible_dir = os.path.normpath(
        os.path.join(base_path, 'ansible'))
    container_file = os.path.join(ansible_dir, 'container.yml')
    if not os.path.exists(ansible_dir) or not os.path.isdir(ansible_dir) or \
            not os.path.exists(container_file) or not os.path.isfile(container_file):
        raise AnsibleContainerNotInitializedException()

def get_latest_image_for(project_name, host, client):
    image_data = client.images(
        '%s-%s' % (project_name, host,)
    )
    try:
        latest_image_data, = [datum for datum in image_data
                              if '%s-%s:latest' % (project_name, host,) in
                              datum['RepoTags']]
        image_buildstamp = [tag for tag in latest_image_data['RepoTags']
                            if not tag.endswith(':latest')][0].split(':')[-1]
        image_id = latest_image_data['Id']
        return image_id, image_buildstamp
    except (IndexError, ValueError):
        # No previous image built
        return None, None
