Container.yml Specification
===========================

The orchestration document for Ansible Container is the ``container.yml`` file. It's much like a ``docker-compose.yml``
file, defining the services that make up the application, the relationships between each, and how they can be accessed
from the outside world.

The goal for ``container.yml`` is to provide a single definition of the application that defines how to build images,
how to run in development, and how to deploy to a production cloud environment. It's one source of configuration that 
works throughout the application lifecycle.

The structure and contents of the file are based on Docker Compose, supporting versions 1 and 2. Looking at a ``container.yml``
file you will recognize it as mostly Compose with a few notable exceptions. There are directives that are not supported, 
because they do not translate to the supported clouds, and there are new directives added to support
multi-environment, and multi-cloud configurations. 

The aim of this document is to provide a complete reference to ``container.yml``.

.. contents:: Topics

Supported Directives
--------------------

.. |checkmark| unicode:: U+02713 .. check mark

The following tables provide a quick references to supported Compose directives. All of the Compose directives for
version 1, 2 and 2.1 are listed along with any directives added by Ansible Container. A |checkmark| in the *Supported?*
column indicates that the directive is supported. In some cases the directive name links to specific implementation notes
that provide details on how the directive is used.


Top level directives
--------------------

========================== ======================================================== ============
Directive                  Definition                                               Supported?
========================== ======================================================== ============
networks                   Create named, persistent networks
:ref:`registries`          Registry definitions                                     |checkmark|
:ref:`services <services>` Services included in the app                             |checkmark|
:ref:`settings <settings>` Project level configuration settings.                    |checkmark|
version                    Specifiy the version of Compose, '1' or '2'              |checkmark|
:ref:`top-volumes`         Create named, persistent volumes. The syntax differs     |checkmark|
                           from the Docker specification.
:ref:`top-secrets`         Define secrets using Ansible vault variables.            |checkmark|
========================== ======================================================== ============

.. _settings:

Settings
--------

The ``settings`` section is an optional dictionary, or mapping, of project level configuration settings. The following 
settings are supported: 

====================== =====================================================================
Directive              Definition                                              
====================== =====================================================================
project_name           Set the name of the project. Defaults to the basename of the project 
                       directory. For built services, project_name is concatenated with
                       service name to form the built image name.

:ref:`conductor`       Configuration options for the conductor container.

deployment_output_path The deployment_output_path is mounted to the Conductor container,
                       and the ``run`` and ``deployment`` commands then write generated
                       Ansible playbooks to it. Defaults to ``./ansible-deployment``.

:ref:`k8s_auth`        When deploying to K8s or OpenShift, provide API authentication
                       details.

:ref:`k8s_namespace`   When deploying to a K8s or OpenShift cluster, set the namespace, or
                       project name in which to deploy the application
vars_files             List of variable files to use for Jinja2 template rendering while
                       parsing ``container.yml``

vault_files            List of Ansible vault files, where each entry is a file path.
                       Files are decrypted in the conductor at playbook runtime, making
                       variables available to playbooks and roles.

vault_password_file    Path to a file containing a clear text password that can be used to
                       decrypt any vault files.
====================== =====================================================================

