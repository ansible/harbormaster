# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging
plainLogger = logging.getLogger(__name__)

from container.common.visibility import getLogger
logger = getLogger(__name__)

import os
import time
import hashlib
import tempfile
import shutil
import subprocess

import yaml

from container.common.loader import load_engine
from .utils import get_role_fingerprint


def run_playbook(playbook, engine, service_map, ansible_options='',
                 python_interpreter=None, debug=False):
    try:
        tmpdir = tempfile.mkdtemp()
        playbook_path = os.path.join(tmpdir, 'playbook.yml')
        with open(playbook_path, 'w') as ofs:
            yaml.safe_dump(playbook, ofs)
        inventory_path = os.path.join(tmpdir, 'hosts')
        with open(inventory_path, 'w') as ofs:
            for service_name, container_id in service_map.iteritems():
                ofs.write('%s ansible_host="%s" ansible_python_interpreter="%s"\n' % (
                    service_name, container_id,
                    python_interpreter or engine.python_interpreter_path))
        os.mkdir(os.path.join(tmpdir, 'files'))
        os.mkdir(os.path.join(tmpdir, 'templates'))
        rc = subprocess.call(['mount', '--bind', '/src',
                              os.path.join(tmpdir, 'files')])
        if rc:
            raise OSError('Could not bind-mount /src into tmpdir')
        rc = subprocess.call(['mount', '--bind', '/src',
                              os.path.join(tmpdir, 'templates')])
        if rc:
            raise OSError('Could not bind-mount /src into tmpdir')

        ansible_args = dict(inventory=inventory_path,
                            playbook=playbook_path,
                            debug_maybe='-vvvv' if debug else '',
                            engine_args=engine.ansible_args,
                            ansible_playbook=engine.ansible_exec_path,
                            ansible_options=ansible_options or '')
        # env = os.environ.copy()
        # env['ANSIBLE_REMOTE_TEMP'] = '/tmp/.ansible-${USER}/tmp'

        ansible_cmd = ('{ansible_playbook} '
                       '{debug_maybe} '
                       '{ansible_options} '
                       '-i {inventory} '
                       '{engine_args} '
                       '{playbook}').format(**ansible_args)
        logger.debug('Running Ansible Playbook', command=ansible_cmd, cwd='/src')
        process = subprocess.Popen(ansible_cmd,
                                   shell=True,
                                   bufsize=1,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT,
                                   cwd='/src',
                                   #env=env
                                   )

        log_iter = iter(process.stdout.readline, '')
        while process.returncode is None:
            try:
                plainLogger.info(log_iter.next().rstrip())
            except StopIteration:
                process.wait()
            finally:
                process.poll()

        return process.returncode
    finally:
        try:
            rc = subprocess.call(['unmount',
                                  os.path.join(tmpdir, 'files')])
            rc = subprocess.call(['unmount',
                                  os.path.join(tmpdir, 'templates')])
        except Exception:
            pass
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass


def apply_role_to_container(role, container_id, service_name, engine,
                            python_interpreter=None, ansible_options='',
                            debug=False):
    playbook = [
        {'hosts': service_name,
         'roles': [role]}
    ]

    container_metadata = engine.inspect_container(container_id)
    onbuild = container_metadata['Config']['OnBuild']
    # FIXME: Actually do stuff if onbuild is not null

    rc = run_playbook(playbook, engine, {service_name: container_id},
                      python_interpreter, ansible_options, debug)
    if rc:
        logger.error('Error applying role!', playbook=playbook, engine=engine,
            exit_code=rc)
    return rc


def build(engine_name, project_name, services, cache=True,
          python_interpreter=None, ansible_options='', debug=False, **kwargs):
    engine = load_engine(['BUILD'], engine_name, project_name, services)
    logger.info(u'%s integration engine loaded. Build starting.',
        engine.display_name, project=project_name)

    for service_name, service in services.iteritems():
        logger.info(u'Building service...', service=service_name, project=project_name)
        cur_image_id = engine.get_image_id_by_tag(service['from'])
        # the fingerprint hash tracks cacheability
        fingerprint_hash = hashlib.sha256('%s::' % cur_image_id)
        logger.debug(u'Base fingerprint hash = %s', fingerprint_hash.hexdigest(),
                     service=service_name, hash=fingerprint_hash.hexdigest())
        cache_busted = not cache

        cur_container_id = engine.get_container_id_for_service(service_name)
        if cur_container_id:
            if engine.service_is_running(service_name):
                engine.stop_container(cur_container_id, forcefully=True)
            engine.delete_container(cur_container_id)

        if service.get('roles'):
            for role in service['roles']:
                role_fingerprint = get_role_fingerprint(role)
                fingerprint_hash.update(role_fingerprint)

                if not cache_busted:
                    logger.debug(u'Still trying to keep cache.', service=service_name)
                    cached_image_id = engine.get_image_id_by_fingerprint(
                        fingerprint_hash.hexdigest())
                    if cached_image_id:
                        # We can reuse the cached image
                        logger.debug(u'Cached layer found for service',
                                     service=service_name, fingerprint=fingerprint_hash.hexdigest())
                        cur_image_id = cached_image_id
                        logger.info(u'Applied role %s from cache', role,
                                    service=service_name, role=role)
                        continue
                    else:
                        cache_busted = True
                        logger.debug(u'Cache busted! No layer found',
                            service=service_name,
                            fingerprint=fingerprint_hash.hexdigest(),
                        )

                container_id = engine.run_container(
                    cur_image_id,
                    service_name,
                    name=engine.container_name_for_service(service_name),
                    user='root',
                    working_dir='/',
                    command='sh -c "while true; do sleep 1; '
                            'done"',
                    entrypoint=[],
                    environment=dict(LD_LIBRARY_PATH='/_usr/lib:/_usr/local/lib',
                                     CPATH='/_usr/include:/_usr/local/include',
                                     PATH='/usr/local/sbin:/usr/local/bin:'
                                          '/usr/sbin:/usr/bin:/sbin:/bin:'
                                          '/_usr/sbin:/_usr/bin:'
                                          '/_usr/local/sbin:/_usr/local/bin',
                                     PYTHONPATH='/_usr/lib/python2.7'),
                    volumes={engine.get_runtime_volume_id(): {'bind': '/_usr',
                                                              'mode': 'ro'}})
                while not engine.service_is_running(service_name):
                    time.sleep(0.2)
                logger.debug('Container running', id=container_id)

                rc = apply_role_to_container(role, container_id, service_name,
                                             engine,
                                             python_interpreter=python_interpreter,
                                             ansible_options=ansible_options,
                                             debug=debug)
                logger.debug('Playbook run finished.', exit_code=rc)
                if rc:
                    raise RuntimeError('Build failed.')
                logger.info(u'Applied role to service', service=service_name, role=role)

                engine.stop_container(container_id, forcefully=True)
                is_last_role = role is service['roles'][-1]
                image_id = engine.commit_role_as_layer(container_id,
                                                       service_name,
                                                       fingerprint_hash.hexdigest(),
                                                       service,
                                                       with_name=is_last_role)
                logger.info(u'Committed layer as image', service=service_name, image=image_id)
                engine.delete_container(container_id)
                cur_image_id = image_id
            # Tag the image also as latest:
            engine.tag_image_as_latest(service_name, cur_image_id)
            logger.info(u'Build complete.', service=service_name)
        else:
            logger.info(u'Service had no roles specified. Nothing to do.', service=service_name)
    logger.info(u'All images successfully built.')


