Installation
============

.. contents:: Topics

.. _getting_ansible_container:

Getting Ansible Container
`````````````````````````

Prerequisites:

* Python 2.7 or Python 3.5
* `pip <https://pip.pypa.io/en/stable/installing/>`_
* `setuptools 20.0.0+ <https://pypi.python.org/pypi/setuptools>`_

Ansible Container relies upon supported container engines for building, running,
and deploying your project. When you install Ansible Container, you must
specify which engines you want your installation to support. Currently supported
engines are:

* ``docker`` - The `Docker Engine <https://docs.docker.com/engine/installation/>`_
* ``k8s`` - `Kubernetes <https://kubernetes.io/docs/setup/pick-right-solution/>`_, on a
  remote service or in a local installation using
  `MiniKube <https://kubernetes.io/docs/getting-started-guides/minikube/>`_
* ``openshift`` - `Red Hat OpenShift <https://developers.openshift.com/getting-started/index.html>`_,
  on a remote service or in a local installation using
  `MiniShift <https://www.openshift.org/minishift/>`_

Specify the engines you wish supported by listing them comma separated in square
brackets as part of your ``pip install`` command. For example, if you intended to
use Docker for local container development but deploy your project into Kubernetes,
you would want to install the ``docker`` and ``k8s`` engines like so:

.. code-block:: console

    $ sudo pip install ansible-container[docker,k8s]

If you do not have root privileges, you'll need to use a ``virtualenv`` to create a Python sandbox:

.. code-block:: console

    $ virtualenv venv
    $ source venv/bin/activate
    $ pip install ansible-container[docker,openshift]

You'll need to run the ``activate`` script in each shell session prior to invoking ``ansible-container``.
See `the virtualenv docs <https://virtualenv.pypa.io/en/stable/>`_ for details.

.. _running_from_source:

Running from Source
```````````````````

If you'd like to run the bleeding edge version of Ansible Container, you can obtain it
from our Github repository.

Prerequisites:

* All of the prerequisites listed in :ref:`getting_ansible_container`
* `git <https://git-scm.com/book/en/v2/Getting-Started-Installing-Git>`_

Clone the repo:

.. code-block:: console

    $ git clone https://github.com/ansible/ansible-container.git

We recommend that you use a Python Virtualenv to sandbox your installation.
See `the virtualenv docs <https://virtualenv.pypa.io/en/stable/>`_ for instructions.

Then, again specifying in square-brackets the engines you wish installed, use
pip to install the cloned code:

.. code-block:: console

    $ cd ansible-container
    $ pip install -e .[docker,openshift]

If you run into the following error, you likely have an older version of setuptools installed:

.. code-block:: pytb

    Traceback (most recent call last):
      File "./setup.py", line 11, in <module>
        packages=find_packages(include='container.*'),
      TypeError: find_packages() got an unexpected keyword argument 'include'

Use the following to upgrade to the latest release, and then run the install command again:

.. code-block:: console

    $ pip install --upgrade setuptools

You may need to run the above command with ``sudo`` if you're not using a ``virtualenv``.