Example
```````

The following is a simple example of a ``settings`` section found in a ``container.yml`` file:

.. code-block:: yaml

    version: '2'
    settings:
      conductor:
        base: 'ubuntu:xenial'
      project_name: myproject

      k8s_namespace:
        name: 'example'
        description: 'Best example ever!'
        display_name: 'Example'

      k8s_auth:
        config_file: /etc/k8s/dev_config
    services:
    ...    

Implementation
``````````````

Some of the options within ``settings`` take a dictionary, or mapping, of multiple options. The following provides further
information for these options:

.. _conductor:

conductor
.........

Configuration options for the Conductor container.

====================== =======================================================================
Directive              Definition
====================== =======================================================================
base                   Base image for the conductor. The Conductor container does the heavy
                       lifting, and provides a portable Python runtime for building your
                       target containers. It should be derived from the same distribution from
                       which you're building the services.

roles_path             Specify a local path containing Ansible roles.

volumes                Provide a list of volumes to mount.

environment            List or mapping of environment variables.
====================== =======================================================================

.. _k8s_auth:

k8s_auth
........	

The ``k8s_auth`` directive takes a dictionary, or mapping, of options that provide details for 
authenticating with the K8s or OpenShift API during the ``run`` command. The following options 
are supported:

====================== =====================================================================
Directive              Definition                                              
====================== =====================================================================
config_file            Path to a K8s config file. Defaults to ${HOME}/.kube/config. If 
                       no other options are supplied, the config file will be used to 
                       authenticate with the cluster API.

context                Name of a context found in the config file. 

host                   URL for accessing the API.

api_key                A valid API authentication token.                       

ssl_ca_cert            Path to a CA certificate file.

cert_file              Path to a certificate file.

key_file               Path to a key file.

verify_ssl             Boolean, indicating if SSL certs should be validated.
====================== =====================================================================

.. _k8s_namespace:

k8s_namespace
.............

Used to set the namespace, or project name, in which the application will be deployed on the cluster.
Specifically, values set here will be passed to the ``k8s_namespace``, or ``openshift_project`` module,
within the Ansible playbook generated by the ``run`` and ``deploy`` commands. 

Expects a dictionary, or mapping, with the following attributes:

====================== =====================================================================
Directive              Definition                                              
====================== =====================================================================
name                   The name of the namespace or project. If not provided, defaults to 
                       the ``project_name``. 

description            A description of the project. Supported only by OpenShift.

display_name           A title, or more formal name, displayed in the OpenShift console. 
                       Supported only by OpenShift.
====================== =====================================================================


.. _services:

Services
--------

The ``services`` section is a dictionary, or mapping, of service name to service settings. For example, the following defines 
two services, ``web`` and ``db``:

.. code-block:: yaml

    version: '2'
    services:
      web:
        from: centos:7
        command: [nginx]
        entrypoint: [/usr/bin/entrypoint.sh]
        ports:
          - 8000:8000
        roles:
          - nginx-server
     db:
       from: 'openshift/postgresql:latest'
       expose:
         - 5487
 
The following table details the attributes, or settings, that can be defined for a service. Only those
with a checkmark in the *Supported* column can be used.  

===================== ======================================================== ============
Directive             Definition                                               Supported?
===================== ======================================================== ============
build                 Run Dockerfile based build
:ref:`build_over`     Service level directives that apply only in container
                      build time                                               |checkmark|
cap_add               Add container capabilities
cap_drop              Drop container capabilities
command               Command executed by the container at startup             |checkmark|
containers            List of containers comprising the service. Use to deploy
                      multiple containers to a single pod. See :doc:`pods`     |checkmark|
container_name        Custom container name
cpuset                CPUs in which to allow execution
cpu_shares            CPU shares (relative weight)
cpu_quota             Limit the CPU CFS (Completely Fair Scheduler) quota
devices               Map devices
:ref:`depends_on`     Express dependency between services                      |checkmark|
:ref:`dev_over`       Service level directives that apply only in development
dns                   Custom DNS servers
dns_search            Custom DNS search
domainname            Set the FQDN
enable_ipv6           Enable IPv6 networking
entrypoint            Override the default entrypoint                          |checkmark|
env_file              Add environment variables from a file
environment           Add environment variables                                |checkmark|
:ref:`expose`         Expose ports internally to other containers              |checkmark|
extends               Extend another service, in the current file or another,
                      optionally overriding configuration
external_links        Link to containers started outside this project
:ref:`extra_hosts`    Add hostname mappings                                    |checkmark|
from                  The base image to start from                             |checkmark|
hostname              Set the container hostname
ipc                   Configure IPC settings
isolation             Specify the container's isolation technology
:ref:`k8s`            k8s engine directives                                    |checkmark|
labels                Add meta data to the container                           |checkmark|
:ref:`links`          Link services                                            |checkmark|
link_local_ips        List of special, external IPs to link to
logging               Logging configuration
log_driver            Specify a log driver (V1 only)
log_opt               Specify logging options as key:value pairs (V1 only)
mac_address           Set the mac address
mem_limit             Memory limit
memswap_limit         Total memory limit (memory + swap)
net                   Network mode (V1 only)
network_mode          Network mode
networks              Networks to join
:ref:`openshift`      openshift engine directives                              |checkmark|
pid                   Sets the PID mode to the host PID mode, enabling between
                      container and host OS
:ref:`ports`          Expose ports externally to the host                      |checkmark|
privileged            Run in privileged mode                                   |checkmark|
read_only             Mount the container's file system as read only           |checkmark|
restart               Restart policy to apply when a container exits           |checkmark|
:ref:`top-secrets`    Define secrets using Ansible vault                       |checkmark|
security_opt          Override default labeling scheme
shm_size              Size of /dev/shm
stdin_open            Keep stdin open                                          |checkmark|
tty                   Allocate a psuedo-tty
stop_signal           Sets an alternative signal to stop the container
tmpfs                 Mount a temporary volume to the container                |checkmark|
ulimits               Override the default ulimit
user                  Username or UID used to execute internal container       |checkmark|
                      processes
:ref:`volumes`        Mounts paths or named volumes                            |checkmark|
volume_driver         Specify a volume driver
:ref:`volumes_from`   Mount one or more volumes from one container into        |checkmark|
                      another
working_dir           Path to set as the working directory                     |checkmark|
===================== ======================================================== ============

Implementation
``````````````

The following provides details about how specific directives are implemented.

.. _build_over:

build_overrides
.............

Use for directives that should only be applied during the execution of the ``build`` command. For example,
consider the following ``container.yml`` file:

.. code-block:: yaml

    version: '2'
    services:
      web:
        from: centos:7
        command: [nginx]
        entrypoint: [/usr/bin/entrypoint.sh]
        ports:
          - 8000:8000
        build_overrides:
          command: /usr/sbin/init
          user: root
          working_dir: /somepath
          environment:
            - container: docker


In this example, when ``ansible-container build`` is executed, the options found in *build_overrides* will
take effect, and the building container will run command ``/usr/sbin/init`` rather than default ``sh -c "while true; do sleep 1; done``, have extra environment variables ``container=docker`` mapped to the container's environment and the container's working directory will be ``/somepath``.

The ``run`` and ``deploy`` commands ignore *build_overrides*. When ``run`` or ``deploy`` executes, the container will not run the command or use environment variables specified in ``build_overrides`` directive.

Supported directives in ``build_overrides`` are ``command``, ``user``, ``working_dir``, ``privileged`` and ``environment``

.. _depends_on:

depends_on
..........

Express a dependency between services, causing services to be started in order. Supported by ``build`` and ``run`` commands,
but will be ignored by ``deploy``.

.. _dev_over:

dev_overrides
.............

Use for directives that should only be applied during the execution of the ``run`` command, or development mode. For example,
consider the following ``container.yml`` file:

.. code-block:: yaml

    version: '2'
    services:
      web:
        from: centos:7
        command: [nginx]
        entrypoint: [/usr/bin/entrypoint.sh]
        ports:
          - 8000:8000
        dev_overrides:
          ports:
            - 8888:8000
          volumes:
            - ${PWD}:/var/lib/static


In this example, when ``ansible-container run`` is executed, the options found in *dev_overrides* will
take effect, and the running container will have its port 8000 mapped to the host's port 8888, and the host's working
directory will be mounted to '/var/lib/static' in the container.

The ``build`` and ``deploy`` commands ignore *dev_overrides*. When ``build`` executs, the running container
does not have the host's working directory mounted, and the container port 8000 is mapped to the host's port 8000. And
likewise, the ``deploy`` command will create a service using port 8000, and will not create any volumes for the container.

.. _expose:

expose
......

For the ``build`` and ``run`` commands, this exposes ports internally, allowing the container to accept requests from other
containers.

In the cloud, an exposed port translates to a service, and ``deploy`` will create a service for each exposed port. The cloud
service will have the same name as the ``container.yml`` service, will listen on the specified port, and forward requests
to the same port on the pod.

.. _extra_hosts:

extra_hosts
...........

For ``build`` and ``run``, adds a hosts entry to the container.

In the cloud, ``deploy`` will create an External IP service. See `Kubernetes external IPs <http://kubernetes.io/docs/user-guide/services/#external-ips for details>`_
for details.

