shipit
======

.. program:: ansible-container shipit

The ``ansible-container shipit`` command generates an Ansible role to deploy your
project to the cloud and orchestrate the project's containers according to the directives
in the *container.yml* file.

When *shipit* executes, it will add a *roles* directory to the project's ansible directory, and within
the *roles* directory an Ansible role, where the role name is in the format *<project_name>_<shipit_engine>*.
Within the *ansible* directory it will also create a sample playbook to execute the role. The playbook name is in the
format *shipit_<shipit_engine>.yml*.

Immediately after *shipit* specify the cloud service provider to use. See engine index below for the supported *shipit*
engines.

**NOTE**: Running the *shipit* command multiple time will overwrite the *shipit_<shipit_engine>.yml* playbook
and the *<project_name>_<shipit_engine>* role. Be careful, if you modify any of the files created by *shipit*, they
will most likely be overwritten.


Dependencies
````````````

Execution of the role created by ``shipit`` depends on:

+ `Ansible <http://docs.ansible.com/ansible/intro_installation.html>`_ 2.0 or greater on the control node.

Check the dependencies of the specific shipit engine for further details.


Engine Index
````````````
.. toctree::
   :maxdepth: 1

   shipit/kube
   shipit/openshift