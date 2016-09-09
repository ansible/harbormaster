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
                      'version': 'Display Ansible Container version information',
                      'init': 'Initialize a new Ansible Container project',
                      'build': 'Build new images based on ansible/container.yml',
                      'run': 'Run and orchestrate built images based on container.yml',
                      'stop': 'Stop the services defined in container.yml, if deployed',
                      'restart': 'Restart the services defined in container.yml',
                      'push': 'Push your built images to a Docker Hub compatible registry',
                      'shipit': 'Generate a deployment playbook to your cloud of choice.'}

def subcmd_init_parser(parser, subparser):
    return

def subcmd_build_parser(parser, subparser):
    subparser.add_argument('--flatten', action='store_true',
                           help=u'By default, Ansible Container will add a single '
                                u'layer to your base images. Specify this to squash '
                                u'the images down to a single layer.',
                           dest='flatten', default=False)
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
    subparser.add_argument('--local-builder', action='store_true',
                           help=u'Instead of using the Ansible Builder Container '
                                u'image from Docker Hub, generate one locally.')
    subparser.add_argument('--save-build-container', action='store_true',
                           help=u'Leave the Ansible Builder Container intact upon build completion. '
                                u'Use for debugging and testing.', default=False)
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
    subparser.add_argument('-d', '--detached', action='store_true',
                           help=u'Run the application in detached mode', dest='detached')
    subparser.add_argument('-o', '--remove-orphans', action='store_true',
                           help=u'Remove containers for services not defined in container.yml',
                           default=False, dest='remove_orphans')

def subcmd_stop_parser(parser, subparser):
    subparser.add_argument('service', action='store',
                           help=u'The specific services you want to stop',
                           nargs='*')
    subparser.add_argument('-f', '--force', action='store_true',
                           help=u'Force stop running containers',
                           dest='force')

def subcmd_restart_parser(parser, subparser):
    subparser.add_argument('service', action='store',
                           help=u'The specific services you want to restart',
                           nargs='*')

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
    subparser.add_argument('--push-to', action='store',
                           help=(u'Name of a registry defined in container.yml or the actual URL of the registry, '
                                 u'including the namespace. If passing a URL, an example would be: '
                                 u'"https://registry.example.com:5000/myproject"'),
                           dest='push_to', default=None)

def subcmd_version_parser(parser, subparser):
    return

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
    parser.add_argument('--project', '-p', action='store', dest='base_path',
                        help=u'Specify a path to your project. Defaults to '
                             u'current working directory.', default=os.getcwd())
    parser.add_argument('--var-file', action='store',
                        help=u'Path to a YAML or JSON formatted file providing variables for '
                             u'Jinja2 templating in container.yml.', default=None)
    parser.add_argument('--playbook', action='store',
                        help=u'Path to a playbook, overriding main.yml. Path will become a volume '
                             u'in Ansible Builder Container', dest='playbook', default='main.yml')
    parser.add_argument('--with-volumes', '-v', action='append',
                        help=u'Mount one or more volumes to the Ansible Builder Container. '
                             u'Specify volumes as strings using the Docker volume format.', default=[])
    parser.add_argument('--with-variables', '-e', action='append',
                        help=u'Define one or more environment variables in the Ansible '
                             u'Builder Container. Format each variable as a key=value string.', default=[])

    subparsers = parser.add_subparsers(title='subcommand', dest='subcommand')
    for subcommand in AVAILABLE_COMMANDS:
        logger.debug('Registering subcommand %s', subcommand)
        subparser = subparsers.add_parser(subcommand, help=AVAILABLE_COMMANDS[subcommand])
        globals()['subcmd_%s_parser' % subcommand](parser, subparser)

    args = parser.parse_args()

    if args.subcommand == 'help':
        parser.print_help()
        sys.exit(0)

    if args.debug and args.subcommand != 'version':
        LOGGING['loggers']['container']['level'] = 'DEBUG'
    config.dictConfig(LOGGING)

    try:
        getattr(engine, u'cmdrun_{}'.format(args.subcommand))(**vars(args))
    except exceptions.AnsibleContainerAlreadyInitializedException, e:
        logger.error('Ansible Container is already initialized')
        sys.exit(1)
    except exceptions.AnsibleContainerNotInitializedException, e:
        if e.message:
            logger.error(e.message)
        else:
            logger.error('No Ansible Container project data found - do you need to '
                         'run "ansible-container init"?')
        sys.exit(1)
    except exceptions.AnsibleContainerNoAuthenticationProvidedException, e:
        logger.error(unicode(e))
        sys.exit(1)
    except Exception, e:
        if args.debug:
            logger.exception(unicode(e))
        else:
            logger.error(unicode(e))
        sys.exit(1)
