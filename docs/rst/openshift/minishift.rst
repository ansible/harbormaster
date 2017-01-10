Minishift
=========

This guide will help you install and configure `Minishift <https://github.com/minishift/minishift>`_ for use with Ansible Container.

.. contents:: Topics

The minishift-up-role
---------------------

Use the `minishift-up-role <https://galaxy.ansible.com/chouseknecht/minishift-up-role>`_ to install Minishift, and create a local VM that hosts an OpenShift cluster and Docker Engine.

Specficially, the role performs the following tasks:

- Downloads and installs the latest Minishift
- Downloads and installs the OpenShift client
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

**OSX**

If you're running on a Mac, you'll need the following installed:

- `homebrew <https://brew.sh>`_ 
- `Ansible 2.1+ <https://docs.ansible.com>`_

**Linux**

For Linux platforms, have the following installed:

- KVM installed and working. The role installs the Docker Machine driver for KVM, but it assumes KVM is already installed, and working.
- Ansible 2.2+


**Fedora**

If you're running on Fedora, Ansible requires the following packages:

- python2-dnf
- libselinux-python

Install the role
----------------

Use the Ansible Galaxy client, which comes bundled with Ansible, to install the role. If you're not familiar with installing roles, start by establishing a local directory where roles will be installed and executed. The following example creates the directory ``roles`` in your home directory, and then adds ``ANSIBLE_ROLES_PATH=~/roles`` to the login script, ``.bashrc``:

.. code-block:: bash

    # Set your home directory as the working directory
    $ cd ~

    # Create the roles directory
    $ mkdir roles

    # Define ANSIBLE_ROLES_PATH in your login script
    $ echo "export ANSIBLE_ROLES_PATH=~/roles" >>.bashrc

.. NOTE::

    The login script name will vary by platform and shell. Use the script that matches your environment.

Now open a new terminal window or tab to create a new session and execute the login script, and then check that *ANSIBLE_ROLES_PATH* is defined:

.. code-block:: bash

    # Check the environment for our new variable 
    $ env | grep ANSIBLE_ROLES

    ANSIBLE_ROLES_PATH=/home/your_username/roles

To install the role to your new ``~/roles`` directory, run the following:

.. code-block:: bash

    # Install the role
    $ ansible-galaxy install chousekncht.minishift-up-role

Run the role
------------

Now that the role is installed, you can execute it using the included playbook. Use the following commands to copy the playbook to your home directory, review the defaults, and execute it:

.. code-block:: bash

    # Set your home directory as the working directory
    $ cd ~ 

    # Copy the included playbook
    $ cp ./roles/chouseknecht.minishift-up-role/files/minishift-up.yml . 

The ``minishift-up.yml`` playbook contains the following:

.. code-block:: bash

    ---
    - name: Install minishift
      hosts: localhost
      connection: local
      gather_facts: yes
      roles:
        - role: chouseknecht.minishift-up-role
          minishift_repo: minishift/minishift
          minishift_github_url: https://api.github.com/repos
          minishit_release_tag_name: "v1.0.0-beta.1"
          minishift_dest: /usr/local/bin
          minishift_force_install: yes
          minishift_volume:
            name: pv0001
            path: /data/pv0001/
            size: 5Gi
          minishift_restart: yes
          minishift_delete: no
          minishift_start_options:
          - insecure-registry 172.30.0.0/16
          - insecure-registry minishift
          - iso-url https://github.com/minishift/minishift-centos-iso/releases/download/v1.0.0-alpha.1/minishift-centos.iso
          openshift_repo: openshift/origin
          openshift_client_dest: /usr/local/bin
          openshift_force_client_install: yes

By default it will install release 'v1.0.0-beta.1' of Minishift to ``/usr/local/bin``, overwriting any previous installation, and shutting down any existing instance of the Minishift VM. It will download the latest relase of ``oc``, the OpenShift client, to ``/usr/local/bin``. 

After downloading and installing the Minishift and OpenShift tools, it executes ``minishift start`` passing as parameters any values in the *minishift_start_options* role parameter. And once the instance is up and runnning, it creates a persistent volume for the OpenShift cluster, with the storage path set to ``/data/pv0001/`` inside the VM.     

You can impact these actions by changing the role parameter values. For more information about the parameters, view the role's `README <https://github.com/chouseknecht/minishift-up-role>`_ file.

After reviewing the role parameters, use the following to run the role:

.. code-block:: bash

   # Run the minishift role
   $ ansible-playbook minishift-up-role.yml --ask-sudo-pass

Post Installation
-----------------

Add client tools to your PATH 
`````````````````````````````

By default the ``oc`` and ``minishift`` binary files are installed to ``/usr/local/bin``, which is *generally* included in the the environment PATH variable. If for some reason that is not the case, or the binaries were installed to a different location, modify your login script, and add the appropriate directory to the PATH variable.

Install and configure Docker locally
````````````````````````````````````

You'll want to have Docker installed locally, outside of the Minishift instance. During development, if you plan to use a container to *watch* for changes on the local file system, it's better to run such a container outside of Minishift using the local Docker daemon. When simulating production or deploying the app to the OpenShift instance, then it makes sense to use the Docker daemon running inside the Minishift instance. However, you'll still need to run Docker commands, such as ``docker ps`` or ``docker images``, from outside of the Minishift instance.

After installing Docker Engine on a Fedora or RHEL platform, modify ``/etc/sysconfig/docker`` so that it doesn't automatically set the value of DOCKER_CERT_PATH. You'll do this by changing ``DOCKER_CERT_PATH=/etc/docker`` to the following:

.. code-block:: bash

    if [ -z "${DOCKER_CERT_PATH}" ]; then
        DOCKER_CERT_PATH=/etc/docker
    fi

Set the API version
```````````````````

After running ``eval $(minishift docker-env)`` to set your environment to use the Minishift VM's Docker daemon, you'll likely receive an API match error the first time you run a Docker command. For example:

.. code-block:: bash
    
    # Set the environment to use the Minishift VM's Docker
    $ eval $(minishift docker-env)
    
    # Check the status of running containers
    $ docker ps 

    Error response from daemon: client is newer than server (client API version: 1.23, server API version: 1.22)

To fix the error, reset the *DOCKER_API_VERSION* environment variable to match the server's API version: 

.. code-block:: bash
    
    # Set the API version
    $ export DOCKER_API_VERSION=1.22

