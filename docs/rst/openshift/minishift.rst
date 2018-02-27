Minishift
=========

This guide will help you install and configure `Minishift <https://github.com/minishift/minishift>`_ for use with Ansible Container.

.. contents:: Topics

The minishift-up-role
---------------------

Use the `minishift-up-role <https://galaxy.ansible.com/chouseknecht/minishift-up-role>`_ to install Minishift, and create a local VM that hosts an OpenShift cluster and Docker Engine.

Specficially, the role performs the following tasks:

- Downloads and installs the latest Minishift
- Copies the ``oc`` client to ``/usr/local/bin``
- Installs the Docker Machine driver
- Creates a Minishift instance 
- Grants cluster admin to the *developer* account
- Adds a persistent volume

The following platforms are supported: 

- Debian
- Red Hat
- OSX

Prerequisites 
-------------

- Prior to running the role, clear your terminal session of any DOCKER* environment variables.
- sudo access is required in order to install packages

**Mac OS**

If you're running on a Mac, you'll need the following installed:

- `homebrew <https://brew.sh>`_ 
- `Ansible 2.4+ <https://docs.ansible.com>`_

**Linux**

For Linux platforms, have the following installed:

- KVM installed and working. The role installs the Docker Machine driver for KVM, but it assumes KVM is already installed, and working.
- Ansible 2.4+


**Fedora**

If you're running on Fedora, Ansible requires the following packages:

- python2-dnf
- libselinux-python

Install the role
----------------

Use the Ansible Galaxy client, which comes bundled with Ansible, to install the role. If you're not familiar with installing roles, start by establishing a local directory where roles will be installed and executed. The following example creates the directory ``roles`` in your home directory, and then adds ``ANSIBLE_ROLES_PATH=~/roles`` to the login script, ``.bashrc``:

.. code-block:: console

    # Set your home directory as the working directory
    $ cd ~

    # Create the roles directory
    $ mkdir roles

    # Define ANSIBLE_ROLES_PATH in your login script
    $ echo "export ANSIBLE_ROLES_PATH=~/roles" >>.bashrc

.. NOTE::

    The login script name will vary by platform and shell. Use the script that matches your environment.

Now open a new terminal window or tab to create a new session and execute the login script, and then check that *ANSIBLE_ROLES_PATH* is defined:

.. code-block:: console

    # Check the environment for our new variable 
    $ env | grep ANSIBLE_ROLES

    ANSIBLE_ROLES_PATH=/home/your_username/roles

To install the role to your new ``~/roles`` directory, run the following:

.. code-block:: console

    # Install the role
    $ ansible-galaxy install chouseknecht.minishift-up-role

Run the role
------------

Now that the role is installed, you can execute it using the included playbook. Use the following commands to copy the playbook to your home directory, review the defaults, and execute it:

.. code-block:: console

    # Set your home directory as the working directory
    $ cd ~ 

    # Copy the included playbook
    $ cp ./roles/chouseknecht.minishift-up-role/minishift-up.yml . 

The ``minishift-up.yml`` playbook contains the following:

.. code-block:: yaml

    ---
    - name: Install minishift
      hosts: localhost
      connection: local
      gather_facts: yes
      roles:
      - role: chouseknecht.minishift-up-role
        minishift_repo: minishift/minishift
        minishift_github_url: https://api.github.com/repos
        minishift_release_tag_name: ""
        minishift_dest: /usr/local/bin
        minishift_force_install: yes
        minishift_restart: yes
        minishift_delete: yes
        minishift_start_options: []
        openshift_client_dest: /usr/local/bin
        openshift_force_client_copy: yes

It will install the latest ``minishift`` binary to ``/usr/local/bin``, overwriting any previous installation, and shut down and replace any existing instance of the Minishift VM. The copy of the ``oc`` binary delivered with the Minishift release will be copied to ``/usr/local/bin``. 

You can impact these actions, and how Minishift is started, by changing the role parameter values. For more information about the parameters, view the role's `README <https://github.com/chouseknecht/minishift-up-role>`_ file.

After reviewing the role parameters, use the following to run the role:

.. code-block:: console

   # Run the minishift role
   $ ansible-playbook minishift-up-role.yml --ask-become-pass

Post Installation
-----------------

Add client tools to your PATH 
`````````````````````````````

By default the ``oc`` and ``minishift`` binary files are installed to ``/usr/local/bin``, which is *generally* included in the the environment PATH variable. If for some reason that is not the case, or the binaries were installed to a different location, modify your login script, and add the appropriate directory to the PATH variable.

Enable Pushing images to Minishift
``````````````````````````````````

If you plan to build images using a Docker daemon external to Minishift, and then need to push them to the Minishift registry, you can reference the registry using ``https://local.openshift``. When you executed the role, an entry for ``local.openshift`` was added to your ``/etc/hosts`` file, and a route was created to expose the registry. To successfully access the registry with this URL, you'll need to add ``local.openshift`` and ``172.30.0.0/16`` to the list of insecure registries passed to the external Docker daemon at startup via the ``--insecure-registry`` option.