.. _links:

links
.....

Links allow containers to communicate directly without having to define a network, and this is supported by the ``build``
and ``run`` commands.

In the cloud, *links* are not supported, and so they will be ignored by ``deploy``. However, containers can communicate
using services, so to enable communication between two containers, add the *expose* directive. See *expose* above.

.. _k8s:

k8s
...

Specify directives specific to the ``k8s`` engine. View :ref:`k8s_openshift_options` for a reference of available directives.


.. _openshift:

openshift
.........

Specify directives specific to the ``openshift`` engine. View :ref:`k8s_openshift_options` for a reference of available directives.

.. _ports:

ports
.....

Connects ports from the host to the container, allowing the container to receive external requests. This is supported by
the ``build`` and ``run`` commands.

The ``deploy`` command supports it as well by mapping the same functionality to the cloud. In the case of Kubernetes it creates
a load balanced service that accepts external requests on the host port and relays them to the pod, which contains the
container, on the container port. In the case of OpenShift it creates a route and service, where the route accepts external
requests on the host port, and relays them to a service listening on the container port, which relays them to a pod also on
the container port.

.. _registries:

registries
..........

Define registries that can be used by the ``push`` and ``deploy`` commands. For each registry, provide a *url*, an optional
*namespace*, and an optional *repository_prefix*. For both *namespace* and *repository_prefix*, if a value is not provided, the project
name is used.

