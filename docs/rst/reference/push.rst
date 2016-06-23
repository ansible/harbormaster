push
====

.. program:: ansible-container push

The ``ansible-container push`` command sends the latest build of your images
to a container registry of your choosing. This command is analogous to ``docker push``.

If you already have credentials stored in your container engine configuration for
the URL you provide, Ansible Container uses that credential during "push". Otherwise,
you may specify a username and email on the command line. Likewise, if you specify a
password, it is used as part of your credentials; otherwise, the user is prompted to type in the password.

Ansible Container performs a login for you. The credentials are stored in
your container engine's configuration for future use.

.. option:: --url <url>

The URL of the container image registry to which you wish to push. By default, this is
the public Docker registry.

.. option:: --username <username>

The username to use when logging into the registry.

.. option:: --email <email>

The email address associated with your username in the registry.

.. option:: --password <password>

The password used to authenticate your user with the registry.

.. opton:: --namespace <namespace>

A namespace within the registry. The namespace is prepended to the name of image. Defaults to username.

.. option:: --push-to <registry name>

A name defined in the *registries* key within container.yml. Use in place of --namespace and --url.





