# -*- coding: utf-8 -*-
from __future__ import absolute_import

from .visibility import getLogger
logger = getLogger(__name__)

"""
cli.py - The console script for Ansible Container inside of the Conductor
container.
"""

import sys
import argparse
import base64
import json

from .config import AnsibleContainerConductorConfig
from . import core

from logging import config
LOGGING = {
        'version': 1,
        'disable_existing_loggers': True,
        'handlers': {
            'console': {
                'level': 'DEBUG',
                'class': 'logging.StreamHandler',
            },
        },
        'loggers': {
            'conductor': {
                'handlers': ['console'],
                'level': 'INFO',
                'propagate': False
            },
        },
        'root': {
            'handlers': ['console'],
            'level': 'ERROR'
        }
    }

def decode_b64json(encoded_params):
    return json.loads(base64.decodestring(encoded_params))

def commandline():
    sys.stderr.write('Parsing conductor CLI args.\n')
    parser = argparse.ArgumentParser(description=u'This should not be invoked '
                                                 u'except in a container by '
                                                 u'Ansible Container.')
    parser.add_argument('command', action='store', help=u'Command to run.',
                        choices=['build', 'deploy', 'install', 'push', 'run', 'restart',
                                 'stop'])
    parser.add_argument('--project-name', action='store', help=u'Project name.', required=True)
    parser.add_argument('--engine', action='store', help=u'Engine name.', required=True)
    parser.add_argument('--params', action='store', required=False,
                        help=u'Encoded parameters for command.')
    parser.add_argument('--config', action='store', required=True,
                        help=u'Encoded Ansible Container config.')
    parser.add_argument('--encoding', action='store', choices=['b64json'],
                        help=u'Encoding used for parameters.', default='b64json')

    args = parser.parse_args()

    decoding_fn = globals()['decode_%s' % args.encoding]
    if args.params:
        params = decoding_fn(args.params)
    else:
        params = {}

    if params.get('debug'):
        LOGGING['loggers']['conductor']['level'] = 'DEBUG'
    config.dictConfig(LOGGING)

    containers_config = decoding_fn(args.config)
    conductor_config = AnsibleContainerConductorConfig(containers_config)

    logger.debug('Starting Ansible Container Conductor: %s', args.command,
        services=conductor_config.services)
    getattr(core, args.command)(args.engine, args.project_name,
                                conductor_config.services,
                                volume_data=conductor_config.volumes,
                                repository_data=conductor_config.registries,
                                **params)
