Getting Started
===============

Projects in Ansible Container are identified by their path in the filesystem.
The project path contains all of the source and files for use inside of your
project, as well as the Ansible Container build and orchestration
instructions.

.. _conductor_container:

Conductor Container
-------------------

The heavy lifting of Ansible Container happens within a special container,
generated during the ``build`` process, called the Conductor.

It contains everything you need to build your target container images, including
Ansible Core itself. Since Ansible requires a Python runtime on the hosts it
is configuring, and so that you don't need to install Python on those target
container images you are building, the Python runtime and all library dependencies
are mounted from the Conductor container into the target containers during builds.

Because of this, the Conductor container is built upon a base image of your
choice, and it's recommended that you select the same flavor of Linux distribution
that your  target containers will be built from. For example, if you're building
container images based on Alpine Linux, it's a good idea to use Alpine Linux as
your Conductor container base image as well, so that what the Conductor exports
to your target containers contains ``apk`` and other binary dependencies you will
likely need.

For more about how the Conductor container gets built, available pre-baked Conductor images, and
how to build your own Conductor image, see :doc:`conductor`.


Dipping a Toe In - Starting from Scratch
----------------------------------------

Ansible Container provides a convenient way to start your app by simply running
``ansible-container init`` from within your project directory, which creates:

.. code-block:: none

    ansible.cfg
    ansible-requirements.txt
    container.yml
    meta.yml
    requirements.yml
    .dockerignore

Other ``ansible-container`` subcommands enable the container development workflow:

* ``ansible-container build`` initiates the build process. It builds and launches
  the :ref:`conductor_container`. The Conductor then runs
  instances of your base container images as specified in ``container.yml``.
  The Conductor container applies `Ansible roles <https://docs.ansible.com/ansible/playbooks_roles.html>`_
  against them, committing each role as new image layers. Ansible communicates
  with the other containers through the container engine, not through SSH.
* ``ansible-container run`` orchestrates containers from your built images together as described
  by the ``container.yml`` file. The ``container.yml`` can specify overrides to
  make development faster without having to rebuild images for every code change.
* ``ansible-container deploy`` uploads your built images to a container registry
  of your choice and generates an Ansible playbook to orchestrate containers from
  your built images in production container platforms, like Kubernetes or Red Hat OpenShift.

So what goes into the files that make this work?

container.yml
`````````````

The ``container.yml`` file is a file in YAML-syntax that describes the services
in your project, how to build and run them, the repositories to push them to,
and more.

The ``container.yml`` file is similar to the other multi-container orchestration formats, like
Docker Compose or OpenCompose. Much like these other formats, this file describes the
orchestration of your app. Ansible Container uses this file to determine what images to
build, what containers to run and connect, and what images to push to
your repository. Additionally, when Ansible Container generates an Ansible playbook to ship and
orchestrate your images in the cloud, this file describes the configuration target for your
entire container infrastructure. It is automatically run, but it also saves the playbook for
you to examine or reuse.

By way of an example, consider the below ``container.yml`` file:

.. code-block:: yaml

    version: "2"
    services:
      web:
        from: "centos:7"
        roles:
          - common
          - apache
        ports:
          - "80:80"
        command: ["/usr/bin/dumb-init", "/usr/sbin/apache2ctl", "-D", "FOREGROUND"]
        dev_overrides:
          environment:
            - "DEBUG=1"

Things to note:

1. In this example the schema is set to version 2. (Version 2 support was add in version 0.3.0.)
2. Each of the containers you wish to orchestrate should be under the `services` key.
3. For supported `service` keys, see :doc:`container_yml/reference`.
4. The image you specify should be the base image that your containers will start from.
   Ansible Container will use your roles to build upon this base image. Each role you
   specify needs to be in a `roles/` directory in your project, in your `requirements.yml` file,
   or in the `--roles-path` you specify at runtime in the command line.
5. You may optionally specify a `dev_overrides` section. During build and in generating
   the Ansible roles to deploy your app to the cloud, this section will be
   ignored. However, when running your containers locally for your development environment,
   you may use this section to override settings from your production configuration. For
   instance, a Javascript developer may wish to use Gulp and BrowserSync to dynamically
   rebuild assets while development is taking place, versus rebuilding the entire container
   for every code change. Thus that developer may wish to include `dev_overrides` that run
   a BrowserSync server for those assets, whereas in production Gulp would build those assets
   and exit.

meta.yml
````````
You can share your project on `Ansible Galaxy <https://galaxy.ansible.com>`_ for
others to use as a template for building projects of their own. These templates are called
"Container Apps". Provide the requested information in ``meta.yml``, and then log into
Galaxy to import it into the Ansible Container project template registry.

