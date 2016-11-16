Installation
============

.. contents:: Topics

.. _getting_ansible_container:

Getting Ansible Container
`````````````````````````

Prerequisites:

* Python 2.7
* `pip <https://pip.pypa.io/en/stable/installing/>`_
* `setuptools 20.0.0+ <https://pypi.python.org/pypi/setuptools>`_
* `Docker 1.11 <https://docs.docker.com/engine/installation/>`_ or access to a
  Docker daemon. If you're installing Docker Engine or accessing a remote Docker
  daemon, see :ref:`configure_docker`.

Then simply:

.. code-block:: bash

    $ sudo pip install ansible-container

If you do not have root privileges, you'll need to use a `virtualenv` to create a Python sandbox:

.. code-block:: bash

    $ virtualenv ansible-container
    $ source ansible-container/bin/activate
    $ pip install ansible-container

You'll need to run the `activate` script in each shell session prior to invoking `ansible-container`.
See `the virtualenv docs <https://virtualenv.pypa.io/en/stable/>`_ for details.

Then you can move on to :ref:`configure_docker` to work with Ansible Container.

.. _running_from_source:

Running from Source
```````````````````

If you'd like to run the bleeding edge version of Ansible Container, you can obtain it
from our Github repository.

Prerequisites:

* All of the prerequisites listed in :ref:`getting_ansible_container`
* `git <https://git-scm.com/book/en/v2/Getting-Started-Installing-Git>`_

Clone the repo:

.. code-block:: bash

    $ git clone https://github.com/ansible/ansible-container.git

We recommend that you use a Python Virtualenv to sandbox your installation.
See `the virtualenv docs <https://virtualenv.pypa.io/en/stable/>`_ for instructions.

If you just want to run ansible-container:

.. code-block:: bash

    $ cd ansible-container
    $ python ./setup.py install

Or, if you plan to help develop ansible-container:

.. code-block:: bash

    $ cd ansible-container
    $ python ./setup.py develop

If you run into the following error, you likely have an older version of setuptools installed:

.. code-block:: bash

    Traceback (most recent call last):
      File "./setup.py", line 11, in <module>
        packages=find_packages(include='container.*'),
      TypeError: find_packages() got an unexpected keyword argument 'include'

Use the following to upgrade to the latest release, and then run the install command again:

.. code-block:: bash 

    $ pip install --upgrade setuptools

You may need to run the above command with `sudo` if you're not using a `virtualenv`.

.. _configure_docker:

Configuring Docker
``````````````````
If you're using `Docker Machine <https://docs.docker.com/machine/>`_, you can skip this section. Simply ensure your
Docker Machine environment is active in your shell session.

If you're not using Docker Machine, you'll still need `Docker Engine <https://docs.docker.com/engine/installation/>`_
installed. By default, Docker Engine comes set to only listen on a UNIX socket. It is recommended that you configure
your Docker Engine for TLS-secured TCP, however it is not strictly necessary.

To use Ansible Container with Docker Engine's UNIX socket, simply ensure the ``DOCKER_HOST`` environment variable is unset.

.. _docker_engine:

Enabling TCP for Docker Engine
------------------------------
After `installing Docker engine <https://docs.docker.com/engine/installation/>`_ the daemon is accessible via a Unix
socket that restricts access to the local root user. Ansible Container can communicate with the Docker daemon using the 
Unix socket, however allowing access over a TCP connection may be desirable. 

You can simply change the -H option in the startup options of the Docker daemon service, setting it to
*tcp://<host IP address>:2376* and giving access to everyone. This is **NOT recommended** because it will be
trivial for anyone to gain root access to the host. Instead, we recommend securing the Docker daemon.
See :ref:`secure_docker` below.

For ansible-container to access the daemon via a TCP connection, the daemon must be set to listen on an IP address 
assigned to the host **NOT** 127.0.0.1. This is because the daemon must be accessible remotely by the Ansible build
container.

To access the Docker daemon define the DOCKER_HOST environment variable in the user's environment so that it matches the
-H setting of the Docker daemon:

.. code-block:: bash

    export DOCKER_HOST=tcp://<host IP address>:2376

**NOTE** Without this environment variable set, Ansible Container will fall back to using Docker's UNIX socket.

.. _secure_docker:

Securing Docker Daemon with TLS
-------------------------------
To secure the Docker daemon you will need the following:

* openssl
* ansible (optional)

Use the `ansible.secure-docker-daemon <https://github.com/ansible/role-secure-docker-daemon/>`_ Galaxy role to
generate the certificates. Instructions for using the role and a sample playbook are provided in the README. You can
also generate the certificates manually by following the
`instructions here <https://docs.docker.com/engine/security/https/>`_.

Once the certificates are generated, copy the client certificate, key and CA certificate to $HOME/.docker for any user
accessing the Docker daemon or running ansible-container. Set access permissions on the files so that only the user can
access them.

Copy the server certificate, key and CA certificate to the daemon host, if they were not generated on the host. On a
Linux host these files will typically be placed in /etc/docker. Set the file permissions so that only the root user has
access. Modify the Docker daemon startup options to use TLS and load the server certificates. How you modify the daemon
startup options will depend on your environment. Set the following options and restart the service:

* --tlsverify
* --tlscacert=/path/to/ca.pem
* --tlscert=/path/to/server-cert.pem
* --tlskey=/path/to/server-key.pem
* -H=tcp://<host IP address>:2376

For client access to the daemon, set the following variables in the user environment:

* export DOCKER_TLS_VERIFY=1
* export DOCKER_HOST=tcp://<host IP address>:2376

For ansible-container to access the client certificates, set the following variable in the user's environment:

* export DOCKER_CERT_PATH=/path/to/certs

For convenience the ansible.secure-docker-daemon Galaxy role generates a small shell script called docker_env.sh that
can be used in a Linux environment to define the above variables.









