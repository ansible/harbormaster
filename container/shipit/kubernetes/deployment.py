
# -*- coding: utf-8 -*-

from __future__ import absolute_import


import logging
import re
import shlex

from collections import OrderedDict
from six import string_types

from ..base_engine import BaseShipItObject

logger = logging.getLogger(__name__)

DOCKER_VOL_PERMISSIONS = ['rw', 'ro', 'z', 'Z']


class Deployment(BaseShipItObject):

    def _get_template_or_task(self, request_type="task"):
        templates = []
        for name, service in self.config.get('services', {}).items():
            new_template = self._create(name,request_type, service)
            if new_template:
                templates.append(new_template)
        return templates

    def _create(self, name, request_type, service):
        '''
        Creates a deployment template or playbook task
        :param request_type:
        '''

        container, volumes, pod = self._service_to_container(name, service, request_type=request_type)
        labels = dict(
            app=self.project_name,
            service=name
        )

        if request_type == 'config':
            state = 'present'
            if pod.get('state'):
                state = pod.pop('state')

            if state != 'absent':
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
                            )
                        ),
                        replicas=1,
                        strategy=dict(
                            type='RollingUpdate'
                        )
                    )
                )
                if volumes:
                    template['spec']['template']['spec']['volumes'] = volumes
                if pod:
                    for key, value in pod.items():
                        if key == 'replicas':
                            template['spec'][key] = value
        else:
            template = dict(
                kube_deployment=OrderedDict(
                    deployment_name=name,
                    labels=labels.copy(),
                    replace=True,
                    containers=[container],
                )
            )
            if volumes:
                template['kube_deployment']['volumes'] = volumes
            if pod:
                template['kube_deployment'].update(pod)

        return template

    def _service_to_container(self, name, service, request_type="task"):
        '''
        Turn a service into a container and set of volumes. Maps Docker run directives
        to the Kubernetes container spec: http://kubernetes.io/docs/api-reference/v1/definitions/#_v1_container

        :param name:str: Name of the service
        :param service:dict: Configuration
        :param request_type: task or config
        :return: (container, volumes, pod)
        '''

        container = OrderedDict(
            name=name,
            securityContext=dict()
        )
        volumes = []
        pod = {}

        IGNORE_DIRECTIVES = [
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
                if isinstance(value, string_types):
                    container['args'] = shlex.split(value)
                else:
                    container['args'] = value
            elif key == 'container_name':
                    container['name'] = value
            elif key == 'entrypoint':
                if isinstance(value, string_types):
                    container['command'] = shlex.split(value)
                else:
                    container['command'] = value
            elif key == 'environment':
                expanded_vars = self._expand_env_vars(value)
                if request_type == 'config':
                    container['env'] = expanded_vars
                else:
                    container['env'] = self._env_vars_to_task(expanded_vars)
            elif key in ('ports', 'expose'):
                if not container.get('ports'):
                    container['ports'] = []
                self._get_ports(value, request_type, container['ports'])
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
        if service.get('options', {}).get('kube'):
            for key, value in service['options']['kube'].items():
                if key == 'seLinuxOptions':
                    container['securityContext']['seLinuxOptions'] = value
                elif key == 'runAsNonRoot':
                    container['securityContext']['runAsNonRoot'] = value
                elif key == 'runAsUser':
                    container['securityContext']['runAsUser'] = value
                elif key == 'replicas':
                    pod['replicas'] = value
                elif key == 'state':
                    pod['state'] = value

        return container, volumes, pod

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
                if re.match(r'\$', source):
                    # Source is an environment var. Skip for now.
                    continue
                elif re.match(r'[~./]', source):
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

    def _get_ports(self, ports, request_type, existing_ports):
        '''
        Determine the list of ports to expose from the container, and add to existing ports.

        :param: ports: list of port mappings
        :param: type: 'config' or 'task'
        :param: existing_ports: list of existing or already discovered ports
        :return: None
        '''
        for port in ports:
            if ':' in port:
                parts = port.split(':')
                if not self._port_exists(parts[1], existing_ports):
                    if request_type == 'config':
                        existing_ports.append(dict(containerPort=int(parts[1])))
                    else:
                        existing_ports.append(int(parts[1]))
            else:
                if not self._port_exists(port, existing_ports):
                    if request_type == 'config':
                        existing_ports.append(dict(containerPort=int(port)))
                    else:
                        existing_ports.append(int(port))

    @staticmethod
    def _port_exists(port, ports):
        found = False
        for p in ports:
            if isinstance(p, dict) and p.get('containerPort') == int(port):
                found = True
                break
            elif isinstance(p, int) and p == int(port):
                found = True
                break
        return found

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

    @staticmethod
    def _expand_env_vars(env_variables):
        '''
        Turn container environment attribute into dictionary of name/value pairs.

        :param env_variables: container env attribute value
        :type env_variables: dict or list
        :return: dict
        '''
        results = []
        if isinstance(env_variables, dict):
            for key, value in env_variables.items():
                results.append({u'name': key, u'value': value})
        elif isinstance(env_variables, list):
            for envvar in env_variables:
                parts = envvar.split('=', 1)
                if len(parts) == 1:
                    results.append({u'name': parts[0], u'value': None})
                elif len(parts) == 2:
                    results.append({u'name': parts[0], u'value': parts[1]})
        return results