def run(engine_name, project_name, services, **kwargs):
    engine = load_engine(['RUN'], engine_name, project_name, services)
    logger.info(u'Engine integration loaded. Preparing run.',
                engine=engine.display_name)

    # Verify all images are built
    for service_name in services:
        logger.info(u'Verifying service image', service=service_name)
        image_id = engine.get_latest_image_id_for_service(service_name)
        if image_id is None:
            logger.error(u'Missing image! Run "ansible-container build" '
                         u'to (re)create it.', service=service_name)
            raise RuntimeError('Run failed.')

    playbook = engine.generate_orchestration_playbook()
    rc = run_playbook(playbook, engine, services)


def restart(engine_name, project_name, services, **kwargs):
    engine = load_engine(engine_name, project_name, services)
    logger.info(u'Engine integration loaded. Preparing to restart containers.',
                engine=engine.display_name())
    engine.restart_all_containers()
    logger.info(u'All services restarted.')


def stop(engine_name, project_name, services, **kwargs):
    engine = load_engine(engine_name, project_name, services)
    logger.info(u'Engine integration loaded. Preparing to stop all containers.',
                engine=engine.display_name())
    for service_name in services:
        container_id = engine.get_container_id_for_service(service_name)
        if container_id:
            logger.debug(u'Stopping %s...', service_name)
            engine.stop_container(container_id)
    logger.info(u'All services stopped.')


def deploy(engine_name, project_name, services, repository_data, playbook_dest, **kwargs):
    engine = load_engine(engine_name, project_name, services)
    logger.info(u'Engine integration loaded. Preparing deploy.',
                engine=engine.display_name())

    # Verify all images are built
    for service_name in services:
        logger.info(u'Verifying image for %s', service_name)
        image_id = engine.get_latest_image_id_for_service(service_name)
        if not image_id:
            logger.error(u'Missing image. Run "ansible-container build" '
                         u'to (re)create it.', service=service_name)
            raise RuntimeError(u'Run failed.')

    for service_name in services:
        logger.info(u'Pushing image for service', service=service_name, repo_name=repository_data['name'])
        image_id = engine.get_latest_image_id_for_service(service_name)
        engine.push_image(image_id, service_name, repository_data)

    logger.info(u'All images pushed.')

    playbook = engine.generate_orchestration_playbook(repository=repository_data)

    try:
        with open(os.path.join(playbook_dest, '%s.yml' % project_name), 'w') as ofs:
            yaml.safe_dump(playbook, ofs)
    except OSError:
        logger.error(u'Failure writing deployment playbook', exc_info=True)
        raise


def install(engine_name, project_name, services, role, **kwargs):
    # FIXME: Port me from ac_galaxy.py
    pass


def push(engine_name, project_name, services, **kwargs):
    """ Push images to a registry """
    username = kwargs.pop('username')
    password = kwargs.pop('password')
    email = kwargs.pop('email')
    url = kwargs.pop('url')
    namespace = kwargs.pop('namespace')
    tag = kwargs.pop('tag')
    config_path = kwargs.pop('config_path')

    engine = load_engine(['PUSH', 'LOGIN'], engine_name, project_name, services)
    logger.info(u'Engine integration loaded. Preparing push.',
                engine=engine.display_name)

    # Verify that we can authenticate with the registry
    username, password = engine.login(username, password, email, url, config_path)

    repo_data = {
        'url': url,
        'namespace': namespace or username,
        'tag': tag,
        'username': username,
        'password': password
    }

    # Push each image that has been built using Ansible roles
    for service_name, service_config in services.items():
        if service_config.get('roles'):
            # if the service has roles, it's an image we should push
            image_id = engine.get_latest_image_id_for_service(service_name)
            engine.push(image_id, service_name, repo_data)
