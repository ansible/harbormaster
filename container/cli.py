# -*- coding: utf-8 -*-
from __future__ import absolute_import

from .utils.visibility import getLogger
logger = getLogger(__name__)

import os
import sys
import argparse
import base64
import json

import requests.exceptions

import container

from . import core
from . import exceptions
from container.config import AnsibleContainerConductorConfig
from container.utils import list_to_ordereddict

from collections import OrderedDict
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
        },
        'root': {
            'handlers': ['console'],
            'level': 'ERROR'
        }
    }

class HostCommand(object):

    AVAILABLE_COMMANDS = {'help': 'Display this help message',
                          'version': 'Display Ansible Container version information',
                          'init': 'Initialize a new Ansible Container project',
                          'install': 'Install a service from Ansible Galaxy',
                          'build': 'Build new images based on ansible/container.yml',
                          'run': 'Run and orchestrate built images based on container.yml',
                          'stop': 'Stop the services defined in container.yml, if deployed',
                          'restart': 'Restart the services defined in container.yml',
                          'destroy': 'Stop all services and delete their containers & all built images',
                          'push': 'Push your built images to a Docker Hub compatible registry',
                          'import': 'Convert a Dockerfile to a container.yml and role.',
                          # FIXME: implement purge command
                          # 'purge': 'Delete all Ansible Container instances, volumes, and images',
                          # FIXME: implement status command
                          # 'status': 'Query the status of your project's containers/images',
                          'deploy': 'Deploy your built images into production'
                          }

    def subcmd_common_parsers(self, parser, subparser, cmd):
        if cmd in ('build', 'run', 'deploy', 'push', 'restart', 'stop', 'destroy'):
            subparser.add_argument('--with-volumes', '-v', action='store', nargs='+',
                                   help=u'Mount one or more volumes to the Conductor. '
                                        u'Specify volumes as strings using the Docker volume format.',
                                   default=[])
            subparser.add_argument('--with-variables', '-e', action='store', nargs='+',
                                   help=u'Define one or more environment variables in the '
                                        u'Conductor. Format each variable as a key=value string.',
                                   default=[])

        if cmd in ('build', 'run', 'deploy', 'push'):
            subparser.add_argument('--roles-path', action='store', default=None,
                                   help=u'Specify a local path containing roles you want to '
                                        u'use in the Conductor.')

        if cmd in ('deploy', 'push'):
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
            subparser.add_argument('--tag', action='store',
                                   help=u'Tag the images before pushing.',
                                   dest='tag', default=None)


    def subcmd_init_parser(self, parser, subparser):
        subparser.add_argument('--server', '-s', action='store',
                               default='https://galaxy.ansible.com/',
                               help=u'Use a different Galaxy server URL')
        subparser.add_argument('project', nargs='?', action='store',
                               help=u'Use a project template instead of making a '
                                    u'blank project from an Ansible Container project '
                                    u'from Ansible Galaxy.')
        subparser.add_argument('--force', '-f', action='store_true',
                               help=u'Overrides the requirement that init be run'
                                    u'in an empty directory, for example'
                                    u'if a virtualenv exists in the directory.')


    def subcmd_build_parser(self, parser, subparser):
        subparser.add_argument('--flatten', action='store_true',
                               help=u'By default, Ansible Container will add a single '
                                    u'layer to your base images. Specify this to squash '
                                    u'the images down to a single layer.',
                               dest='flatten', default=False)
        subparser.add_argument('--no-purge-last', action='store_false',
                               help=u'By default, Ansible Container will remove the '
                                    u'previously built image for your hosts. Disable '
                                    u'that with this flag.',
                               dest='purge_last', default=True)
        subparser.add_argument('--save-conductor-container', action='store_true',
                               help=u'Leave the Ansible Builder Container intact upon build completion. '
                                    u'Use for debugging and testing.', default=False)
        subparser.add_argument('--no-cache', action='store_false',
                               help=u'Ansible Container caches image layers during builds '
                                    u'and reuses existing layers if it determines no '
                                    u'changes have been made necessitating rebuild. '
                                    u'You may disable layer caching with this flag.',
                               dest='cache', default=True)
        subparser.add_argument('--use-local-python', action='store_true',
                               help=u'Prevents Ansible Container from bringing its own Python runtime '
                                    u'into target containers in order to run Ansible. Use when the target '
                                    u'already has an installed Python runtime.',
                               dest='local_python', default=False)
        subparser.add_argument('--no-conductor-runtime', action='store_false',
                               help=u'')
        subparser.add_argument('ansible_options', action='store',
                               help=u'Provide additional commandline arguments to '
                                    u'Ansible in executing your playbook. If you '
                                    u'use this argument, you will need to use -- to '
                                    u'prefix your extra options. Use this feature with '
                                    u'caution.', default=u'', nargs='*')
        self.subcmd_common_parsers(parser, subparser, 'build')

    def subcmd_deploy_parser(self, parser, subparser):
        # subparser.add_argument('service', action='store',
        #                        help=u'The specific services you want to deploy',
        #                        nargs='*')
        subparser.add_argument('--output-path', action='store',
                               help=u'Path where deployment artifacts will be written. '
                                    u'Defaults to [project path]/ansible-deployment',
                               default=None, dest='deployment_output_path')
        subparser.add_argument('--local-images', action='store_true',
                               help=u'Prevents images from being pushed to the default registry',
                               default=False, dest='local_images')
        self.subcmd_common_parsers(parser, subparser, 'deploy')

    def subcmd_run_parser(self, parser, subparser):
        subparser.add_argument('service', action='store',
                               help=u'The specific services you want to run',
                               nargs='*')
        subparser.add_argument('--production', action='store_true',
                               help=u'Run the production configuration locally',
                               default=False, dest='production')
        subparser.add_argument('-d', '--detached', action='store_true',
                               help=u'Run the application in detached mode', dest='detached')
        self.subcmd_common_parsers(parser, subparser, 'run')


    def subcmd_stop_parser(self, parser, subparser):
        subparser.add_argument('service', action='store',
                               help=u'The specific services you want to stop',
                               nargs='*')
        subparser.add_argument('-f', '--force', action='store_true',
                               help=u'Force stop running containers',
                               dest='force')
        self.subcmd_common_parsers(parser, subparser, 'stop')


    def subcmd_restart_parser(self, parser, subparser):
        subparser.add_argument('service', action='store',
                               help=u'The specific services you want to restart',
                               nargs='*')
        self.subcmd_common_parsers(parser, subparser, 'restart')

    def subcmd_destroy_parser(self, parser, subparser):
        self.subcmd_common_parsers(parser, subparser, 'destroy')

    def subcmd_help_parser(self, parser, subparser):
        return

    def subcmd_push_parser(self, parser, subparser):
        self.subcmd_common_parsers(parser, subparser, 'push')

    def subcmd_version_parser(self, parser, subparser):
        return

    def subcmd_install_parser(self, parser, subparser):
        subparser.add_argument('roles', nargs='+', action='store')

    def subcmd_import_parser(self, parser, subparser):
        # Commenting out until we can solidify the "import" interface
        # subparser.add_argument('--dockerfile', action='store',
        #                       help=u"Name of the file to import. Defaults to 'Dockerfile'.",
        #                       dest='dockerfile_name', default='Dockerfile')
        subparser.add_argument('--bundle-files', action='store_true',
                               help=u'By default, Ansible Container treats files '
                                    u'in the same path you\'re importing from as '
                                    u'the build context. If you wish those files to '
                                    u'be copied to the content of the role itself, '
                                    u'use this flag.', default=False)
        subparser.add_argument('import_from', action='store',
                               help=u'Path to project/context to import.')


    @container.host_only
    def __call__(self):
        parser = argparse.ArgumentParser(description=u'Build, orchestrate, run, and '
                                                     u'ship Docker containers with '
                                                     u'Ansible playbooks')
        # FIXME: Write custom help text and command description for major/minor commands
        parser.add_argument('--debug', action='store_true', dest='debug',
                            help=u'Enable debug output', default=False)
        parser.add_argument('--devel', action='store_true', dest='devel',
                            help=u'Enable developer-mode to aid in iterative '
                                 u'development on Ansible Container.', default=False)
        parser.add_argument('--engine', action='store', dest='engine_name',
                            help=u'Select your container engine and orchestrator',
                            default='docker')
        parser.add_argument('--project-path', '-p', action='store', dest='base_path',
                            help=u'Specify a path to your project. Defaults to '
                                 u'current working directory.', default=os.getcwd())
        parser.add_argument('--project-name', '-n', action='store', dest='project_name',
                            help=u'Specify an alternate name for your project. Defaults '
                                 u'to the directory it lives in.', default=None)
        parser.add_argument('--var-file', action='store',
                            help=u'Path to a YAML or JSON formatted file providing variables for '
                                 u'Jinja2 templating in container.yml.', default=None)
        parser.add_argument('--no-selinux', action='store_false', dest='selinux',
                            help=u"Disables the 'Z' option from being set on volumes automatically "
                                 u"mounted to the build container.", default=True)

        subparsers = parser.add_subparsers(title='subcommand', dest='subcommand')
        subparsers.required = True
        for subcommand in self.AVAILABLE_COMMANDS:
            logger.debug('Registering subcommand', subcommand=subcommand)
            subparser = subparsers.add_parser(subcommand, help=self.AVAILABLE_COMMANDS[subcommand])
            getattr(self, 'subcmd_%s_parser' % subcommand)(parser, subparser)

        args = parser.parse_args()

        if args.subcommand == 'help':
            parser.print_help()
            sys.exit(0)

        if args.debug and args.subcommand != 'version':
            LOGGING['loggers']['container']['level'] = 'DEBUG'
        config.dictConfig(LOGGING)

        try:
            getattr(core, u'hostcmd_{}'.format(args.subcommand))(**vars(args))
        except exceptions.AnsibleContainerAlreadyInitializedException as e:
            logger.error('{0}'.format(e), exc_info=False)
            sys.exit(1)
        except exceptions.AnsibleContainerNotInitializedException:
            logger.error('No Ansible Container project data found - do you need to '
                    'run "ansible-container init"?', exc_info=False)
            sys.exit(1)
        except exceptions.AnsibleContainerNoAuthenticationProvidedException:
            logger.error('No authentication provided, unable to continue', exc_info=False)
            sys.exit(1)
        except exceptions.AnsibleContainerConductorException as e:
            logger.error(str(e), exc_info=False)
            sys.exit(1)
        except exceptions.AnsibleContainerNoMatchingHosts:
            logger.error('No matching service found in ansible/container.yml', exc_info=False)
            sys.exit(1)
        except exceptions.AnsibleContainerHostNotTouchedByPlaybook:
            logger.error('The requested service(s) is not referenced in ansible/main.yml. Nothing to build.',
                         exc_info=False)
            sys.exit(1)
        except exceptions.AnsibleContainerDockerConnectionRefused:
            logger.error('The connection to Docker was refused. Check your Docker environment configuration.',
                         exc_info=False)
            sys.exit(1)
        except exceptions.AnsibleContainerConfigException as e:
            logger.error('Invalid container.yml: {}'.format(e), exc_info=False)
            sys.exit(1)
        except requests.exceptions.ConnectionError:
            logger.error('Could not connect to container host. Check your docker config', exc_info=False)
            sys.exit(1)
        except exceptions.AnsibleContainerEngineCapability as e:
            logger.error(str(e), exc_info=False)
            sys.exit(1)
        except exceptions.AnsibleContainerMissingImage as e:
            logger.error(str(e), exc_info=False)
            sys.exit(1)
        except Exception as e:
            if args.debug:
                logger.exception('Unknown exception %s' % e, exc_info=True)
            else:
                logger.error('Unknown exception', exc_info=True)
            sys.exit(1)

host_commandline = HostCommand()


def decode_b64json(encoded_params):
    # Using object_pairs_hook to preserve the original order of any dictionaries
    return json.loads(base64.b64decode(encoded_params).decode())


@container.conductor_only
def conductor_commandline():
    sys.stderr.write('Parsing conductor CLI args.\n')
    parser = argparse.ArgumentParser(description=u'This should not be invoked '
                                                 u'except in a container by '
                                                 u'Ansible Container.')
    parser.add_argument('command', action='store', help=u'Command to run.',
                        choices=['build', 'deploy', 'install', 'push', 'run', 'restart',
                                 'stop', 'destroy'])
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
        LOGGING['loggers']['container']['level'] = 'DEBUG'
    config.dictConfig(LOGGING)

    containers_config = decoding_fn(args.config)
    conductor_config = AnsibleContainerConductorConfig(list_to_ordereddict(containers_config))

    logger.debug('Starting Ansible Container Conductor: %s', args.command, services=conductor_config.services)
    getattr(core, 'conductorcmd_%s' % args.command)(
        args.engine,
        args.project_name,
        conductor_config.services,
        volume_data=conductor_config.volumes,
        repository_data=conductor_config.registries,
        **params)
