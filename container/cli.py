# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

logger = logging.getLogger(__name__)

import os
import sys
import argparse
import importlib

from . import engine
from . import exceptions

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
                           help=(u'Username to log into registry. If not provided, '
                                 u'it is expected that your ~/.docker/config.json '
                                 u'contains your login information.'),
                           dest='username', default=None)
    subparser.add_argument('--email', action='store',
                           help=(u'Email to log into the registry. If not provided, '
                                 u'it is expected that your ~/.docker/config.json '
                                 u'contains your login information.'),
                           dest='email', default=None)
    subparser.add_argument('--password', action='store',
                           help=(u'Password to log into registry. If not provided, '
                                 u'you will be prompted for it.'),
                           dest='password', default=None)
    subparser.add_argument('--url', action='store',
                           help=(u'Base URL for your registry. If not provided, '
                                 u'Docker Hub will be used.'),
                           dest='url', default=None)
    subparser.add_argument('--repository', action='store',
                           help=(u'Path of the repository to tag and push the image into. Will be appended to '
                                 u'registry URL. Defaults to the registry username.'),
                           dest='repository', default=None)

class LoadSubmoduleAction(argparse.Action):
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        if nargs is not None:
            raise ValueError("nargs not allowed")
        super(LoadSubmoduleAction, self).__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        # Rudimentary input sanitation
        engine_name = values.split(' ', 1)[0].strip('.')
        try:
            engine_module = importlib.import_module(
                'container.shipit.%s.engine' % engine_name)
        except ImportError as exc:
            raise ImportError(
                'No shipit module for %s found - %s' % (engine_name, str(exc)))
        try:
            engine_cls = getattr(engine_module, 'ShipItEngine')
        except Exception as exc:
            raise ImportError('Error getting ShipItEngine for %s - %s' % (
            engine_name, str(exc)))

        engine_obj = engine_cls(os.getcwd())
        setattr(namespace, self.dest, engine_obj)
        engine_obj.add_options(parser)

def subcmd_shipit_parser(parser, subparser):
    subparser.add_argument('shipit_engine', action=LoadSubmoduleAction,
                           help=u'Specify the shipit engine for your cloud provider.',
                           metavar='shipit-engine')

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