ansible-requirements.txt
````````````````````````
Running Ansible inside of the Conductor container may have Python library
dependencies that your modules require. Use the ``ansible-requirements.txt``
file to specify those dependencies. This file follows the standard `pip <https://pip.pypa.io/>`_
format for Python dependencies. When your Conductor container image is created,
these dependencies are installed.

requirements.yml
````````````````
If the roles in your ``container.yml`` file are in Ansible Galaxy or a remote
SCM repository, and your project depends upon them, add them to ``requirements.yml``.
For more information about ``requirements.yml`` see
`Installing Roles From a File <http://docs.ansible.com/ansible/galaxy.html#installing-multiple-roles-from-a-file>`_.

ansible.cfg
```````````
Set Ansible configuration settings within the build container. For more
information see `Configuration File <http://docs.ansible.com/ansible/intro_configuration.html>`_.
Do note that overriding some of the settings, like `roles_path`, might have unexpected results,
due to Ansible using the Conductor container as its execution environment.

.dockerignore
`````````````
During a build, it is commonplace to synchronize the source from your project into
one of your target containers. However many such files are not appropriate to be
part of that build context, such as your ``.git`` directory. The Docker Engine would
ignore files or patterns contained in the ``.dockerignore`` file from the build context
and for conformity, Ansible Container will do the same.

.. _hello_world:

Hello World
-----------

Every good walkthrough needs a `"Hello, world,"`_ right? So let's start there,
and make a Flask_ web service.

.. _"Hello, world,": https://en.wikipedia.org/wiki/%22Hello,_World!%22_program
.. _Flask: https://flask.pocoo.org/


Writing the code
````````````````

.. code-block:: console

    $ mkdir hello-world
    $ cd hello-world
    $ ansible-container init
    Ansible Container initialized.

Now that we have the skeleton of an empty project, let's make our Flask app.
First, we need to list our Python requirements. So let's create a file called
``requirements.txt`` that lists the Python packages we need:

.. code-block:: none

    Flask==0.12.2
    gunicorn==19.7.1

And let's write the Hello, world, Flask app code, in a file called ``helloworld.py``:

.. code-block:: python

    from flask import Flask
    app = Flask(__name__)

    @app.route('/')
    def hello_world():
        return 'Hello, World!'

Next, let's write the Ansible role that will be used to build our container. First,
we have to create a ``roles/`` directory and create the skeleton of a new Ansible
role using the ``ansible-galaxy`` utility (make sure you have Ansible installed
to get this utility):

.. code-block:: console

    $ mkdir roles
    $ cd roles
    $ ansible-galaxy init flask
    - flask was created successfully

We can put the steps to build our container in ``tasks/main.yml``.

First, we grab dumb-init_ from GitHub. In Linux systems, the process with
process id (PID) 1 is special, in that it is expected to react differently to
different system signals. The ``dumb-init`` utility very simply handles those
signals properly and then spawns the real command you want your container to run.

.. _dumb-init: https://engineeringblog.yelp.com/2016/01/dumb-init-an-init-for-docker.html

Second, we need to install the Python package management utility ``pip``, which
in the CentOS world is in EPEL (Extra Packages for Enterprise Linux). So our
next tasks set up our container to look into EPEL for its packages, from which
it can find Pip.

Next, we need to create an unprivileged user to run our application. Running a
container as root is a Bad Idea™, and enterprise-grade Kubernetes platforms like
Red Hat OpenShift will refuse to execute a container that tries to run as root.
However, we can keep our user in the root group without the same security impact.

Using the syncrhonize plugin, we can copy our project source into the container
to use. Our Ansible Container project path is staged in the Conductor container
at ``/src``, so synchronize can find it there. This content will have already been
filtered by the ``.dockerignore`` file in our project, and by default that
``.dockerignore`` file includes sensible things to ignore like ``.git/``.

Finally, we want to use the ``pip`` utility we installed to grab the contents of the
``requirements.txt`` file to install Python dependencies.

.. code-block:: yaml

    ---
    - name: Install dumb init
      get_url:
        dest: /usr/bin/dumb-init
        url: https://github.com/Yelp/dumb-init/releases/download/v1.2.0/dumb-init_1.2.0_amd64
        mode: 0775
        validate_certs: no
    - name: Install epel
      yum:
        name: epel-release
        state: present
        disable_gpg_check: yes
    - name: Install pip
      yum:
        name: python2-pip
        state: present
        disable_gpg_check: yes
    - name: Create flask user
      user:
        name: flask
        uid: 1000
        group: root
        state: present
        createhome: yes
        home: "/app"
    - name: Copy source into container
      synchronize:
        src: "/src/"
        dest: "/app"
      remote_user: flask
    - name: Install Python dependencies
      pip:
        requirements: /app/requirements.txt

Having written the role's tasks, we're almost ready to build. We still have to
describe how our application will be built and run in the ``container.yml`` file.

As generated by ``ansible-container init``, the boilerplate ``container.yml`` file
contains a lot of commented out hints about what it can contain. Our example below
contains just the significant parts of the ``container.yml``, not the commented
parts, so feel free either to read the comments in the boilerplate before
copy-and-pasting our example into your text editor or to make line by line edits.
Your choice.

The ``container.yml`` file encompasses all of your services and containers,
all of your container registries, all of your persistent storage, and all of
your overrides of Ansible Container runtime defaults.

For our Ansible Container ``settings``, we need to identify the Conductor base
image that we're going to use; this should be the distribution that our target
images are also ultimately based on. Since we're going to build a CentOS 7
container image for Flask, we need the CentOS 7 base. And since we're going to
deploy our app into Kubernetes, we should configure the Kubernetes namespace
(also the OpenShift project) in which our application will be deployed.

For our services, we have only the one: our Flask service. We must state its
base image and the list of roles from which it will be built. And then we also
specify its runtime configuration, much like one might do in a Docker Compose
file.

Registries is required to be present, even if we don't have a private registry
we're going to deploy to just yet.

Our ``container.yml`` thus looks like this:

.. code-block:: yaml

    version: "2"
    settings:
      conductor:
        base: centos:7
      project_name: hello-world
      k8s_namespace:
         name: hello-world
         description: Simple Demo
         display_name: Hello, World
    services:
      flask:
        from: centos:7
        roles:
          - flask
        entrypoint: /usr/bin/dumb-init
        command: gunicorn -w 4 -b 0.0.0.0:4000 helloworld:app
        ports:
          - 4000:4000
        working_dir: /app
        user: flask
    registries: {}

That's it - we're all set to start building and running.

Building the service
````````````````````

To kick off a build, all you do is run:

.. code-block:: console

    $ ansible-container build

But let's talk about what happens when you do. First, Ansible Container builds
its Conductor container. This may involve pulling the Conductor base image from
the Docker Hub registry, but once it has that base image it makes a custom
Conductor image for your project.

Then, Ansible Container starts up this Conductor container, which in turn tells
the container engine to start up instances of each service's base image to use
in the build. From there, the Conductor runs Ansible, applying each of the roles
to the target containers, committing new image layers for each role.

Ansible Container also maintains a build cache. If you were to run the build
again, Ansible Container would recognize that your service configuration and
the ``flask`` role hadn't changed and would exit quickly. It will only rebuild
the layers of your image that it has detected likely to have changed. You can
always disable the build cache with ``--no-cache`` when you build.

But back to our build. When we run, ``ansible-container build``, we see some
output like this:

.. code-block:: console

    Building Docker Engine context...
    Starting Docker build of Ansible Container Conductor image (please be patient)...
    Parsing conductor CLI args.
    Copying build context into Conductor container.
    Docker™ daemon integration engine loaded. Build starting.       project=hello-world
    Building service...     project=hello-world service=flask
    Fingerprint for this layer: 60ed99196f031a470d2dfbe39e9af02fb934b7d328a0e3f494f11ba1072e878e    parent_fingerprint=ccfe8c87363124f4f46aa60b2d727e06366c81d2a3d552672faa027e1cee144d parent_image_id=<Image: 'centos:7'> role=flask service=flask
    Cached layer for for role flask not found or invalid.   cur_image_id=<Image: 'centos:7'> fingerprint=60ed99196f031a470d2dfbe39e9af02fb934b7d328a0e3f494f11ba1072e878e service=flask
    Could not locate intermediate build container to reapply role flask. Applying role on image <Image: 'centos:7'> as container hello-world_flask-ccfe8c87-flask.  cur_image_fingerprint=ccfe8c87363124f4f46aa60b2d727e06366c81d2a3d552672faa027e1cee144d service=flask

    PLAY [flask] *******************************************************************

    TASK [Gathering Facts] *********************************************************
    ok: [flask]

    TASK [flask : Install dumb init] ***********************************************
    changed: [flask]

    TASK [flask : Install epel] ****************************************************
    changed: [flask]

    TASK [flask : Install pip] *****************************************************
    changed: [flask]

    TASK [flask : Create flask user] ***********************************************
    changed: [flask]

    TASK [flask : Copy source into container] **************************************
    changed: [flask]

    TASK [flask : Install Python dependencies] *************************************
    changed: [flask]

    PLAY RECAP *********************************************************************
    flask                      : ok=7    changed=6    unreachable=0    failed=0

    Applied role to service role=flask service=flask
    Committed layer as image        fingerprint=60ed99196f031a470d2dfbe39e9af02fb934b7d328a0e3f494f11ba1072e878e image=sha256:5367a04394b09a145dc9d3b6302ae89cb5f0aeab9fe61589632c4775cc8bac94 role=flask service=flask
    Build complete. service=flask
    Cleaning up stale build artifacts.      service=flask
    All images successfully built.
    Conductor terminated. Cleaning up.      command_rc=0 conductor_id=54f566e42f800de2c00842fbac32e25c13d863a86b351f38c695aba27ed0604c save_container=False

Looking through it, we can see the steps it took: building the Conductor, the
build cache looking at known fingerprints, the Ansible playbook executing, the
and container image layer being committed. If you run ``docker images`` you can
see that you've got new images for your project's Conductor and the service it
built. Ansible Container will use the build timestamp for the version label.

And if we inspect the image we've build, we can see it is the ``centos:7`` image
plus a single additional layer (note that the specific hash ID's will almost
certainly be different for your installation):

.. code-block:: console

    $ docker inspect --format '{{.RootFS.Layers}}' centos:7
    [sha256:e15afa4858b655f8a5da4c4a41e05b908229f6fab8543434db79207478511ff7]
    $ docker inspect --format '{{.RootFS.Layers}}' hello-world-flask
    [sha256:e15afa4858b655f8a5da4c4a41e05b908229f6fab8543434db79207478511ff7 sha256:f40f4bccee05c1406fa7812d2aa33345796306bd31f562470582410fdcb0e488]

Now we can go on ahead and run the project.

Running the service
```````````````````