The following is an example taken from a ``container.yml`` file:

.. code-block:: yaml

    ...
    registries:
      google:
        url: https://gcr.io
        namespace: my-project
      openshift:
        url: https://local.openshift
        namespace: my-project
        repository_prefix: foo
        pull_from_url: http://172.30.1.1:5000

The ``deploy`` command will automatically push images before generating the deployment Ansible playbook. Use the ``--push-to`` option
to specify the registry to which images will be pushed. For example:

.. code-block:: bash

    # Push images and generate the deployment playbook
    $ ansible-container deploy --push-to openshift

In the above example, images will be pushed to *https://local.openshift*. Each image will result in a repository name
of *foo-<service-name>*, where *foo* is the *repository_prefix* value for the *openshift* registry. For example, suppose the project
included a service named *web*. Its image would be pushed to a repository named *foo-web*

Use the ``pull_from_url`` attribute, if the URL for pushing images differs from the URL used to pull images. When using a registry hosted
on the cluster, it's possible that the DNS name or IP address used to access the registry from outside the cluster differs from that used
inside the cluster. In that case, set the ``url`` to the external address, the one used to push images, and set the ``pull_from_url`` to
the address used inside the cluster to pull images.

The ``push`` command can also be used to push images directly, and bypass the generation of a deployment playbook. The following will
push images to the *google* registry:

.. code-block:: bash

     # Push images
     $ ansible-container push --push-to google

.. _volumes:

volumes
.......

Supported by ``run`` and ``deploy`` commands. The volumes directive mounts host paths or named volumes to the container.
In version 2 of compose a named volume must be defined in the :ref:`top-level volumes directive <top-volumes>`. In version 1, if a named volume does
not exist, it is automatically created.

.. _volumes_from:

volumes_from
............

Mount all the volumes from another service or container. Supported by ``build`` and ``run`` commands, but not supported
in the cloud, and thus ignored by ``deploy``.


