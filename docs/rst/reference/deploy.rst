deploy
======

.. program:: ansible-container deploy

The ``deploy`` command pushes images to a remote registry, and generates an Ansible playbook that can be used to deploy the application to a cloud platform.

The cloud platform is determined by the engine used to generate the deployment. Supported engines include: docker, k8s, and openshift. The default is docker.
Use the ``--engine`` option to choose the engine.

The ``deploy`` command maps your ``container.yml`` file to a cloud configuration, depending on the engine. See the :doc:`../../container_yml/reference`
for details on how directives are mapped, and for cloud specific options.

The playbook name will match the name of the project, and have a ``.yml`` extension. The playbook is created in in the ``ansible-deployment`` directory, which will be 
created automatically. Use the *deployment_output_path* option in the *settings* section of ``container.yml`` to write the playbook to a different directory.

.. note::

    For K8s and OpenShift, the generated playbook requires the ``ansible.kubernetes-modules`` role, which is automatically installed to ``ansible-deployment/roles``.
    It contains the K8s and OpenShift modules, and by referencing the role in the generated playbook, subsequent tasks and roles can access the modules.

    For more information about the role, visit `ansible/ansible-kubernetes-modules <https://github.com/ansible/ansible-kubernetes-modules>`_.


Before ``deploy`` executes, the conductor container is started, and images are pushed to a registry. If you don't wish to push images, but intend to use images
local to the cluster, use the ``--local-images`` option.

Use the ``--push-to`` option to specify the registry where images will be pushed. Pass either a registry name defined in the *registries* section
of ``container.yml``, or pass a URL.

If using the URL form, include the namespace. For example: ``registry.example.com:5000/myproject``. If a namespace is not provided,
the default namespace for the engine will be used. In the case of docker, the default is the project name. In the case of k8s and openshift, the *k8s_namespace* defined
in the *settings* section of ``container.yml`` will be used. If that's not defined, the project name will be used.

.. option:: --help

Display usage help.

.. option:: --engine

Specify the deployment engine. The selected engine will be used to generate the Ansible playbook for deploying the application to the corresponding platform.
Valid engines include: docker, k8s, and openshift, with the default engine being docker.

.. option:: --local-images

Use images directly from the local image cache managed by the Docker daemon. Prevents images from being automatically pushed.

.. option:: --push-to

Pass either a name defined in the *registries* key within container.yml, or the URL to the registry.

If passing a URL, you can include the namespace. For example: ``registry.example.com:5000/myproject``. If the namespace is not included, the default namespace
for the engine will be used. For the docker engine, the default namespace is the project name. For k8s and openshift, the *k8s_namespace*
value will be used from the *settings* section of ``container.yml``. If the value is not set, then the project name will be used.

When passing a registry name defined in the *registries* section of ``container.yml``, set the *namespace* as an attribute of the registry.

If no ``--push-to`` option is passed, and the ``--local-images`` option is not passed, then the default registry will be used. The current default is
set to ``https://index.docker.io/v1/``.

.. option:: --with-variables WITH_VARIABLES [WITH_VARIABLES ...]

Define one or more environment variables in the Ansible Builder Container. Format each variable as a key=value string.

.. option:: --with-volumes WITH_VOLUMES [WITH_VOLUMES ...]

Mount one or more volumes to the Conductor container. Specify volumes as strings using the Docker volume format.

.. option:: --roles-path LOCAL_PATH

If you have Ansible roles in a local path other than your `ansible/` directory that you wish to use, specify that path with this option.

.. option:: --username

If the registry requires authentication, pass the username.

.. option:: --password

If the registry requires authentication, pass a password. If the ``--username`` is provided without the ``--password`` option, you will
be prompted for a password.

.. option:: --email

If registry authentication requires an email address, use to pass the email address.

.. option:: --tag

Tag the images prior to pushing.
