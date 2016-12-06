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
* `Docker Engine <https://docs.docker.com/engine/installation/>`_, `Docker for Mac<https://docs.docker.com/engine/installation/mac/>`_,
  or access to a Docker daemon.

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












