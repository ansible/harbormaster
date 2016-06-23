shipit
======

.. program:: ansible-container shipit

The ``ansible-container shipit`` command generates an Ansible role to deploy your
project to the cloud and orchestrate the project's containers according to the directives
in the *container.yml* file.

Immediately after *shipit* specify the cloud service provider. See the :ref:`shipit-engine-idx` for the supported *shipit*
engines. For example, to execute *shipit* with the Kubernetes engine:

.. code-block:: bash

   $ ansible-container shipit kube


When *shipit* executes it will add a *roles* directory to the project's ansible directory, and within
the *roles* directory an Ansible role. The role name will be in the format *<project_name>_<shipit_engine>*.
Within the *ansible* directory it will also create a sample playbook to execute the role. The playbook name will be in
the format *shipit_<shipit_engine>.yml*.


**NOTE**: Running the *shipit* command multiple times will overwrite the playbook and role for the selected engine. If
any of the files created by *shipit* were modified, those modifications will be lost.

Dependencies
````````````

Execution of the role created by ``shipit`` depends on `Ansible <http://docs.ansible.com/ansible/intro_installation.html>`_
2.0 or greater. Check the dependencies of the specific *shipit* engine for any additional dependencies.

.. _shipit-engine-idx:

Engine Index
````````````
.. toctree::
   :maxdepth: 1

   shipit/kube
   shipit/openshift