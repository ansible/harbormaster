Ansible Container Compose Specification
=======================================

The orchestration document for Ansible Container is the ``container.yml`` file. It's much like a ``docker-compose.yml``
file, defining the services that make up the application, the relationships between each, and how they can be accessed
from the outside world.

However, the goal for ``container.yml`` is much more ambitious. It is to provide a single definition of the application
that builds and deploys in development and in a production cloud environment. One source of configuration that works
throughout the application lifecycle.

The structure and contents of the file are based on Docker Compose, supporting versions 1 and 2. Looking at a ``container.yml``
file you will recognize it as mostly Compose with a few notable additions. There are of course directives that are not
supported, because they do not translate to the supported clouds, and directives have been added to provide support for
multiple environments and multiple clouds. So it is the aim of this document to provide a complete reference to Ansible
Container Compose, the contents of ``container.yml``.

.. contents:: Topics

Supported Directives
--------------------

.. |checkmark| unicode:: U+02713 .. check mark

The following tables provide a quick references to supported Compose directives. All of the Compose directives for
version 1, 2 and 2.1 are listed along with any directives added by Ansible Container. A |checkmark| in the *Supported?*
column indicates that the directive is supported. In some cases the directive name links to specific implementation notes
that provide details on how the directive is used.

.. note::

    Support of Compose V2 directives is new in Ansible Container 0.3.0. Earlier versions support V1 directives only.

Top level directives
````````````````````

===================== ======================================================== ============
Directive             Definition                                               Supported?
===================== ======================================================== ============
networks              Create named, persistent networks
:ref:`registries`     Registry definitions
services              Services included in the app                             |checkmark|
version               Specifiy the version of Compose, '1' or '2'              |checkmark|
volumes               Create named, persistent volumes                         |checkmark|
===================== ======================================================== ============

Service level directives
````````````````````````

===================== ======================================================== ============
Directive             Definition                                               Supported?
===================== ======================================================== ============
build                 Run Dockerfile based build
cap_add               Add container capabilities
cap_drop              Drop container capabilities
command               Command executed by the container at startup             |checkmark|
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
hostname              Set the container hostname
image                 The base image to start from                             |checkmark|
ipc                   Configure IPC settings
isolation             Specify the container's isolation technology
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
:ref:`options`        Cloud deployment directives                              |checkmark|
pid                   Sets the PID mode to the host PID mode, enabling between
                      container and host OS
:ref:`ports`          Expose ports externally to the host                      |checkmark|
privileged            Run in privileged mode                                   |checkmark|
read_only             Mount the container's file system as read only           |checkmark|
restart               Restart policy to apply when a container exits           |checkmark|
security_opt          Override default labeling scheme
shm_size              Size of /dev/shm
stdin_open            Keep stdin open                                          |checkmark|
tty                   Allocate a psuedo-tty
stop_signal           Sets an alternative signal to stop the container
tmpfs                 Mount a temporary volume to the container                |checkmark|
ulimits               Override the default ulimit
user                  Username or UID used to execute internal container       |checkmark|
                      processes
:ref: `volumes`       Mounts paths or named volumes                            |checkmark|
volume_driver         Specify a volume driver
:ref: `volumes_from`  Mount one or more volumes from one container into        |checkmark|
                      another
working_dir           Path to set as the working directory                     |checkmark|
===================== ======================================================== ============

Implementation
--------------

The following provides details about how specific directives are implemented.

.. _depends_on:

depends_on
``````````
Express a dependency between services, causing services to be started in order. Supported by ``build`` and ``run`` commands,
but will be ignored by ``shipit``.

.. _dev_over:

dev_overrides
`````````````
Use for directives that should only be applied during the execution of the ``run`` command, or development mode. For example,
consider the following ``container.yml`` file:

.. code-block:: yaml

    version: '2'
    services:
      web:
        image: centos:7
        command: [nginx]
        entrypoint: [/usr/bin/entrypoint.sh]
        ports:
          - 8000:8000
        dev_overrides:
          ports:
            - 8888:8000
          volumes:
            - ${PWD}:/var/lib/static


In this example, when ``ansible-container run`` is executed (development mode), the options found in *dev_overrides* will
take affect, and the running container will have its port 8000 mapped to the host's port 8888, and the host's working
directory will be mounted to '/var/lib/static' in the container.

The ``build`` and ``shipit`` commands completely ignore *dev_overrides*. When ``build`` is executed the running container
does not have the host's working directory mounted, and the container port 8000 is mapped to the host's port 8000. And
likewise, the ``shipit`` command will create a service using port 8000, and will not create any volumes for the container.

.. _expose:

expose
``````

For the ``build`` and ``run`` commands, this exposes ports internally, allowing the container to accept requests from other
containers.

In the cloud, an exposed port translates to a service, and ``shipit`` will create a service for each exposed port. The cloud
service will have the same name as the `container.yml` service, and it will listen on the specified port and forward requests
to the same port on the pod.

.. _extra_hosts:

extra_hosts
```````````
For ``build`` and ``run``, adds a hosts entry to the container.

In the cloud, ``shipit`` will create an External IP service. See `Kubernetes external IPs <http://kubernetes.io/docs/user-guide/services/#external-ips for details>`_
for details.

.. _links:

links
`````

Links allow containers to communicate directly without having to define a network, and this is upported by the ``build``
and ``run`` commands.

In the cloud, *links* are not supported, and so they will be ignored by ``shipit``. However, containers can communicate
using services, so to enable communication between two containers, add the *expose* directive. See *expose* above.

.. _options:

options
```````

