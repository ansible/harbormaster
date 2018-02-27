Accessing Roles
===============

.. contents:: Topics


From the file system
--------------------

Ansible Container provides the ability to add local roles to the Conductor container, and make them available to the ``build`` process,  by using the ``--roles-path`` 
option.

For example, if roles are locally installed in ``/etc/ansible/roles``, the following will make the roles available inside the Conductor container:

.. code-block:: console

    $ ansible-container build --roles-path /etc/ansible/roles

In ``container.yml``, refer to roles by name. For example, if the role ``apache`` is installed in ``/etc/ansible/roles``
locally, then the following will execute the role during ``build``: 

.. code-block:: yaml

    version: '2'
    services:
      web:
        roles:
        - apache

Settings
````````

In addition to the command line option, ``roles_path`` can also be defined within ``container.yml``. Specifically, it can be defined as part of the ``conductor`` options within the ``settings`` section, as depicted in the following example:

.. code-block:: yaml

    version: '2'
    settings:
      conductor:
        base: 'centos:7'
        save: yes
        roles_path:
          - /etc/ansible/roles
          - /home/me/my-roles

From Galaxy and version control
-------------------------------

Ansible Container will automatically install roles included in the ``requirements.yml`` file found in the root of your project directory. If you are unfamiliar with ``requirements.yml``, see `Installing Multiple Roles From a File <http://docs.ansible.com/ansible/galaxy.html#installing-multiple-roles-from-a-file>`_.

Roles are installed to ``/etc/ansible/roles`` on the Conductor container. To run an installed role, simply reference it by name in ``container.yml``.


Installing roles
----------------

For convenience, the ``install`` command can be used to add roles from Galaxy to your project. The process will start a ``conductor`` container, download the role, add a service entry to the ``container.yml`` file, and add the role to the ``requirements.yml`` file.

Because a ``conductor`` container is required to perform the install, you'll need to have run the ``build`` command at least once prior to running ``install`` to insures there is a ``condcutor`` image available.

After ``install`` completes, run the ``build`` process to include the roles within the conductor image. By itself, the ``install`` process takes care of the admin activities of updating ``container.yml`` and ``requirements.yml``, but it does not create a new ``conductor`` image. You'll need to run the ``build`` command to update the conductor image prior to executing the ``run`` or ``deploy`` commands.

.. note::

    After performing an ``install``, do not include the ``--devel`` option on the subsequent run of the ``build`` command. Using the ``--devel`` option causes the ``build`` process to bypass building a new ``conductor`` image, which means the newly installed roles won't be available.

For additional information, visit :doc:`the install reference </reference/install>`.
