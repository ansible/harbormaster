
# -*- coding: utf-8 -*-

from __future__ import absolute_import


import logging
import re
import shlex

from collections import OrderedDict

logger = logging.getLogger(__name__)

DOCKER_VOL_PERMISSIONS = ['rw', 'ro', 'z', 'Z']

class Deployment(object):

    def __init__(self, config=None, project_name=None):
        self.project_name = project_name
        self.config = config

    def get_template(self, service_names=None):
        return self._get_template_or_task(request_type="config", service_names=service_names)

    def get_task(self, service_names=None):
        return self._get_template_or_task(request_type="task", service_names=service_names)

    def _get_template_or_task(self, request_type="task", service_names=None):
        templates = []
        for name, service in self.config.get('services', {}).items():
            if request_type == 'task':
                new_template = self._create_task(name, service)
            elif request_type == 'config':
                new_template = self._create_template(name, service)
            templates.append(new_template)
        return templates

    def _create_template(self, name, service):
        '''
        Creates a deployment template from a set of services. Each service becomes a container
        defined within the replication controller.
        '''
        name = "%s-%s" % (self.project_name, name)
        container, volumes = self._service_to_container(name, service, type="config")
        labels = dict(
            app=self.project_name,
            service=name
        )
        template = dict(
            apiVersion="extensions/v1beta1",
            kind="Deployment",
            metadata=dict(
                name=name,
                labels=labels
            ),
            spec=dict(
                template=dict(
                    metadata=dict(
                        labels=labels.copy()
                    ),
                    spec=dict(
                        containers=[container],
                        volumes=volumes
                    )
                ),
                replicas=1,
                strategy=dict(
                    type='RollingUpdate'
                )
            )
        )
        return template

    def _create_task(self, name, service):
        '''
        Generates an Ansible playbook task.

        :param service:
        :return:
        '''

        container, volumes = self._service_to_container(name, service, type="task")
        name = "%s-%s" % (self.project_name, name)
        labels = dict(
            app=self.project_name,
            service=name
        )
        template = dict(
            kube_deployment=OrderedDict(
                deployment_name=name,
                labels=labels.copy(),
                containers=[container],
                volumes=volumes
            )
        )
        return template

    def _service_to_container(self, name, service, type="task"):
        '''
        Turn a service into a container and set of volumes. Maps Docker run directives
        to the Kubernetes container spec: http://kubernetes.io/docs/api-reference/v1/definitions/#_v1_container

        :param name:str: Name of the service
        :param service:dict: Configuration
        :param type: task or config
        :return: (container, volumes)
        '''

        #TODO: add ability to influence pod configuration (i.e. return a pod dict)

        container = OrderedDict(
            name=name,
            securityContext=dict()
        )
        volumes = []

        IGNORE_DIRECTIVES = [
            'aliases',
            'build',
            'expose',
            'labels',
            'links',
            'cgroup_parent',
            'dev_options',
            'devices',
            'depends_on',
            'dns',
            'dns_search',
            'env_file',        # TODO: build support for this?
            'user',            # needs to map to securityContext.runAsUser, which requires a UID
            'extends',
            'extrenal_links',
            'extra_hosts',
            'ipv4_address',
            'ipv6_address'
            'labels',
            'links',           # TODO: Add env vars?
            'logging',
            'log_driver',
            'lop_opt',
            'net',
            'network_mode',
            'networks',
            'restart',         # for replication controller, should be Always
            'pid',             # could map to pod.hostPID
            'security_opt',
            'stop_signal',
            'ulimits',
            'cpu_shares',
            'cpu_quota',
            'cpuset',
            'domainname',
            'hostname',
            'ipc',
            'mac_address',
            'mem_limit',
            'memswap_limit',
            'shm_size',
            'tmpfs',
            'options',
            'volume_driver',
            'volumes_from',   #TODO: figure out how to map?
        ]

        DOCKER_TO_KUBE_CAPABILITY_MAPPING=dict(
            SETPCAP='CAP_SETPCAP',
            SYS_MODULE='CAP_SYS_MODULE',
            SYS_RAWIO='CAP_SYS_RAWIO',
            SYS_PACCT='CAP_SYS_PACCT',
            SYS_ADMIN='CAP_SYS_ADMIN',
            SYS_NICE='CAP_SYS_NICE',
            SYS_RESOURCE='CAP_SYS_RESOURCE',
            SYS_TIME='CAP_SYS_TIME',
            SYS_TTY_CONFIG='CAP_SYS_TTY_CONFIG',
            MKNOD='CAP_MKNOD',
            AUDIT_WRITE='CAP_AUDIT_WRITE',
            AUDIT_CONTROL='CAP_AUDIT_CONTROL',
            MAC_OVERRIDE='CAP_MAC_OVERRIDE',
            MAC_ADMIN='CAP_MAC_ADMIN',
            NET_ADMIN='CAP_NET_ADMIN',
            SYSLOG='CAP_SYSLOG',
            CHOWN='CAP_CHOWN',
            NET_RAW='CAP_NET_RAW',
            DAC_OVERRIDE='CAP_DAC_OVERRIDE',
            FOWNER='CAP_FOWNER',
            DAC_READ_SEARCH='CAP_DAC_READ_SEARCH',
            FSETID='CAP_FSETID',
            KILL='CAP_KILL',
            SETGID='CAP_SETGID',
            SETUID='CAP_SETUID',
            LINUX_IMMUTABLE='CAP_LINUX_IMMUTABLE',
            NET_BIND_SERVICE='CAP_NET_BIND_SERVICE',
            NET_BROADCAST='CAP_NET_BROADCAST',
            IPC_LOCK='CAP_IPC_LOCK',
            IPC_OWNER='CAP_IPC_OWNER',
            SYS_CHROOT='CAP_SYS_CHROOT',
            SYS_PTRACE='CAP_SYS_PTRACE',
            SYS_BOOT='CAP_SYS_BOOT',
            LEASE='CAP_LEASE',
            SETFCAP='CAP_SETFCAP',
            WAKE_ALARM='CAP_WAKE_ALARM',
            BLOCK_SUSPEND='CAP_BLOCK_SUSPEND'
        )

        for key, value in service.items():
            if key in IGNORE_DIRECTIVES:
                pass
            elif key == 'cap_add':
                if not container['securityContext'].get('Capabilities'):
                    container['securityContext']['Capabilities'] = dict(add=[], drop=[])
                for cap in value:
                    if DOCKER_TO_KUBE_CAPABILITY_MAPPING[cap]:
                        container['securityContext']['Capabilities']['add'].append(DOCKER_TO_KUBE_CAPABILITY_MAPPING[cap])
            elif key == 'cap_drop':
                if not container['securityContext'].get('Capabilities'):
                    container['securityContext']['Capabilities'] = dict(add=[], drop=[])
                for cap in value:
                    if DOCKER_TO_KUBE_CAPABILITY_MAPPING[cap]:
                        container['securityContext']['Capabilities']['drop'].append(DOCKER_TO_KUBE_CAPABILITY_MAPPING[cap])
            elif key == 'command':
                if isinstance(value, basestring):
                    container['args'] = shlex.split(value)
                else:
                    container['args'] = value
            elif key == 'container_name':
                    container['name'] = value
            elif key == 'entrypoint':
                if isinstance(value, basestring):
                    container['command'] = shlex.split(value)
                else:
                    container['command'] = value
            elif key == 'environment':
                expanded_vars = self._expand_env_vars(value)
                if type == 'config':
                    container['env'] = expanded_vars
                else:
                    container['env'] = self._env_vars_to_task(expanded_vars)
            elif key == 'ports':
                container['ports'] = self._get_ports(value, type)
            elif key == 'privileged':
                container['securityContext']['privileged'] = value
            elif key == 'read_only':
                container['securityContext']['readOnlyRootFileSystem'] = value
            elif key == 'stdin_open':
                container['stdin'] = value
            elif key == 'volumes':
                vols, vol_mounts = self._kube_volumes(value)
                if vol_mounts:
                    container['volumeMounts'] = vol_mounts
                if vols:
                    volumes += vols
            elif key == 'working_dir':
                container['workingDir'] = value
            else:
                container[key] = value

        # Translate options:
        if service.get('options'):
            for key, value in service['options'].items():
                if key == 'kube_seLinuxOptions':
                    container['SecurityOptions']['seLinuxOptions'] = value
                elif key == 'kube_runAsNonRoot':
                    container['SecurityOptions']['runAsNonRoot'] = value
                elif key == 'kube_runAsUser':
                    container['SecurityOptions']['runAsUser'] = value

        return container, volumes

    @staticmethod
    def _get_ports(ports, type):
        '''
        Convert docker ports to list of kube containerPort
        :param ports:
        :type ports: list
        :return: list
        '''
        results = []
        for port in ports:
            if ':' in port:
                parts = port.split(':')
                if type == 'config':
                    results.append(dict(containerPort=int(parts[1])))
                else:
                    results.append(int(parts[1]))
            else:
                if type == 'config':
                    results.append(dict(containerPort=int(port)))
                else:
                    results.append(int(port))
        return results

    def _kube_volumes(self, docker_volumes):
        '''
        Given an array of Docker volumes return a set of volumes and a set of volumeMounts

        :param volumes: array of Docker volumes
        :return: (volumes, volumeMounts) - where each is a list of dicts
        '''
        volumes = []
        volume_mounts = []
        for vol in docker_volumes:
            logger.debug("volume: %s" % vol)
            source = None
            destination = None
            permissions = None
            if ':' in vol:
                pieces = vol.split(':')
                if len(pieces) == 3:
                    source, destination, permissions = vol.split(':')
                elif len(pieces) == 2:
                    if pieces[1] in DOCKER_VOL_PERMISSIONS:
                        destination, permissions = vol.split(':')
                    else:
                        source, destination = vol.split(':')
            else:
                destination = vol
            logger.debug("source: %s destination: %s permissions: %s" % (source, destination, permissions))
            named = False
            if destination:
                # slugify the destination to create a name
                name = re.sub(r'\/', '-', destination)
                name = re.sub(r'-', '', name, 1)

            if source:
                if re.match(r'[~./]', source):
                    # Source is a host path. We'll assume it exists on the host machine?
                    volumes.append(dict(
                        name=name,
                        hostPath=dict(
                            path=source
                        )
                    ))
                else:
                    # Named volume. The volume should be defined elsewhere.
                    name = source
                    named = True
            else:
                # Volume with no source, a.k.a emptyDir
                volumes.append(dict(
                    name=name,
                    emptyDir=dict(
                        medium=""
                    ),
                ))

            if not named:
                volume_mounts.append(dict(
                    mountPath=destination,
                    name=name,
                    readOnly=(True if permissions == 'ro' else False)
                ))

        return volumes, volume_mounts

    @staticmethod
    def _env_vars_to_task(env_vars):
        '''
        Turn list of vars into a dict for playbook task.
        :param env_variables: list of dicts
        :return: dict
        '''
        result = dict()
        for var in env_vars:
            result[var['name']] = var['value']
        return result

    def _expand_env_vars(self, env_variables):
        '''
        Turn containier environment attribute into dictionary of name/value pairs.

        :param env_variables: container env attribute value
        :type env_variables: dict or list
        :return: dict
        '''
        def r(x, y):
            if re.match('shipit_', x, flags=re.I):
                return dict(name=re.sub('^shipit_', '', x, flags=re.I), value=self._resolve_resource(y))
            return dict(name=x, value=y)

        results = []
        if isinstance(env_variables, dict):
            for key, value in env_variables.items():
                results.append(r(key, value))
        elif isinstance(env_variables, list):
            for envvar in env_variables:
                parts = envvar.split('=')
                if len(parts) == 1:
                    results.append(dict(name=re.sub('^shipit_', '', parts[0], flags=re.I), value=None))
                elif len(parts) == 2:
                    results.append(r(parts[0], parts[1]))
        return results

    def _resolve_resource(self, path):
        result = path
        if '/' in path:
            # TODO - support other resource types?
            res_type, res_name = path.split('/')
            if res_type == 'service':
                parts = res_name.split(':')
                result = unicode("{{ %s_service.spec.clusterIP }}:%s" % (parts[0].replace('-', '_'), parts[1]))
        return result
