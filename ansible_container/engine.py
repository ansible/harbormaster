# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

logger = logging.getLogger(__name__)

import os
import tarfile
import datetime
import getpass
import json

import docker
from docker.utils import kwargs_from_env
from compose.config.config import load as config_load, find as config_find


from .exceptions import (AnsibleContainerNotInitializedException,
                         AnsibleContainerAlreadyInitializedException,
                         AnsibleContainerNoAuthenticationProvided)
from .utils import (extract_hosts_from_docker_compose,
                    jinja_render_to_temp,
                    launch_docker_compose,
                    make_temp_dir,
                    jinja_template_path,
                    which_docker,
                    extract_hosts_touched_by_playbook,
                    get_current_logged_in_user,
                    assert_initialized,
                    get_latest_image_for)

from ansible_container.shipit.run import run_shipit


def cmdrun_init(base_path, **kwargs):
    container_dir = os.path.normpath(
        os.path.join(base_path, 'ansible'))
    container_cfg = os.path.join(container_dir, 'container.yml')
    if os.path.exists(container_cfg):
        raise AnsibleContainerAlreadyInitializedException()
    if not os.path.exists(container_dir):
        os.mkdir(container_dir)
    template_dir = os.path.join(jinja_template_path(), 'ansible')
    for tmpl_filename in os.listdir(template_dir):
        jinja_render_to_temp('ansible/%s' % tmpl_filename,
                             container_dir,
                             tmpl_filename.replace('.j2', ''))
    logger.info('Ansible Container initialized.')

def build_buildcontainer_image(base_path):
    assert_initialized(base_path)
    # To ensure version compatibility, we have to generate the kwargs ourselves
    client_kwargs = kwargs_from_env(assert_hostname=False)
    client = docker.AutoVersionClient(**client_kwargs)
    with make_temp_dir() as temp_dir:
        logger.info('Building Docker Engine context...')
        tarball_path = os.path.join(temp_dir, 'context.tar')
        tarball_file = open(tarball_path, 'wb')
        tarball = tarfile.TarFile(fileobj=tarball_file,
                                  mode='w')
        container_dir = os.path.normpath(os.path.join(base_path,
                                                      'ansible'))
        try:
            tarball.add(container_dir, arcname='ansible')
        except OSError:
            raise AnsibleContainerNotInitializedException()
        jinja_render_to_temp('ansible-dockerfile.j2', temp_dir, 'Dockerfile')
        tarball.add(os.path.join(temp_dir, 'Dockerfile'),
                    arcname='Dockerfile')
        jinja_render_to_temp('hosts.j2', temp_dir, 'hosts',
                             hosts=extract_hosts_from_docker_compose(base_path))
        tarball.add(os.path.join(temp_dir, 'hosts'), arcname='hosts')
        tarball.close()
        tarball_file = open(tarball_path, 'rb')
        logger.info('Starting Docker build of Ansible Container image...')
        return [streamline for streamline in client.build(fileobj=tarball_file,
                                                          rm=True,
                                                          custom_context=True,
                                                          pull=True,
                                                          forcerm=True,
                                                          tag='ansible-container-builder')]


