install
=======

.. program::ansible-container build <galaxy_role>

The ``ansible-container install`` command will install a *container enabled* role as a new containerized service in your project. A *container enabled* role contains meta data that enables Ansible Container to integrate it with an existing project. The meta data can be found in the role's ``meta/container.yml`` file, and consists of service level settings such as: *expose*, *command*, *working_dir*, *entrypoint*, etc.

The ``install`` command is executed through the ``conductor`` container. In other words, prior to running ``install``, you need to run the ``build`` command to insure a ``conductor`` image exists.

The ``install`` process integrates the role into the project by modifying the project's ``container.yml`` file and adding an entry for the service, and modifying the project's ``requirements.yml`` file to include the new role. In the ``container.yml`` file, the service name is set to the role name, and a *roles* directive with the new role is added. The settings from the role's meta data are not copied into the ``container.yml`` file. Instead, at runtime, the main ``container.yml`` is aggregated with the role's ``meta/container.yml`` file to create a complete service definition. Precedence is given to the settings in the project's ``container.yml`` file.

After running the install command, run the ``build`` command to incorporate the new roles into the ``conductor`` image. The build process will install all roles listed in the project's ``requirements.yml`` file, including the new role.

.. note::

    After performing an ``install``, do not include the ``--devel`` option on the subsequent run of the ``build`` command. Using the ``--devel`` option causes the ``build`` process to bypass building a new ``conductor`` image, which means the newly installed roles won't be available.

Public *container enabled* roles can be found on the Ansible Galaxy web site, and these roles can be installed by name. For example, to install the *solr* role contributed by `geerlingguy <https://ansible.galaxy.com/geerlingguy.com>`_, the command is:

.. code-block:: yaml

    $ ansible-container install geerlingguy.solr

The ``ansible-container install`` command takes the same role name options as the ``ansible-galaxy install`` command. In other words, it accepts the following:

.. code-block:: yaml

   $ ansible-container install role_name(s)[,version] | scm+role_repo_url[,version] | tar_file(s)