Specify directives specific to cloud deployment. Used exclusively by the ``shipit`` command to impact how services are deployed.
View :ref:`cloud_options` for a reference of options directives.

.. _ports:

ports
`````
Connects ports from the host to the container, allowing the container to receive external requests. This is supported by
the ``build`` and ``run`` commands.

The ``shipit`` command supports it as well by mapping the same functionality to the cloud. In the case of Kubernetes it creates
a load balanced service that accepts external requests on the host port and relays them to the pod, which contains the
container, on the container port. In the case of OpenShift it creates a route and service, where the route accepts external
requests on the host port, and relays them to a service listening on the container port, which relays them to a pod also on
the container port.

.. _registries:

registries
``````````
Define registries that can be referenced by the ``push`` and ``shipit`` commands. For each registiry provide a *url* and
and optional namespace. If no namespace is provided, the username found in your .docker/config.json or specified on the
command line will be used.

The following is an example taken from a ``container.yml`` file:

.. code-block:: yaml

    registries:
      google:
        url: https://gcr.io
        namespace: my-project
      openshift
        url: https://192.168.30.14.xip.io

Use the following command to push images to the *google* registry:

.. code-block:: bash

     # Push images
     $ ansible-container push --push-to google

.. _volumes:

volumes
```````

Supported by the ``build`` and ``run`` commands. The volumes directive mounts host paths or named volumes to the container.
In version 2 of compose a named volume must be defined in the top-level volumes directive. In version 1, if a named volume does
not exist, it is automatically created.

In the cloud, host paths result in the creation of an `emptyDir <http://kubernetes.io/docs/user-guide/volumes/#emptydir>`_,
and a named volume will result in the creation of a persistent volume claim (PVC). The resulting emptyDir or PVC will then
be mounted to the container using the specified path.

Ansible Container follows the `Portable Configuration pattern <http://kubernetes.io/docs/user-guide/persistent-volumes/#writing-portable-configuration>`_,
which means:

- It does not create persistent volumes
- It does create persistent volume claims.

.. _volumes_from:

volumes_from
````````````

Mount all the volumes from another service or container. Supported by ``build`` and ``run`` commands, but not supported
in the cloud, and thus ignored by ``shipit``.


.. _cloud_options:

Cloud options
-------------

The *options* directive allows the user to impact how a service is deployed to each cloud, and thus a set of directives
can be added for each cloud. For example, the following shows directives being added for OpenShift and Kubernetes:

.. code-block:: yaml

    version: '2'
    services:
      web:
        image: centos:7
        command: [nginx]
        entrypoint: [/usr/bin/entrypoint.sh]
        ports:
          - 8000:8000
        dev_overrides:
          ports:
            - 8888:8000
          volumes:
            - ${PWD}:/var/lib/static
        options:
          kube:
            runAsUser: 997
            replicas: 2
          openshift:
            replicas: 3

.. note::

    Directives intended for OpenShift are added using an *openshift* section (or object), and a *kube* section for Kubernetes.

The following table lists the available directives:

======================== ======================================================================================================
Directive                Definition
======================== ======================================================================================================
persistent_volume_claims Define a persistent volume claim. See :ref:`pvc` for more details.

replicas                 Scale the servie by setting the number of pods to create. Defaults to 1.
runAsNonRoot             Set the runAsNonRoot option in the container's security context. Boolean. Defaults to false.
runAsUser                The UID to run the entrypoint of the container process. Defaults to user specified in image metadata,
                         if unspecified.
seLinuxOptions           Set the `seLinuxOptions <http://kubernetes.io/docs/api-reference/v1/definitions/#_v1_selinuxoptions>`_
                         in the container's security context.
state                    Set to 'absent', if the service should not be deployed to the cloud. Defaults to 'present'.
======================== ======================================================================================================

.. _pvc:

Persistent volume claims
````````````````````````

Docker named volumes map to persistent volume claims (PVCs) in the cloud. Consider the following ``container.yml``:

.. code-block:: yaml

    version: '2'
    services
      web:
        image: nginx:latest
        volumes:
          - static-files:/var/lib/nginx
      options:
        openshift:
          persistent_volume_claims:
            - volume_name: static-files
              claim_name: static-files-nginx
              access_modes:
                - ReadWriteMany

    volumes:
       static-files: {}

In the above example the Compose *volumes* directives create a named volume called *static-files*, and the Docker volume gets
created during the execution of the ``build`` and ``run`` commands. When ``shipit`` executes, it creates a volume called
*static-files* that maps to a persistent volume claim, and it creates the persistent volume claim using the parameters
specified in *options*. In this case the options are supplied for OpenShift.

The following options can be defined for a persistent volume claim:

======================== =============================================================================================================
Directive                Definition
======================== =============================================================================================================
annotations              Define a meta data annotation object. See the Class section of
                         `Persistent Volume Claims <http://kubernetes.io/docs/user-guide/persistent-volumes/#persistentvolumeclaims>`_
access_modes             A list of valid `access modes <http://kubernetes.io/docs/user-guide/persistent-volumes/#access-modes>`_.
claim_name               The meta data name to give the PVC. Required.
match_labels             Filter matching volumes by specifying labels the volume must have.
match_expressions        Filter matching volumes by specifying key, list of values, and an operator that relates the key and values.
persistent_volume_name   The name of a specific persistent volume to use.
requested_storage        The amount of storage being requested. Defaults to 1Gi.
                         See `compute resources <http://kubernetes.io/docs/user-guide/compute-resources/>`_ for abbreviations.
volume_name              The name of the Docker volume. Required.
======================== =============================================================================================================
