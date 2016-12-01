Install and Configure OpenShift
===============================

Prior to running any of the examples that deploy an application to OpenShift, you'll need access to an OpenShift instance, and this guide
will help you install and configure an OpenShift cluster in your environment.

The installation and configuration process is fairly simple, as the OpenShift instance you'll install runs in containers. In fact, if you
already have Docker installed and working, you're halfway there!

.. contents:: Topics

.. _prerequisites:

Prerequisites
-------------

Before creating a local OpenShift cluster, you'll need the following:

+ `Docker Engine <https://docs.docker.com/engine/installation/>`_ or `Docker for Mac <https://docs.docker.com/docker-for-mac/>`_ (This guide was created using Docker for Mac 1.12.3-beta30.1 (13946)).
+ Install *socat*, if you're using Docker for Mac

  The following will install *socat* using `homebrew <http://brew.sh/>`_:

    .. code-block:: bash

        # Install socat
        $ brew install socat

.. _install_the_oc_client:

Install the oc client
---------------------

From the `release page <https://github.com/openshift/origin/releases>`_, download the latest stable OpenShift client. At the time of this writing the latest
release was `v1.3.1 <https://github.com/openshift/origin/releases/tag/v1.3.1>`_.

Unzip the downloaded release file, and move the executable into a directory that is part of your *PATH*. The following example demonstrates installing the
client on Mac OSX:

.. code-block:: bash

    # Set the working directory to your Downloads directory
    $ cd ~/Downloads

    # Create a temp directory
    $ mkdir tmp

    # Change the working directory to tmp
    $ cd tmp

    # Unzip the release file
    $ unzip ../openshift-origin-client-tools-v1.3.1-2748423-mac.zip

    # As the root user, move the executable to a directory found in your PATH
    $ sudo mv oc /usr/local/bin/oc

Now make sure you can execute the ``oc`` command by running the following test:

.. code-block:: bash

    # Set the path to your home directory
    $ cd ~

    # Demonstrate success by getting the client version
    $ oc version

You should see a response similar to the following:

.. code-block:: bash

    oc v1.3.1
    kubernetes v1.3.0+52492b4
    features: Basic-Auth

.. _create_the_cluster:

Create the cluster
------------------

The first time you attempt to create the cluster, you will likely get an error about needing to set the ``--insecure-registry``
option, as pictured in the following example:

.. code-block:: bash

    # Create the cluster
    $ oc cluster up

    -- Checking OpenShift client ... OK
    -- Checking Docker client ... OK
    -- Checking Docker version ... OK
    -- Checking for existing OpenShift container ... OK
    -- Checking for openshift/origin:v1.3.1 image ... OK
    -- Checking Docker daemon configuration ... FAIL
       Error: did not detect an --insecure-registry argument on the Docker daemon
       Solution:

           Ensure that the Docker daemon is running with the following argument:
     	       --insecure-registry 172.30.0.0/16

           You can run this command with --create-machine to create a machine with the
           right argument.

.. _allow_insecure_registry_access:

Allow insecure registry access
``````````````````````````````

In order to use the private registry that comes installed, you will need Docker to allow access to the insecure registry address
displayed when you ran the ``oc cluster up`` command, as pictured above.

Additionally, you will need to allow access to the host name on which the registry will be exposed. The host name will be your
local IP address followed by *.xip.io*. For example, if your IP address is 192.168.30.14, the host name will be *192.168.30.14.xip.io*.

To obtain your IP address on Mac OSX run ``ifconfig en0`` in a terminal window, and look for the *inet* address. On linux hosts, use
the command ``ip addr show eth0``.

Once you're ready to add the insecure registries, follow the instructions for the version of Docker you're using.

+ `Docker Engine <https://docs.docker.com/registry/insecure/>`_
+ `Docker Machine <https://docs.docker.com/machine/reference/create/#/specifying-configuration-options-for-the-created-docker-engine>`_

Docker for Mac
..............

Go to the Docker toolbar menu, choose *Preferences* and open the *Advanced* tab. Add the addresses to the list of
*Insecure Registries*, as pictured in the following:

.. image:: _static/doc_images/insecure_registry.png
   :height: 111px
   :width: 188px
   :scale: 250%
   :alt: Adding an insecure registry
   :align: center

.. Docker Toolbox
   ..............
   For Docker Toolbox you will need to create a new machine with the correct options. The following demonstrates creating a new
   machine named *devel*. Replace the IP addresses with those for your machine:
   .. code-block:: bash
   # Create a new Docker machine
   $ docker-machine create -d virtualbox
       --engine-insecure-registry 172.30.0.0/16 \
       --engine-insecure-registry 192.168.30.14.xip.io \
       --virtualbox-host-dns-resolver \
       devel

