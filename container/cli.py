# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

logger = logging.getLogger(__name__)

import os
import sys
import argparse

from . import engine
from . import exceptions
from .utils import load_shipit_engine, AVAILABLE_SHIPIT_ENGINES

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
            'container': {
                'handlers': ['console'],
                'level': 'INFO',
                'propagate': False
            },
            'compose': {
                'handlers': ['console'],
                'level': 'WARNING',
                'propagate': False
            },
            'docker': {
                'handlers': ['console'],
                'level': 'WARNING',
                'propagate': False
            }
        },
        'root': {
            'handlers': ['console'],
            'level': 'ERROR'
        }
    }


AVAILABLE_COMMANDS = {'help': 'Display this help message',
                      'init': 'Initialize a new Ansible Container project',
                      'build': 'Build new images based on ansible/container.yml',
                      'run': 'Run and orchestrate built images based on container.yml',
                      'push': 'Push your built images to a Docker Hub compatible registry',
                      'shipit': 'Generate a deployment playbook to your cloud of choice.'}

def subcmd_init_parser(parser, subparser):
    return

def subcmd_build_parser(parser, subparser):
    subparser.add_argument('--no-flatten', action='store_false',
                           help=u'By default, Ansible Container will flatten your '
                                u'build image into a single layer. With this '
                                u'flag, it will preserve the history of your '
                                u'base image.',
                           dest='flatten', default=True)
    subparser.add_argument('--no-purge-last', action='store_false',
                           help=u'By default, Ansible Container will remove the '
                                u'previously built image for your hosts. Disable '
                                u'that with this flag.')
    subparser.add_argument('--from-scratch', action='store_true',
                           help=u'Instead of running the Ansible playbook against '
                                u'the existing copies of your containers, run the '
                                u'playbook against the base image, rebuilding them '
                                u'from scratch.',
                           dest='rebuild', default=False)
    subparser.add_argument('ansible_options', action='store',
                           help=u'Provide additional commandline arguments to '
                                u'Ansible in executing your playbook. If you '
                                u'use this argument, you will need to use -- to '
                                u'prefix your extra options. Use this feature with '
                                u'caution.', default=u'', nargs='*')

def subcmd_run_parser(parser, subparser):
    subparser.add_argument('service', action='store',
                           help=u'The specific services you want to run',
                           nargs='*')
    subparser.add_argument('--production', action='store_true',
                           help=u'Run the production configuration locally',
                           default=False, dest='production')

def subcmd_help_parser(parser, subparser):
    return

def subcmd_push_parser(parser, subparser):
    subparser.add_argument('--username', action='store',
                           help=u'If authentication with the registry is required, provide a valid username.',
                           dest='username', default=None)
    subparser.add_argument('--email', action='store',
                           help=(u'If authentication with the registry requires an email address, provide a '
                                 u'valid email address'),
                           dest='email', default=None)
    subparser.add_argument('--password', action='store',
                           help=u'If authentication with the registry is required, provide a valid password.',
                           dest='password', default=None)
    subparser.add_argument('--url', action='store',
                           help=(u'When authenticating with a registry, provide the registry URL. Otherwise, the ',
                                 u'default URL for the selected container engine will be used.'),
                           dest='url', default=None)
    subparser.add_argument('--namespace', action='store',
                           help=(u'An optional organization or project name to append to the registry URL. Defaults '
                                 u'to the username.'),
                           dest='namespace', default=None)
    subparser.add_argument('--registry-name', action='store',
                           help=(u'Name to associate with the registry in container.yml. If not provided, '
                                 u'will attempt to use the default registry name for the selected container engine.'),
                           dest='registry_name', default=None)
    subparser.add_argument('--push-to', action='store',
                           help=u'Name of a registry defined in container.yml to which images should be pushed.',
                           dest='push_to', default=None)

def subcmd_shipit_parser(parser, subparser):
    se_subparser = subparser.add_subparsers(title='shipit-engine', dest='shipit_engine')
    for engine_name, engine in AVAILABLE_SHIPIT_ENGINES.items():
        engine_parser = se_subparser.add_parser(engine_name, help=engine['help'])
        engine_obj = load_shipit_engine(engine['cls'], base_path=os.getcwd())
        engine_obj.add_options(engine_parser)


def commandline():
    parser = argparse.ArgumentParser(description=u'Build, orchestrate, run, and '
                                                 u'ship Docker containers with '
                                                 u'Ansible playbooks')
    parser.add_argument('--debug', action='store_true', dest='debug',
                        help=u'Enable debug output', default=False)
    parser.add_argument('--engine', action='store', dest='engine_name',
                        help=u'Select your container engine and orchestrator',
                        default='docker')
    subparsers = parser.add_subparsers(title='subcommand', dest='subcommand')
    for subcommand in AVAILABLE_COMMANDS:
        logger.debug('Registering subcommand %s', subcommand)
        subparser = subparsers.add_parser(subcommand, help=AVAILABLE_COMMANDS[subcommand])
        globals()['subcmd_%s_parser' % subcommand](parser, subparser)

    args = parser.parse_args()

    if args.subcommand == 'help':
        parser.print_help()
        sys.exit(0)

    if args.debug:
        LOGGING['loggers']['container']['level'] = 'DEBUG'
    config.dictConfig(LOGGING)

    try:
        getattr(engine, u'cmdrun_{}'.format(args.subcommand))(os.getcwd(),
                                                              **vars(args))
    except exceptions.AnsibleContainerAlreadyInitializedException, e:
        logger.error('Ansible Container is already initialized')
        sys.exit(1)
    except exceptions.AnsibleContainerNotInitializedException, e:
        logger.error('No Ansible Container project data found - do you need to '
                     'run "ansible-container init"?')
        sys.exit(1)
    except exceptions.AnsibleContainerNoAuthenticationProvided, e:
        logger.error(unicode(e))
        sys.exit(1)
    except Exception, e:
        if args.debug:
            logger.exception(unicode(e))
        else:
            logger.error(unicode(e))
        sys.exit(1)
