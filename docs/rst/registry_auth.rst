Registry Authentication
=======================

Pushing Images
''''''''''''''

When pushing images with Ansible Container you can authenticate with the registry by passing your credentials using the
``--username`` and ``--password`` options. On successful authentication your credentials are encrypted and stored in
``~/.docker/config.json``, exactly as if you had authenticated using ``docker login``.

Each time images are pushed to the registry Ansible Container needs to know the URL of the registry and the namespace of the
repository. This information can be passed using the ``--push-to`` option. For example:


.. code-block:: console

    $ ansible-container push --push-to https://gcr.io/example-project

For convenience, the ``--push-to`` option can also be a registry name defined in ``container.yml``. For example:

.. code-block:: yaml

    registries:
      google:
        url: https://gcr.io
        namespace: example-project

The above defines a registry called *google*. The *url* property is required. The namespace is optional. If a namespace
is not provided, Ansible Container will attempt to default it to your registry username.

When a registry is defined in ``container.yml``, the name can be passed using the ``--push-to`` option. For example, to push to the
*google* registry defined in ``container.yml`` use the following:

.. code-block:: console

    $ ansible-container push --push-to google

.. note::

    No credentials are stored in ``container.yml``. You still need to authenticate with the registry each time you push
    images or allow your credentials to be stored in ``~/.docker/config.json``.