.. _k8s_openshift_options:

k8s and openshift options
-------------------------

When using the ``k8s`` and ``openshift`` engines, the following commands are available for managing cluster objects:

 - deploy
 - restart
 - run
 - stop
 - destroy

To impact how objects are created, a ``k8s`` or ``openshift`` section can be added to a specific service, and to a named volume within the top-level volumes directive. The following presents an``openshift`` example:


.. code-block:: yaml

    version: '2'
    services:
      web:
        from: centos:7
        command: [nginx]
        entrypoint: [/usr/bin/entrypoint.sh]
        ports:
          - 8000:8000
        volumes:
            - static-content:/var/www/static
        dev_overrides:
          ports:
            - 8888:8000
          volumes:
            - $PWD:/var/www/static
            - /home/myuser/directory-on-the-host:/var/www/static2
        openshift:
          state: present
          service:
            force: false
          deployment:
            force: false
            replicas: 2
            security_context:
              run_as_user: root
            strategy:
              type: Rolling
              rolling_params:
                timeout_seconds: 120
                max_surge: "20%"
                max_unavailable: "10%"
                pre: {}
                post: {}
          routes:
          - port: 8443
            tls:
            termination: passthrough
            force: false

     volumes:
       static-content:
         openshift:
            state: present
            force: false
            access_modes:
            - ReadWriteOnce
            requested_storage: 5Gi


Service level directives
````````````````````````

The following directives can be added to a ``k8s`` or ``openshift`` section within a service:

======================== ======================================================================================================
Directive                Definition
======================== ======================================================================================================
state                    Set to *present*, if the service should be deployed to the cluster, or *absent*, if it should not.
                         Defaults to *present*.
:ref:`service_sub`       Adds a mapping of Service object attributes.
:ref:`deployment_sub`    Adds a mapping of Deployment (or DeploymentConfig for OpenShift) object attributes.
:ref:`route_sub`         Adds a mapping of OpenShift Route object attributes.
======================== ======================================================================================================

.. _service_sub:

service
.......

Service objects expose container ports based on the ``expose`` and ``ports`` directives defined on the service. The ``expose`` directive will result in a Service exposing ports internally, enabling containers to communicate with one another, and ``ports`` will result in a service exposing ports externally, enabling access from outside of the cluster.

Any valid attributes of a Service object can be added to the ``service`` subsection, where they'll be passed through to the resulting Service definition. The only requirement is that attributes be added in snake_case, rather than camelCase. The following demonstrates setting *cluster_ip*, *load_balancer_ip*, *type*, and *annotations*:

.. code-block:: yaml

    openshift:
      service:
        force: false
        cluster_ip: 10.0.171.239
        load_balancer_ip: 78.11.24.19
        type: LoadBalancer
        metadata:
          annotations: service.beta.kubernetes.io/aws-load-balancer-ssl-cert: arn:aws:acm:us-east-1:123456789012:certificate/12345678-1234-1234-1234-123456789012

By default, existing objects are patched when attributes differ from those specified in ``container.yml``. The patch process is additive, meaning that array and dictionary type values are added to rather than replaced. To override this behavior, and force an update of the object, set the ``force`` option to *true*.

.. _deployment_sub:

deployments
...........

Container objects are created by way of Deployments (or Deployment Configs on OpenShift), and each service will be translated into a Deployment that creates and manages the container.

Any valid attributes of a Deployment object can be added to the ``deployment`` subsection, where they'll be passed through to the resulting Deployment definition. The only requirement is that attributes be added in snake_case, rather than camelCase.

For example, the following shows setting *replicas*, *security_context*, *strategy*, and *triggers*:

.. code-block:: yaml

    openshift:
      deployment:
        force: false
        replicas: 2
        security_context:
          run_as_user: root
        strategy:
          type: Rolling
          rolling_params:
            timeout_seconds: 120
            max_surge: "20%"
            max_unavailable: "10%"
            pre: {}
            post: {}
        triggers:
        - type: "ImageChange"
          image_change_params:
            automatic: true
            from:
              kind: "ImageStreamTag"
              name: "test-mkii-web:latest"
            container_names:
              - "web"

