push
====

.. program:: ansible-container push

The ``ansible-container push`` command sends the latest build of your images to a container registry of your choosing. This command is analogous to ``docker push``.

Use the ``--push-to`` option to specify the registry where images will be pushed. Pass either a registry name defined in the *registries* section
of ``container.yml``, or pass a URL.

If using the URL form, include the namespace. For example: ``registry.example.com:5000/myproject``. If a namespace is not provided,
the default namespace for the engine will be used. In the case of docker, the default is the project name. In the case of k8s and openshift, the *k8s_namespace* defined
in the *settings* section of ``container.yml`` will be used. If that's not defined, the project name will be used.

The process will use registry credentials from your container engine configuration file (e.g., ${HOME}/.docker/config.json), if they exist, to authenticate with the registry.
Otherwise, you may specify a username and password on the command line using the ``--username`` and ``--password`` options. If the ``--username`` option is provided without
``--password``, you will be prompted for the password. After a successful login, the engine configuration file will be updated with the new credentials.

.. note::

    If you have a credential store service running in your local environment, and you previously logged into the registry using ``docker login``, the authentication data
    will not exist in the configuration file. Instead, it is stored in the credential store. Ansible Container will not have access to the credential store. To resolve this, remove
    the registry entry from the configuration file, and use the Ansible Container ``deploy`` or ``push`` commands to perform the authentication.


.. option:: --push-to

Pass either a name defined in the *registries* key within container.yml, or the URL to the registry.

If passing a URL, you can include the namespace. For example: ``registry.example.com:5000/myproject``. If the namespace is not included, the default namespace
for the engine will be used. For the docker engine, the default namespace is the project name. For k8s and openshift, the *k8s_namespace*
value will be used from the *settings* section of ``container.yml``. If the value is not set, then the project name will be used.

When passing a registry name defined in the *registries* section of ``container.yml``, set the *namespace* as an attribute of the registry.

If no ``--push-to`` option is passed, and the ``--local-images`` option is not passed, then the default registry will be used. The current default is
set to ``https://index.docker.io/v1/``.

.. option:: --username

If the registry requires authentication, pass the username.

.. option:: --password

If the registry requires authentication, pass a password. If the ``--username`` is provided without the ``--password`` option, you will
be prompted for a password.

.. option:: --email

If registry authentication requires an email address, use to pass the email address.

.. option:: --tag

Tag the images prior to pushing.

.. option:: --with-variables WITH_VARIABLES [WITH_VARIABLES ...]

Define one or more environment variables in the Ansible Builder Container. Format each variable as a key=value string.

.. option:: --with-volumes WITH_VOLUMES [WITH_VOLUMES ...]

Mount one or more volumes to the Conductor container. Specify volumes as strings using the Docker volume format.

.. option:: --roles-path LOCAL_PATH

If you have Ansible roles in a local path other than your `ansible/` directory that you wish to use, specify that path with this option.