def cmdrun_build(base_path, recreate=True, flatten=True, purge_last=True,
                 **kwargs):
    assert_initialized(base_path)
    # To ensure version compatibility, we have to generate the kwargs ourselves
    client_kwargs = kwargs_from_env(assert_hostname=False)
    client = docker.AutoVersionClient(**client_kwargs)
    if recreate or not client.images(name='ansible-container-builder', quiet=True):
        logger.info('(Re)building the Ansible Container image is necessary.')
        build_output = build_buildcontainer_image(base_path)
        for line in build_output:
            logger.debug(line)
    builder_img_id = client.images(name='ansible-container-builder', quiet=True)[0]
    logger.info('Ansible Container image has ID %s', builder_img_id)
    with make_temp_dir() as temp_dir:
        logger.info('Starting Compose engine to build your images...')
        touched_hosts = extract_hosts_touched_by_playbook(base_path,
                                                          builder_img_id)
        launch_docker_compose(base_path, temp_dir, 'build',
                              which_docker=which_docker(),
                              builder_img_id=builder_img_id,
                              extra_command_options={'--abort-on-container-exit': True})
        build_container_info, = client.containers(
            filters={'name': 'ansible_ansible-container_1'},
            limit=1, all=True
        )
        builder_container_id = build_container_info['Id']
        # Not the best way to test for success or failure, but it works.
        exit_status = build_container_info['Status']
        if '(0)' not in exit_status:
            logger.error('Ansible playbook run failed.')
            logger.info('Cleaning up Ansible Container builder...')
            client.remove_container(builder_container_id)
            return
        # Cool - now export those containers as images
        # FIXME: support more-than-one-instance
        project_name = os.path.basename(base_path).lower()
        logger.debug('project_name is %s' % project_name)
        version = datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')
        logger.info('Exporting built containers as images...')
        for host in touched_hosts:
            container_id, = client.containers(
                filters={'name': 'ansible_%s_1' % host},
                limit=1, all=True, quiet=True
            )
            previous_image_id, previous_image_buildstamp = get_latest_image_for(
                project_name, host, client
            )
            if flatten:
                logger.info('Flattening image...')
                exported = client.export(container_id)
                client.import_image_from_data(
                    exported.read(),
                    repository='%s-%s' % (project_name, host),
                    tag=version)
            else:
                logger.info('Committing image...')
                client.commit(container_id,
                              repository='%s-%s' % (project_name, host),
                              tag=version,
                              message='Built using Ansible Container'
                              )
            image_id, = client.images(
                '%s-%s:%s' % (project_name, host, version),
                quiet=True
            )
            logger.info('Exported %s-%s with image ID %s', project_name, host,
                        image_id)
            client.tag(image_id, '%s-%s' % (project_name, host), tag='latest',
                       force=True)
            logger.info('Cleaning up %s build container...', host)
            client.remove_container(container_id)
            if purge_last and previous_image_id:
                logger.info('Removing previous image...')
                client.remove_image(previous_image_id, force=True)
        for host in set(extract_hosts_from_docker_compose(base_path)) - set(touched_hosts):
            logger.info('Cleaning up %s build container...', host)
            container_id, = client.containers(
                filters={'name': 'ansible_%s_1' % host},
                limit=1, all=True, quiet=True
            )
            client.remove_container(container_id)
        logger.info('Cleaning up Ansible Container builder...')
        client.remove_container(builder_container_id)

def cmdrun_run(base_path, **kwargs):
    assert_initialized(base_path)
    with make_temp_dir() as temp_dir:
        project_name = os.path.basename(base_path).lower()
        logger.debug('project_name is %s' % project_name)
        launch_docker_compose(base_path, temp_dir, 'run',
                              services=extract_hosts_from_docker_compose(base_path),
                              project_name=project_name)

DEFAULT_DOCKER_REGISTRY_URL = 'https://index.docker.io/v1/'

def cmdrun_push(base_path, username=None, password=None, email=None, url=None,
                **kwargs):
    assert_initialized(base_path)
    # To ensure version compatibility, we have to generate the kwargs ourselves
    client_kwargs = kwargs_from_env(assert_hostname=False)
    client = docker.AutoVersionClient(**client_kwargs)
    if not url:
        url = DEFAULT_DOCKER_REGISTRY_URL
    if username and email:
        # We assume if no username was given, the docker config file suffices
        while not password:
            password = getpass.getpass(u'Enter password for %s at %s: ' % (
                username, url
            ))
        client.login(username=username, password=password, email=email,
                     registry=url)
    username = get_current_logged_in_user(url)
    if not username:
        raise AnsibleContainerNoAuthenticationProvided(u'Please provide login '
                                                       u'credentials for this registry.')
    logger.info('Pushing to repository for user %s', username)
    builder_img_id = client.images(name='ansible-container-builder', quiet=True)[0]
    project_name = os.path.basename(base_path).lower()
    for host in extract_hosts_touched_by_playbook(base_path,
                                                  builder_img_id):
        image_id, image_buildstamp = get_latest_image_for(project_name, host, client)
        client.tag(image_id,
                   '%s/%s-%s' % (username, project_name, host),
                   tag=image_buildstamp)
        logger.info('Pushing %s-%s:%s...', project_name, host, image_buildstamp)
        status = client.push('%s/%s-%s' % (username, project_name, host),
                             tag=image_buildstamp,
                             stream=True)
        last_status = None
        for line in status:
            line = json.loads(line)
            if type(line) is dict and 'error' in line:
                logger.error(line['error'])
            elif type(line) is dict and 'status' in line:
                if line['status'] != last_status:
                    logger.info(line['status'])
                last_status = line['status']
            else:
                logger.debug(line)
    logger.info('Done!')


def cmdrun_shipit(base_path, **kwargs):
    logger.debug("Running shipit")
    project_name = os.path.basename(base_path).lower()
    logger.debug('project_name is %s' % project_name)
    config = config_load(config_find('.', None, dict()))
    logger.debug('config loaded.')
    create_templates = kwargs.pop('save_config')
    logger.debug('create_templates: %s' % create_templates)
    run_shipit(config=config, project_name=project_name, project_dir='.', create_templates=create_templates)