By default, existing objects are patched when attributes differ from those specified in ``container.yml``. The patch process is additive, meaning that array and dictionary type values are added to rather than replaced. To override this behavior, and force an update of the object, set the ``force`` option to *true*.

.. _route_sub:

routes
......

Route objects are used by OpenShift to expose services externally, and Ansible Container generates routes based on the ``ports`` directive of a service.

Consider the following service defined in ``container.yml``:

.. code-block:: yaml

    services:
      web:
        from: centos:7
        entrypoint: ['/usr/bin/entrypoint.sh']
        working_dir: /
        user: apache
        command: [/usr/bin/dumb-init, httpd, -DFOREGROUND]
        ports:
        - 8000:8080
        - 4443:8443

For each port in the set of defined ``ports``, a Route object is generated, and the above will generate the following routes:

.. code-block:: yaml

    apiVersion: v1
    kind: Route
    metadata:
      name: web-8000
      namespace: test-mkii
      labels:
        app: test-mkii
        service: web
      spec:
        to:
          kind: Service
          name: web
        port:
          targetPort: port-8000-tcp

.. code-block:: yaml

    apiVersoin: v1
    kind: Route
    metadata:
      name: web-4443
      namespace: test-mkii
      labels:
        app: test-mkii
        service: web
      spec:
        to:
          kind: Service
          name: web
        port: 4443

To add additional options, such as configuring TLS, add the options to the service level `k8s` or `openshift`, as in the following example:

.. code-block:: yaml

    services:
      web:
        from: centos:7
        entrypoint: ['/usr/bin/entrypoint.sh']
        working_dir: /
        user: apache
        command: [/usr/bin/dumb-init, httpd, -DFOREGROUND]
        ports:
        - 8000:8080
        - 4443:8443
        openshift:
          routes:
          - port: 4443
            tls:
              termination: edge
              key: |-
                -----BEGIN PRIVATE KEY-----
                [...]
                -----END PRIVATE KEY-----
              certificate: |-
                -----BEGIN CERTIFICATE-----
                [...]
                -----END CERTIFICATE-----
              caCertificate: |-
                -----BEGIN CERTIFICATE-----
                [...]
                -----END CERTIFICATE-----
            force: false

Notice that ``routes`` is a list. To set the route attributes for a specific port, add a new entry to the list, and set the ``port`` to the host or external port value.

The host port value comes from the ``ports`` directive set at the service level, where a port is in the Docker format of ``host_port:container_port``. Looking back at the first example, the ``web`` service publishes container port 8443 to host port 4443, and thus the route port will be 4443.

With the new options, the route for port 4443 will be updated with the following:

.. code-block:: yaml

    apiVersoin: v1
    kind: Route
    metadata:
      name: web-4443
      namespace: test-mkii
      labels:
        app: test-mkii
        service: web
    spec:
      to:
        kind: Service
        name: web
      port: 4443
      tls:
        termination: edge
        key: |-
          -----BEGIN PRIVATE KEY-----
          [...]
          -----END PRIVATE KEY-----
        certificate: |-
          -----BEGIN CERTIFICATE-----
          [...]
          -----END CERTIFICATE-----
        caCertificate: |-
          -----BEGIN CERTIFICATE-----
          [...]
          -----END CERTIFICATE-----

.. _top-volumes:

