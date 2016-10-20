Accessing Roles
===============

.. contents:: Topics


From the file system
--------------------

Starting with version 0.2.0 Ansible Container provides the ability to add local to the Ansible Build Container
by using the ``--roles-path`` option. So if you have roles already installed on the local file system, you can simply
reference the local path for the build container to use.

For example, if roles are locally installed in ``/etc/ansible/roles``, the following will make the roles available
inside the build container:

.. code-block:: bash

    $ ansible-container build --roles-path /etc/ansible/roles

In your ``main.yml`` playbook refer to roles by name. For example, if the role ``apache`` is installed in ``/etc/ansible/roles``
locally, then the following will execute the role as part of ``main.yml``:

.. code-block:: yaml

    - name: Example play
      hosts: web
      roles:
        - name: Install apache
          role: apache

.. note::

    If using Docker Machine, be aware that mounting paths outside of the user's home directory to a container may
    require additional steps. For more details see the Docker tutorial, `Manage data in containers <https://docs.docker.com/engine/tutorials/dockervolumes/#/mount-a-host-directory-as-a-data-volume>`_.

.. note::

    If you choose to access locally installed roles using ``--roles-path``, then you must include the ``--roles-path``
    option when running the ``run``, ``push`` and ``shipit`` commands. During these operations the ``main.yml`` playbook is
    accessed using the ``--list-hosts`` option to determine the list of hosts affected by the playbook. If roles cannot be
    accessed, Ansible Playbook will fail to parse ``main.yml``.


From Galaxy and version control
-------------------------------

Starting in version 0.2.0 Ansible Container will automatically install roles included in a ``requirements.yml`` file placed in
the ``ansible`` directory. If you are unfamiliar with ``requirements.yml``, see `Installing Multiple Roles From a File <http://docs.ansible.com/ansible/galaxy.html#installing-multiple-roles-from-a-file>`_.

The default ``roles_path`` is set to ``/etc/ansible/roles`` on the build container, and roles will be installed there. No special
changes are required in ``main.yml``. To run an installed role simply refer to it by name.