To run your project, Ansible Container spins up the Conductor once more. Behind
the scenes, it uses your ``container.yml`` to generate an Ansible playbook to
orchestrate your application in the container platform. Then it executes this
playbook. So if we were to run our project, we might see:

.. code-block:: console

    $ ansible-container run
    Parsing conductor CLI args.
    Copying build context into Conductor container.
    Engine integration loaded. Preparing run.	engine=Docker™ daemon
    Verifying service image	service=flask

    PLAY [Deploy hello-world] ******************************************************

    TASK [docker_service] **********************************************************
    changed: [localhost]

    PLAY RECAP *********************************************************************
    localhost                  : ok=1    changed=1    unreachable=0    failed=0

    All services running.	playbook_rc=0
    Conductor terminated. Cleaning up.	command_rc=0 conductor_id=d043ef69b3a71d919cfcdcac959e635dc18deb8020ba3c98706b7979f2f5678f save_container=False

Let's verify that the service is actually running by asking Docker and hitting
the Flask server:

.. code-block:: console

    $ docker ps
    CONTAINER ID        IMAGE                              COMMAND                  CREATED             STATUS              PORTS                    NAMES
    8a23d7571c05        hello-world-flask:20180127130321   "/usr/bin/dumb-init …"   14 seconds ago      Up 12 seconds       0.0.0.0:4000->4000/tcp   helloworld_flask_1
    $ docker logs helloworld_flask_1
    [2018-01-27 13:04:18 +0000] [7] [INFO] Starting gunicorn 19.7.1
    [2018-01-27 13:04:18 +0000] [7] [INFO] Listening at: http://0.0.0.0:4000 (7)
    [2018-01-27 13:04:18 +0000] [7] [INFO] Using worker: sync
    [2018-01-27 13:04:18 +0000] [12] [INFO] Booting worker with pid: 12
    [2018-01-27 13:04:18 +0000] [13] [INFO] Booting worker with pid: 13
    [2018-01-27 13:04:18 +0000] [14] [INFO] Booting worker with pid: 14
    [2018-01-27 13:04:18 +0000] [19] [INFO] Booting worker with pid: 19
    $ curl http://127.0.0.1:4000/
    Hello, World!

