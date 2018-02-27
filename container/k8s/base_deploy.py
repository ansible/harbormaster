# -*- coding: utf-8 -*-
from __future__ import absolute_import

import copy
import os
import re
import shlex
import string_utils

from abc import ABCMeta, abstractmethod

from six import iteritems, string_types, add_metaclass
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from container.utils.visibility import getLogger
logger = getLogger(__name__)

"""
Translate the container.yml derived config into an Ansible playbook/role
to deploy the services.
"""


@add_metaclass(ABCMeta)
class K8sBaseDeploy(object):

    DEFAULT_API_VERSION = 'v1'
    CONFIG_KEY = 'k8s'

    def __init__(self, services=None, project_name=None, volumes=None, secrets=None, auth=None, namespace_name=None,
                 namespace_description=None, namespace_display_name=None):
        self._services = services
        self._project_name = project_name
        self._namespace_name = namespace_name
        self._namespace_description = namespace_description
        self._namespace_display_name = namespace_display_name
        self._volumes = volumes
        self._secrets = secrets
        self._auth = auth

    @property
    def auth(self):
        return self._auth

    @auth.setter
    def auth(self, auth):
        self._auth = auth

    @property
    def namespace_name(self):
        return self._namespace_name

    @namespace_name.setter
    def namespace_name(self, namespace_name):
        self._namespace_name = namespace_name

    @property
    def namespace_description(self):
        return self._namespace_description

    @namespace_description.setter
    def namespace_description(self, namespace_description):
        self._namespace_description = namespace_description

    @property
    def namespace_display_name(self):
        return self._namespace_display_name

    @namespace_display_name.setter
    def namespace_display_name(self, namespace_display_name):
        self._namespace_display_name = namespace_display_name

    @abstractmethod
    def get_namespace_task(self, state='present', tags=[]):
        pass

    def get_services_templates(self):
        """ Generate a service configuration """
        def _create_service(name, service):
            template = CommentedMap()
            state = service.get(self.CONFIG_KEY, {}).get('state', 'present')
            if state == 'present':
                ports = self.get_service_ports(service)
                if ports:
                    template['apiVersion'] = self.DEFAULT_API_VERSION
                    template['kind'] = 'Service'
                    template['force'] = service.get(self.CONFIG_KEY, {}).get('service', {}).get('force', False)
                    labels = CommentedMap([
                        ('app', self._namespace_name),
                        ('service', name)
                    ])
                    template['metadata'] = CommentedMap([
                        ('name', name),
                        ('namespace', self._namespace_name),
                        ('labels', copy.deepcopy(labels))
                    ])
                    template['spec'] = CommentedMap([
                        ('selector', copy.deepcopy(labels)),
                        ('ports', ports)
                    ])
                    # Translate options:
                    if service.get(self.CONFIG_KEY):
                        for key, value in iteritems(service[self.CONFIG_KEY]):
                            if key == 'service':
                                for service_key, service_value in iteritems(value):
                                    if service_key == 'force':
                                        continue
                                    elif service_key == 'metadata':
                                        self.copy_attribute(template, service_key, service_value)
                                    else:
                                        self.copy_attribute(template['spec'], service_key, service_value)
            return template

        templates = CommentedSeq()
        if self._services:
            for name, service in iteritems(self._services):
                if service.get('containers'):
                    ports = []
                    expose = []
                    for container in service['containers']:
                        if container.get('ports'):
                            ports += container['ports']
                        if container.get('expose'):
                            expose += container['expose']
                    if ports or expose:
                        composite = {
                            'ports': ports,
                            'expose': expose
                        }
                        if service.get(self.CONFIG_KEY):
                            composite[self.CONFIG_KEY] = copy.deepcopy(service[self.CONFIG_KEY])
                        template = _create_service(name, composite)
                        if template:
                            templates.append(template)
                else:
                    template = _create_service(name, service)
                    if template:
                        templates.append(template)

                if service.get('links'):
                    # create services for aliased links
                    for link in service['links']:
                        if ':' in link:
                            service_name, alias = link.split(':')
                            alias_config = self._services.get(service_name)
                            if alias_config:
                                new_service = _create_service(alias, alias_config)
                                if new_service:
                                    templates.append(new_service)
        return templates

    def get_service_tasks(self, tags=[]):
        module_name='k8s_v1_service'
        tasks = CommentedSeq()
        for template in self.get_services_templates():
            task = CommentedMap()
            task['name'] = 'Create service'
            task[module_name] = CommentedMap()
            task[module_name]['state'] = 'present'
            if self._auth:
                for key in self._auth:
                    task[module_name][key] = self._auth[key]
            task[module_name]['force'] = template.pop('force', False)
            task[module_name]['resource_definition'] = template
            if tags:
                task['tags'] = copy.copy(tags)
            tasks.append(task)
        if self._services:
            # Remove an services where state is 'absent'
            for name, service in iteritems(self._services):
                if service.get(self.CONFIG_KEY, {}).get('state', 'present') == 'absent':
                    task = CommentedMap()
                    task['name'] = 'Remove service'
                    task[module_name] = CommentedMap()
                    task[module_name]['state'] = 'absent'
                    task[module_name]['name'] = name
                    task[module_name]['namespace'] = self._namespace_name
                    if self._auth:
                        for key in self._auth:
                            task[module_name][key] = self._auth[key]
                    if tags:
                        task['tags'] = copy.copy(tags)
                    tasks.append(task)
        return tasks

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
        'defaults',        # Ignored so that playbook vars/defaults can be passed during container builds but ignored in openshift/k8s deploys
        'env_file',        # TODO: build support for this?
        'user',            # TODO: needs to map to securityContext.runAsUser, which requires a UID
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
        'restart',         # TODO: for replication controller, should be Always
        'pid',             # TODO: could map to pod.hostPID
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
        'volumes_from',   # TODO: figure out how to map?
        'from',
        'roles',
        'k8s',
        'openshift',
    ]

    DOCKER_TO_KUBE_CAPABILITY_MAPPING = dict(
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

    @abstractmethod
    def get_deployment_templates(self, default_api=None, default_kind=None, default_strategy=None, engine_state=None):

        def _service_to_k8s_container(name, config, container_name=None):
            container = CommentedMap()

            if container_name:
                container['name'] = container_name
            else:
                container['name'] = container['name'] if config.get('container_name') else name

            container['securityContext'] = CommentedMap()
            container['state'] = 'present'
            volumes = []

            for key, value in iteritems(config):
                if key in self.IGNORE_DIRECTIVES:
                    pass
                elif key == 'cap_add':
                    if not container['securityContext'].get('Capabilities'):
                        container['securityContext']['Capabilities'] = dict(add=[], drop=[])
                    for cap in value:
                        if self.DOCKER_TO_KUBE_CAPABILITY_MAPPING[cap]:
                            container['securityContext']['Capabilities']['add'].append(
                                self.DOCKER_TO_KUBE_CAPABILITY_MAPPING[cap])
                elif key == 'cap_drop':
                    if not container['securityContext'].get('Capabilities'):
                        container['securityContext']['Capabilities'] = dict(add=[], drop=[])
                    for cap in value:
                        if self.DOCKER_TO_KUBE_CAPABILITY_MAPPING[cap]:
                            container['securityContext']['Capabilities']['drop'].append(
                                self.DOCKER_TO_KUBE_CAPABILITY_MAPPING[cap])
                elif key == 'command':
                    if isinstance(value, string_types):
                        container['args'] = shlex.split(value)
                    else:
                        container['args'] = copy.copy(value)
                elif key == 'container_name':
                    pass
                elif key == 'entrypoint':
                    if isinstance(value, string_types):
                        container['command'] = shlex.split(value)
                    else:
                        container['command'] = copy.copy(value)
                elif key == 'environment':
                    expanded_vars = self.expand_env_vars(value)
                    if expanded_vars:
                        if 'env' not in container:
                            container['env'] = []

                        container['env'].extend(expanded_vars)
                elif key in ('ports', 'expose'):
                    if not container.get('ports'):
                        container['ports'] = []
                    self.add_container_ports(value, container['ports'])
                elif key == 'privileged':
                    container['securityContext']['privileged'] = value
                elif key == 'read_only':
                    container['securityContext']['readOnlyRootFileSystem'] = value
                elif key == 'stdin_open':
                    container['stdin'] = value
                elif key == 'volumes':
                    vols, vol_mounts = self.get_k8s_volumes(value)
                    if vol_mounts:
                        if 'volumeMounts' not in container:
                            container['volumeMounts'] = []

                        container['volumeMounts'].extend(vol_mounts)
                    if vols:
                        volumes += vols
                elif key == 'secrets':
                    for secret, secret_config in iteritems(value):
                        if self.CONFIG_KEY in secret_config:
                            vols, vol_mounts, env_variables = self.get_k8s_secrets(secret, secret_config[self.CONFIG_KEY])

                            if vol_mounts:
                                if 'volumeMounts' not in container:
                                    container['volumeMounts'] = []

                                container['volumeMounts'].extend(vol_mounts)

                            if vols:
                                volumes += vols

                            if env_variables:
                                if 'env' not in container:
                                    container['env'] = []

                                container['env'].extend(env_variables)
                elif key == 'working_dir':
                    container['workingDir'] = value
                else:
                    container[key] = value
            return container, volumes

        def _update_volumes(existing_volumes, new_volumes):
            existing_names = {}
            for vol in existing_volumes:
                existing_names[vol['name']] = 1
            for vol in new_volumes:
                if vol['name'] not in existing_names:
                    existing_volumes.append(vol)

        templates = CommentedSeq()
        for name, service_config in iteritems(self._services):
            containers = []
            volumes = []
            pod = {}
            if service_config.get('containers'):
                for c in service_config['containers']:
                    cname = "{}-{}".format(name, c['container_name'])
                    k8s_container, k8s_volumes, = _service_to_k8s_container(name, c, container_name=cname)
                    containers.append(k8s_container)
                    _update_volumes(volumes, k8s_volumes)
            else:
                k8s_container, k8s_volumes = _service_to_k8s_container(name, service_config)
                containers.append(k8s_container)
                volumes += k8s_volumes

            if service_config.get(self.CONFIG_KEY):
                for key, value in iteritems(service_config[self.CONFIG_KEY]):
                    if key == 'deployment':
                        for deployment_key, deployment_value in iteritems(value):
                            if deployment_key != 'force':
                                self.copy_attribute(pod, deployment_key, deployment_value)

            labels = CommentedMap([
                ('app', self._namespace_name),
                ('service', name)
            ])

            state = service_config.get(self.CONFIG_KEY, {}).get('state', 'present')
            if state == 'present':
                template = CommentedMap()
                template['apiVersion'] = default_api
                template['kind'] = default_kind
                template['force'] = service_config.get(self.CONFIG_KEY, {}).get('deployment', {}).get('force', False)
                template['metadata'] = CommentedMap([
                    ('name', name),
                    ('labels', copy.deepcopy(labels)),
                    ('namespace', self._namespace_name)
                ])
                template['spec'] = CommentedMap()
                template['spec']['template'] = CommentedMap()
                template['spec']['template']['metadata'] = CommentedMap([('labels', copy.deepcopy(labels))])
                template['spec']['template']['spec'] = CommentedMap([
                    ('containers', containers)
                ])
                # When the engine requests a 'stop', set replicas to 0, stopping all containers
                template['spec']['replicas'] = 1 if not engine_state == 'stop' else 0
                if default_strategy:
                    template['spec']['strategy'] = {}
                    for service_key, service_value in iteritems(default_strategy):
                        self.copy_attribute(template['spec']['strategy'], service_key, service_value)

                if volumes:
                    template['spec']['template']['spec']['volumes'] = volumes

                if pod:
                    for key, value in iteritems(pod):
                        if key == 'securityContext':
                            template['spec']['template']['spec'][key] = value
                        elif key != 'replicas' or (key == 'replicas' and engine_state != 'stop'):
                            # Leave replicas at 0 when engine_state is 'stop'
                            template['spec'][key] = value
                templates.append(template)
        return templates

    @abstractmethod
    def get_deployment_tasks(self, module_name=None, engine_state=None, tags=[]):
        tasks = CommentedSeq()
        for template in self.get_deployment_templates(engine_state=engine_state):
            task = CommentedMap()
            if engine_state is None:
                task_name = 'Create deployment, and scale replicas up'
            else:
                task_name = 'Stop running containers by scaling replicas down to 0'
            task['name'] = task_name
            task[module_name] = CommentedMap()
            task[module_name]['state'] = 'present'
            if self._auth:
                for key in self._auth:
                    task[module_name][key] = self._auth[key]
            task[module_name]['force'] = template.pop('force', False)
            task[module_name]['resource_definition'] = template
            if tags:
                task['tags'] = copy.copy(tags)
            tasks.append(task)
        if engine_state != 'stop':
            for name, service_config in iteritems(self._services):
                # Remove deployment for any services where state is 'absent'
                if service_config.get(self.CONFIG_KEY, {}).get('state', 'present') == 'absent':
                    task = CommentedMap()
                    task['name'] = 'Remove deployment'
                    task[module_name] = CommentedMap()
                    task[module_name]['state'] = 'absent'
                    if self._auth:
                        for key in self._auth:
                            task[module_name][key] = self._auth[key]
                    task[module_name]['name'] = name
                    task[module_name]['namespace'] = self._namespace_name
                    if tags:
                        task['tags'] = copy.copy(tags)
                    tasks.append(task)
        return tasks

    def get_pvc_templates(self):
        def _volume_to_pvc(claim_name, claim):
            template = CommentedMap()
            template['force'] = claim.get('force', False)
            template['apiVersion'] = 'v1'
            template = CommentedMap()
            template['apiVersion'] = self.DEFAULT_API_VERSION
            template['kind'] = "PersistentVolumeClaim"
            template['metadata'] = CommentedMap([
                ('name', claim_name),
                ('namespace', self._namespace_name)
            ])
            template['spec'] = CommentedMap()
            template['spec']['resources'] = {'requests': {'storage': '1Gi'}}
            if claim.get('volume_name'):
                template['spec']['volumeName'] = claim['volume_name']
            if claim.get('access_modes'):
                template['spec']['accessModes'] = claim['access_modes']
            if claim.get('requested_storage'):
                template['spec']['resources']['requests']['storage'] = claim['requested_storage']
            if claim.get('storage_class'):
                if not template['metadata'].get('annotations'):
                    template['metadata']['annotations'] = {}
                template['metadata']['annotations']['storageClass'] = claim['storage_class']  #TODO verify this syntax
            if claim.get('selector'):
                if claim['selector'].get('match_labels'):
                    if not template['spec'].get('selector'):
                        template['spec']['selector'] = dict()
                    template['spec']['selector']['matchLabels'] = claim['match_labels']
                if claim['selector'].get('match_expressions'):
                    if not template['spec'].get('selector'):
                        template['spec']['selector'] = dict()
                    template['spec']['selector']['matchExpressions'] = claim['match_expressions']
            return template

        templates = CommentedSeq()
        if self._volumes:
            for volname, vol_config in iteritems(self._volumes):
                if self.CONFIG_KEY in vol_config:
                    if vol_config[self.CONFIG_KEY].get('state', 'present') == 'present':
                        volume = _volume_to_pvc(volname, vol_config[self.CONFIG_KEY])
                        templates.append(volume)
        return templates

    def get_pvc_tasks(self, tags=[]):
        module_name='k8s_v1_persistent_volume_claim'
        tasks = CommentedSeq()
        for template in self.get_pvc_templates():
            task = CommentedMap()
            task['name'] = 'Create PVC'
            task[module_name] = CommentedMap()
            task[module_name]['state'] = 'present'
            if self._auth:
                for key in self._auth:
                    task[module_name][key] = self._auth[key]
            task[module_name]['force'] = template.pop('force', False)
            task[module_name]['resource_definition'] = template
            if tags:
                task['tags'] = copy.copy(tags)
            tasks.append(task)
        if self._volumes:
            # Remove any volumes where state is 'absent'
            for volname, vol_config in iteritems(self._volumes):
                if self.CONFIG_KEY in vol_config:
                    if vol_config[self.CONFIG_KEY].get('state', 'present') == 'absent':
                        task = CommentedMap()
                        task['name'] = 'Remove PVC'
                        task[module_name] = CommentedMap()
                        task[module_name]['name'] = volname
                        task[module_name]['namespace'] = self._namespace_name
                        task[module_name]['state'] = 'absent'
                        if self._auth:
                            for key in self._auth:
                                task[module_name][key] = self._auth[key]
                        if tags:
                            task['tags'] = copy.copy(tags)
                        tasks.append(task)
        return tasks

    def get_secret_templates(self):
        def _secret(secret_name, secret):
            template = CommentedMap()
            template['force'] = secret.get('force', False)
            template['apiVersion'] = 'v1'
            template = CommentedMap()
            template['apiVersion'] = self.DEFAULT_API_VERSION
            template['kind'] = "Secret"
            template['metadata'] = CommentedMap([
                ('name', secret_name),
                ('namespace', self._namespace_name)
            ])
            template['type'] = 'Opaque'
            template['data'] = {}

            for key, vault_variable in iteritems(secret):
                template['data'][key] = "{{ %s | b64encode }}" % vault_variable

            return template

        templates = CommentedSeq()
        if self._secrets:
            for secret_name, secret_config in iteritems(self._secrets):
                secret = _secret(secret_name, secret_config)
                templates.append(secret)

        return templates

    def get_secret_tasks(self, tags=[]):
        module_name='k8s_v1_secret'
        tasks = CommentedSeq()

        for template in self.get_secret_templates():
            task = CommentedMap()
            task['name'] = 'Create Secret'
            task[module_name] = CommentedMap()
            task[module_name]['state'] = 'present'
            if self._auth:
                for key in self._auth:
                    task[module_name][key] = self._auth[key]
            task[module_name]['force'] = template.pop('force', False)
            task[module_name]['resource_definition'] = template
            if tags:
                task['tags'] = copy.copy(tags)
            tasks.append(task)

        return tasks

    @staticmethod
    def get_service_ports(service):
        ports = []

        def _port_in_list(host, container, protocol):
            found = [p for p in ports if p['port'] == int(host) and
                     p['targetPort'] == container and p['protocol'] == protocol]
            return len(found) > 0

        def _append_port(host, container, protocol):
            if not _port_in_list(host, container, protocol):
                ports.append(dict(
                    port=int(host),
                    targetPort=int(container),
                    protocol=protocol,
                    name='port-%s-%s' % (host, protocol.lower())
                ))

        for port in service.get('ports', []):
            protocol = 'TCP'
            if isinstance(port, string_types) and '/' in port:
                port, protocol = port.split('/')
            if isinstance(port, string_types) and ':' in port:
                host, container = port.split(':')
            else:
                host = container = port
            _append_port(host, container, protocol)

        for port in service.get('expose', []):
            protocol = 'TCP'
            if isinstance(port, string_types) and '/' in port:
                port, protocol = port.split('/')
            _append_port(port, port, protocol)

        return ports

    @staticmethod
    def expand_env_vars(env_variables):
        """ Convert service environment attribute into dictionary of name/value pairs. """
        results = []
        if isinstance(env_variables, dict):
            results = [{'name': x, 'value': env_variables[x]} for x in list(env_variables.keys())]
        elif isinstance(env_variables, list):
            for evar in env_variables:
                parts = evar.split('=', 1)
                if len(parts) == 1:
                    results.append({'name': parts[0], 'value': None})
                elif len(parts) == 2:
                    results.append({'name': parts[0], 'value': parts[1]})
        return results

    @staticmethod
    def add_container_ports(ports, existing_ports):
        """ Determine list of ports to expose at the container level, and add to existing_ports """
        def _port_exists(port, protocol):
            found = [p for p in existing_ports if p['containerPort'] == int(port) and p['protocol'] == protocol]
            return len(found) > 0

        for port in ports:
            protocol = 'TCP'
            if isinstance(port, string_types) and '/' in port:
                port, protocol = port.split('/')
            if isinstance(port, string_types) and ':' in port:
                _, port = port.split(':')
            if not _port_exists(port, protocol):
                existing_ports.append({'containerPort': int(port), 'protocol': protocol.upper()})

    DOCKER_VOL_PERMISSIONS = ['rw', 'ro', 'z', 'Z']

    @classmethod
    def get_k8s_volumes(cls, docker_volumes):
        """ Given an array of Docker volumes return a set of volumes and a set of volumeMounts """
        volumes = []
        volume_mounts = []
        for vol in docker_volumes:
            source = None
            destination = None
            permissions = None
            if ':' in vol:
                pieces = vol.split(':')
                if len(pieces) == 3:
                    source, destination, permissions = vol.split(':')
                elif len(pieces) == 2:
                    if pieces[1] in cls.DOCKER_VOL_PERMISSIONS:
                        destination, permissions = vol.split(':')
                    else:
                        source, destination = vol.split(':')
            else:
                destination = vol

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
                    source = os.path.abspath(os.path.normpath(os.path.expanduser(source)))
                    volumes.append(dict(
                        name=name,
                        hostPath=dict(
                            path=source
                        )
                    ))
                else:
                    # Named volume. A PVC *should* get created for this volume.
                    name = source
                    volumes.append(dict(
                        name=name,
                        persistentVolumeClaim=dict(
                            claimName=name
                        )
                    ))
            else:
                # Volume with no source, a.k.a emptyDir
                volumes.append(dict(
                    name=name,
                    emptyDir=dict(
                        medium=""
                    ),
                ))

            volume_mounts.append(dict(
                mountPath=destination,
                name=name,
                readOnly=(True if permissions == 'ro' else False)
            ))

        return volumes, volume_mounts

    @classmethod
    def get_k8s_secrets(cls, secret_name, secrets):
        """ Given an array of Docker secrets return a set of secrets and a set of volumeMounts """
        volume_mounts = []
        volumes = []
        environment_variables = []

        for secret_config in secrets:
            if 'mount_path' in secret_config:
                mount_path = secret_config['mount_path']
                read_only = True
                volume_name = secret_name

                if 'read_only' in secret_config:
                    read_only = secret_config['read_only']

                if 'name' in secret_config:
                    volume_name = secret_config['name']

                secret_volume = dict(secretName=secret_name)

                if 'items' in secret_config:
                    secret_volume['items'] = secret_config['items']

                volume_mounts.append(dict(
                    mountPath=mount_path,
                    name=volume_name,
                    readOnly=read_only
                ))

                volumes.append(dict(
                    name=volume_name,
                    secret=secret_volume
                ))
            elif 'env_variable' in secret_config:
                secret_key_ref=dict(
                    secretKeyRef=dict(
                        name=secret_name,
                        key=secret_config['key']
                    )
                )

                environment_variables.append(dict(
                    name=secret_config['env_variable'],
                    valueFrom=secret_key_ref
                ))

        return volumes, volume_mounts, environment_variables

    @classmethod
    def copy_attribute(cls, target, src_key, src_value):
        """ copy values from src_value to target[src_key], converting src_key and sub keys to camel case """
        src_key_camel = string_utils.snake_case_to_camel(src_key, upper_case_first=False)
        if isinstance(src_value, dict):
            if not target.get(src_key_camel):
                target[src_key_camel] = {}
            for key, value in iteritems(src_value):
                camel_key = string_utils.snake_case_to_camel(key, upper_case_first=False)
                if isinstance(value, dict):
                    target[src_key_camel][camel_key] = {}
                    cls.copy_attribute(target[src_key_camel], key, value)
                else:
                    target[src_key_camel][camel_key] = value
        elif isinstance(src_value, list):
            if not target.get(src_key_camel):
                target[src_key_camel] = []
            for element in src_value:
                if isinstance(element, dict):
                    new_item = {}
                    for key, value in iteritems(element):
                        camel_key = string_utils.snake_case_to_camel(key, upper_case_first=False)
                        cls.copy_attribute(new_item, camel_key, value)
                    target[src_key_camel].append(new_item)
                else:
                    target[src_key_camel].append(element)
        else:
            target[src_key_camel] = src_value

