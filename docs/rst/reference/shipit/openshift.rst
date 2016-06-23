openshift
=========

.. program:: ansible-container shipit openshift

The ``ansible-container shipit openshift`` command creates an Ansible playbook and role to deploy your
application on OpenShift. The playbook and role are created in the ansible directory. The name of the playbook
is *shipit_openshift.yml*, and the name of the role is *<project_name>_openshift* and can be found in the
roles directory.

.. option:: --save-config

In addition to creating the playbook and role, creates a *shipit_config/openshift* directory and writes out each
JSON config file used to create the openshift services, routes and deployments for your application.

.. option:: --url <url>

The URL of the container image registry from which the cluster should pull images. By default, this is
the public Docker registry.

.. option:: --username <username>

The username to use when logging into the registry.

.. option:: --email <email>

The email address associated with your username in the registry.

.. option:: --password <password>

The password used to authenticate your user with the registry.

.. option:: --namespace <namespace>

A namespace within the registry. The namespace is prepended to the name of image. By default this is the username.

.. option:: --push-from <registry name>

A name defined in the *registries* key within container.yml. Use in place of --url and --namespace.