Voila! Up and running.

Deploying to Kubernetes
```````````````````````

If you recall, when we ran our project above, the Conductor container generated
an Ansible playbook to orchestrate the application in the container engine. In
Ansible Container, the ``deploy`` command pushes your build images to a registry
and then writes the deployment playbook to disk for you to execute when you're
ready.

Ansible Container is designed with pluggable backends, called engines. So far,
we have been using the engine for the Docker Engine. But Ansible Container
supports other engines, and we're actively working on new ones. To date, we
support the Docker Engine, Kubernetes, and Red Hat OpenShift. Each of these
requires additional dependencies be installed, as described in the
:ref:`install instructions<getting_ansible_container>`.

For this walkthrough, the easiest thing to do is to install the open-source
upstream for Red Hat OpenShift, an enterprise-grade distribution of Kubernetes,
called OpenShift Origin. OpenShift Origin offers a conveniently packaged version
for developer systems as ``minishift``. We provide an easy Ansible role for
getting Minishift set up :doc:`here<openshift/minishift>`.

Once you've got Minishift going on your system, we use the ``deploy`` command
to generate the deployment playbook:

.. code-block:: console

    $ ansible-container --engine openshift deploy
    Parsing conductor CLI args.
    Copying build context into Conductor container.
    Engine integration loaded. Preparing deploy.	engine=OpenShift™
    Verifying image for flask
    ansible-galaxy 2.4.2.0
      config file = /etc/ansible/ansible.cfg
      configured module search path = [u'/root/.ansible/plugins/modules', u'/usr/share/ansible/plugins/modules']
      ansible python module location = /usr/lib/python2.7/site-packages/ansible
      executable location = /usr/bin/ansible-galaxy
      python version = 2.7.5 (default, Aug  4 2017, 00:39:18) [GCC 4.8.5 20150623 (Red Hat 4.8.5-16)]
    Using /etc/ansible/ansible.cfg as config file
    Opened /root/.ansible_galaxy
    Processing role ansible.kubernetes-modules
    Opened /root/.ansible_galaxy
    - downloading role 'kubernetes-modules', owned by ansible
    https://galaxy.ansible.com/api/v1/roles/?owner__username=ansible&name=kubernetes-modules
    https://galaxy.ansible.com/api/v1/roles/16501/versions/?page_size=50
    - downloading role from https://github.com/ansible/ansible-kubernetes-modules/archive/v0.3.1-6.tar.gz
    - extracting ansible.kubernetes-modules to /home/joeschmoe/devel/hello-world/ansible-deployment/roles/ansible.kubernetes-modules
    - ansible.kubernetes-modules (v0.3.1-6) was installed successfully
    Conductor terminated. Cleaning up.	command_rc=0 conductor_id=c078b981a08206aa09ce413aec4eb19c6b785c1cab73dd2a239d016d8cd263bb save_container=False

The generated output has been written out in our project path to a new directory
``ansible-deployment`, with the playbook ``ansible-deployment/hello-world.yml``.

The playbook contains tagged tasks for each of the lifecycle management stages
of your project: ``start``, ``stop``, ``restart``, and ``destroy``. To execute,
change directory to the ``ansible-deployment`` directory and run:

.. code-block:: console

    $ ansible-playbook hello-world.yml --tags=start

You can then go to the console of your local Minishift instance and see your
project at work. Run ``minishift console`` to bring up the web console, log in
using the default credentials (username and password both ``developer``), and
look at the Hello World project.