Volumes
```````

For Docker, the service level ``volumes`` directive works as expected. The top-level ``volumes`` directive, however, has been modified slightly. The following example ``container.yml`` shows the
three forms of the service level ``volumes`` directive, and the new top-level ``volumes`` format:

.. code-block:: yaml

    version: '2'
    services:
      web:
        from: centos:7
        entrypoint: [/usr/bin/entrypoint.sh]
        working_dir: /
        user: apache
        command: [/usr/bin/dumb-init, httpd, -DFOREGROUND]
        ports:
        - 8000:8080
        - 4443:8443
        roles:
        - apache-container
        volumes:
          - /Users/chouseknecht/projects/test-mkii/static:/var/www/static
          - static-content:/var/www/static2
          - /var/www/static3

    volumes:
      static-content:
        docker: {}
        k8s:
          force: false
          state: present
          access_modes:
          - ReadWriteOnce
          requested_storage: 1Gi
          metadata:
            annotations: 'volume.beta.kubernetes.io/mount-options: "discard"'

For K8s and OpenShift, each of the volumes in the list of volumes for the ``web`` service are handled as follows. The host path volume, the first volume in the list, results in the
creation of a host path volume on the cluster, provided the feature has been enabled, and the path is available to the cluster. This type of volume works well in a development environment where the
cluster is running in a virtual machine, and the host path is shared with the virtual machine.

A path only volume, the third volume in the list, results in an `emptyDir <http://kubernetes.io/docs/user-guide/volumes/#emptydir>`_. And finally, a named volume, the second volume in the list,
results in the creation of a persistent volume claim (PVC).

The top-level directive is organized by volume name. In this case, a volume named ``static-content`` is mounted to the container as ``/var/www/static2``. The definition of the named volume is
found in the top-level ``volumes`` directive, under the same name. Here specific options are organized by container engine. In this case, there are no options for ``docker``, and several
options for ``openshift``.

Ansible Container follows the `Portable Configuration pattern <http://kubernetes.io/docs/user-guide/persistent-volumes/#writing-portable-configuration>`_,
which means:

- It does not create persistent volumes
- It does create persistent volume claims.

During deployment, the ``static-content`` volume definition generates a PVCs, which is then referenced by name in a container volume definitions. The container volume definition simply mounts the
PVC by name to a path within the container, in this case the path is ``/var/www/static2``.

In the top-level ``volumes`` directive for``docker``, valid attributes include: driver, driver_opts and external. For additional information about Docker volumes see Docker's
`volume configuration reference <https://docs.docker.com/compose/compose-file/#volume-configuration-reference>`_.

For ``openshift`` and ``k8s``, the following options are available:

======================== ========================================================================================================================
Directive                Definition
======================== ========================================================================================================================
metadata                 Provide a metadata mapping, as depicted above. In general, the only mapping value provided here would be
                         ``annotations``.
access_modes             A list of valid `access modes <http://kubernetes.io/docs/user-guide/persistent-volumes/#access-modes>`_.
match_labels             A mapping of key:value pairs used to filter matching volumes.
match_expressions        A list of expressions used to filter matching volumes.
                         See `Persistent Volume Claims <https://kubernetes.io/docs/concepts/storage/persistent-volumes/#persistentvolumeclaims>`_
                         for additional details.
requested_storage        The amount of storage being requested. Defaults to 1Gi.
                         See `compute resources <http://kubernetes.io/docs/user-guide/compute-resources/>`_ for abbreviations.
======================== ========================================================================================================================

.. _top-secrets:

Secrets
-------

Use this top-level directive to define secrets, and set their values through variables defined in an Ansible vault file. The secret values will be determined during ``run`` playbook execution, or when the playbook generated by the ``deploy`` process is executed. In both cases, decryption is handled exclusively by ``ansible-playbook``.

When used in conjunction with the Docker engine, secrets are exposed to containers as volumes mounted to ``/run/secrets``. They can also be used with the K8s and OpenShift engines to create secret objects on the cluster.

The top-level secrets directive creates a mapping, as illustrated by the following ``container.yml``:

.. code-block:: yaml

    version: '2'

    settings:

      vault_files:
        - vault.yml

    services:
      web:
        ...
        secrets:
          web_secret:  # the source of the secret, defined in top-level secrets
            docker:
              - web_secret_password  # Short form

              - source: web_secret_username   # Or, alternatively, the long form
                target: web_username
                uid: '1000'
                gid: '1001'
                mode: 0440

            openshift:
              - mount_path: /etc/foo  # mount as a volume
                read_only: true

              - env_variable: WEB_PASSWORD   # Expose the password as an environment variable
                key: password
    secrets:
      web_secret:
        password: web_password   # variable defined in vault
        username: web_username
      postgres:
        username: db_username
        password: db_password