|

.. _restart_the_cluster:

Create the cluster
``````````````````

After adding the insecure registries, run the ``oc cluster up`` command again. The following shows the command completing
successfully:

.. code-block:: bash

    # Create the cluster
    $ oc cluster up

    ...

    -- Server Information ...
       OpenShift server started.
       The server is accessible via web console at:
           https://192.168.30.14:8443

       You are logged in as:
          User:     developer
          Password: developer

       To login as administrator:
         oc login -u system:admin

At the end of the output you will see a *Server Information* section, providing instructions for logging in and accessing
the console.

Error restarting the cluster
````````````````````````````

If you're using Docker for Mac, you may receive an error when you run the ``oc cluster up`` command multiple times, as
pictured in the following:

.. code-block:: bash

   -- Finding server IP ... FAIL
   Error: cannot determine a server IP to use

This is likely caused by one or more ``socat`` processes that are still running after the cluster was stopped. You'll need
to terminate them before attempting to restart the cluster. The following command will prompt for the *root* password and
execute the ``kill`` command for each process:

.. code-block:: bash

    # Terminate any running socat processes
    $ sudo kill -9 $(ps -ef | grep socat | awk '{ print $2 }')

Now attempt to restart the cluster:

.. code-block:: bash

    # Create the cluster
    $ oc cluster up

.. _configure_the_cluster:

Configure the cluster
---------------------

Now that you have a running cluster, you will need to create a route to the internal registry and a persistent volume.

.. _create_a_route:

Create a route
``````````````
Start by giving yourself (the developer) admin rights to the cluster, and setting the namespace or project to *default*:

.. code-block:: bash

    # Log in as the system user
    $ oc login -u system:admin

    # Give yourself (the developer) admin rights
    $ oc adm policy add-cluster-role-to-user cluster-admin developer

    # Log in as the developer
    $ oc login -u developer -p developer

    # Switch to the default project
    $ oc project default

Next copy the following YAML to a local file called *registry.yml*, replacing each occurrence of the IP address (there are two)
with your local IP address:

.. code-block:: bash

    apiVersion: v1
    kind: Route
    metadata:
      name: registry-access
    spec:
      host: 192.168.30.14.xip.io
      to:
        kind: Service
        name: docker-registry
        weight: 100
      port:
        targetPort: 5000-tcp
      tls:
        termination: edge
        insecureEdgeTerminationPolicy: Allow
    status:
      ingress:
        -
          host: 192.168.30.14.xip.io
          routerName: router
          conditions:
            -
              type: Admitted
              status: 'True'

The above configuration defines a route object that allows the registry to be accessed as *https://<your IP address>.xip.io*.

Now execute the following to actually create the route by using the ``oc create`` command to read the definition from the file
you just created:

.. code-block:: bash

    # Create the route
    $ oc create -f registry.yml

To test registry access, log in with the ``docker login`` command, using *developer* as the username and the OpenShift access
token as the password. Execute the following command to perform the login, replacing the IP address with your own:

.. code-block:: bash

    # Log into the OpenShift registry
    $ docker login https://192.168.30.14.xip.io -u developer -p $(oc whoami -t)

.. _create_a_persistent_volume:

Create a persistent volume
``````````````````````````

Copy the following definition to a file called *persistent.yml*, replacing the *path* with a path that works in your environment.
You will use this definition to create a 10GB persistent volume named *project-data* that will exist as long as the cluster exists.

.. code-block:: bash

    apiVersion: v1
    kind: PersistentVolume
    metadata:
      name: project-data
    spec:
      capacity:
        storage: 10Gi
      accessModes:
        - ReadWriteOnce
        - ReadWriteMany
      persistentVolumeReclaimPolicy: Retain
      hostPath:
        path: /Users/<your username>/volumes/project-data


Now execute the following to actually create the volume by using ``oc create`` to read the definition from the file you just
created:

.. code-block:: bash

    # Create the persistent volume
    $ oc create -f persistent.yml

.. _remove_the_cluster:

Remove the cluster
------------------

When you're done with the cluster, you can remove it by simply running the following:

.. code-block:: bash

    # Remove the cluster
    $ oc cluster down

The above will completely remove the OpenShift containers.

If you're running Docker for Mac, you will also want to remove any lingering ``socat`` processes. Executing the follwogin will
prompt for the *root* password and then execute the ``kill`` command on each:

.. code-block:: bash

    # Stop any lingering socat processes
    $ sudo kill -9 $(ps -ef | grep socat | awk '{ print $2 }')
