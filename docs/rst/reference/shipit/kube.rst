kube
====

.. program:: ansible-container shipit kube

The ``ansible-container shipit kube`` command creates in the ``ansible`` directory an Ansible
playbook and role to deploy your application on Kubernetes. The name of the playbook is
*shipit-kubernetes.yml*, and the name of the role is *roles/<project_name>-kubernetes*.

The ``shipit`` commands maps your ``container.yml`` file to a cloud configuration. See the :doc:`../../container_yml/reference`
for details on how directives are mapped and for available Cloud options.


.. note::
    
    The generated role requires that ``kubectl``, the Kubernetes client tool, be installed.
    
.. note::

    Before ``shipit`` starts, the build container is started, and Ansible Playbook is
    invoked with the ``--list-hosts`` option to inspect ``main.yml`` and return the list of hosts
    it touches. Supply the same ``--roles-path``, ``--with-volumes`` and ``--with-variables`` options
    passed to the``build`` command to ensure that ``main.yml`` can be parsed and interpreted.

.. option:: --help

Display usage help.

.. option:: --save-config

In addition to creating the playbook and role, creates a *shipit_config/kubernetes* directory and writes out each
JSON config file used to create the Kubernetes services and deployments for your application.

.. option:: --pull-from <registry name>

Pass either a name defined in the *registries* key within container.yml or the actual URL the cluster will use to
pull images. If passing a URL, an example would be 'registry.example.com:5000/myproject'.

.. option:: --with-variables WITH_VARIABLES [WITH_VARIABLES ...]

**New in version 0.2.0**

Define one or more environment variables in the Ansible Builder Container. Format each variable as a
key=value string.

.. option:: --with-volumes WITH_VOLUMES [WITH_VOLUMES ...]

**New in version 0.2.0**

Mount one or more volumes to the Ansible Builder Container. Specify volumes as strings using the Docker
volume format.

If ``--with-volumes`` was used during the `build` process to access roles or includes, then pass the same option to the `shipit` command so that ``main.yml`` can be parsed. 

.. option:: --roles-path LOCAL_PATH

**New in version 0.2.0**

If you have Ansible roles in a local path other than your `ansible/` directory that you wish to use, specify that path with this option.

If ``--roles-path`` was used during the `build` process, then pass the same option to the `shipit` command so that ``main.yml`` can be parsed. 

.. option:: --local-images

**New in version 0.3.0**

Use images directly from the local image cache managed by the Docker daemon. Prevents the automatic use of the default registry URL.