The top-level mapping associates secret names with variables defined in a vault file. So given the above mapping, the following ``vault.yml`` file will provide the expected variables:

.. code-block:: yaml

    ---
    web_username: apache
    web_password: opensesame!
    db_username:  postgres
    db_password:  $password!

Notice the vault variable names are not written as template strings in ``container.yml``. In other words, they're not bracketed with ``{{ }}``. This is because vault files are not decrypted until playbook runtime, which means the values are only available during ``run`` playbook execution. During the ``run`` command, a playbook is generated, and vault variable names are written as template strings.

When used with the Docker engine, the ``run`` command flattens the above structure, creating key=value pairs. For example, ``web_secrets`` becomes ``web_secrets_password`` and ``web_secrets_username``. The above will be translated into the following:

.. code-block:: yaml

    services:
      web:
        ...
        volumes:
          - test-secrets_secrets:/run/secrets:ro
        secrets:
          - web_secret_password
          - source: web_secret_username
            target: web_username
            uid: '1000'
            gid: '1001'
            mode: 0440
    secrets: &id002
      web_secret_password:
        external: true
    version: '3.1'
    volumes:
      test-secrets_secrets:
        external: true

In order to provide external secrets through Docker compose, secrets are decrypted and written to a named Docker volume, and the volume is then bind mounted to the container at `/run/secrets`.

The OpenShift and K8s engines will transform the above ``container.yml`` into the following templates taken from the generated deployment playbook:

.. code-block:: yaml

    apiVersion: v1
    kind: Secret
    metadata:
        name: web_secret
        namespace: test-secrets
    type: Opaque
    data:
        password: '{{ web_password | b64encode }}'


    apiVersion: v1
    kind: deployment_config
    metadata:
        name: web
        labels:
            app: test-secrets
            service: web
        namespace: test-secrets
    spec:
        template:
            metadata:
                labels:
                    app: test-secrets
                    service: web
            spec:
                containers:
                  - name: web
                    securityContext: {}
                    state: present
                    volumeMounts:
                      - readOnly: true
                        mountPath: /etc/foo
                        name: web_secret
                    env:
                      - valueFrom:
                            secretKeyRef:
                                name: web_secret
                                key: password
                        name: WEB_PASSWORD
                    ...
                volumes:
                  - secret:
                        secretName: web_secret
                    name: web_secret

Vault files
```````````

Vault files can be provided using the following options:

  - A list of file paths using the ``vault_files`` directing in ``settings``. For example:

    .. code-block:: yaml

        version: '2'

        settings:

           vault_files:
             - vault.yml
             - other-vault.yml

  - Using the ``--vault-file`` option on the command line.


Vault password
``````````````

As mentioned above, vault files are decrypted when the ``run`` process executes the generated playbook. In order to decrypt the files, a password is required, and it can be supplied by using the following options:

  - A text file, using the ``vault_password_file`` directive in ``settings`` to supply the path to the file. For example:

    .. code-block:: yaml

        version: '2'
        settings:

          vault_files:
            - vault.yml

          vault_password_file: '~/.vault-password'

  - On the command line by using the ``--vault-password-file`` option.

  - Or, enter it at a prompt by using the ``--ask-vault-pass`` option.

The ``deploy`` command generates a playbook, but does not execute it. The generated playbook references vault files using the ``vars_files`` directive, and it will also contain references to variable names that are expected to be defined within the vault files. When you're ready to run the playbook, use the ``ansible-playbook`` options ``--vault-password-file`` or ``--ask-vault-pass``, or set``ANSIBLE_VAULT_PASSWORD_FILE`` in the environment.

