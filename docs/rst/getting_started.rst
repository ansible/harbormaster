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

.. code-block:: bash

    ansible.cfg
    ansible-requirements.txt
    container.yml
    meta.yml
    requirements.yml

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

.. _example-project:

Real World Usage - Starting from a Working Base Setup
-----------------------------------------------------

Most of the time, when you're starting a new project, you're probably using a fairly standard set of components
that all link together to form a working system. For example, if you're starting a new Wordpress app, you will
likely want a container for Apache, one for MySQL/MariaDB, one for Memcache, and one for Wordpress itself. Ansible
Container enables you to bootstrap a new project based on such templates, hosted on `Ansible Galaxy <http://galaxy.ansible.com/>`_.

Let's look at a working example. A basic `Django <http://djangoproject.com>`_ application might have the Django
application server, a static files server, a PostgreSQL database, and static assets compiled from sources using
Gulp and Node.js. To pull the template from Ansible Galaxy and bootstrap a new project based on it, run:

.. code-block:: bash

  ansible-container init ansible.django-template

From here, you can even build and run this project, even though it doesn't do a whole lot.

.. code-block:: bash

  ansible-container build
  ansible-container run

To take a deeper dive into what the project template offers, it requires looking into the ``container.yml``
file, where we find the application orchestration and build instructions.

container.yml
`````````````

As explained above, the ``container.yml`` file, like a Docker Compose file, describes the
orchestration of the containers in your app for both development and production environments. In this
app, we have Django application server, a PostgreSQL database server, and an nginx web server.

This ``container.yml`` file has an additional top-level key called `defaults`, mapping variables to
some same default values:

.. code-block:: yaml

    defaults:
      POSTGRES_USER: django
      POSTGRES_PASSWORD: sesame
      POSTGRES_DB: django
      DJANGO_PORT: 8080

These variables can be substituted into the `services` and `registries` sections of the file using
Jinja2 syntax, just like Ansible Core, abstracting out runtime constants for easy tweaking. They
can also be overridden at run-time with environment variables or by passing an variables files,
just like Ansible Core.

The Django service runs with the self-reloading development server for the development environment
while running with the Gunicorn WSGI server for production:

.. code-block:: yaml

    django:
      from: centos:7
      roles:
        - django-gunicorn
      environment:
        DATABASE_URL: "pgsql://{{ POSTGRES_USER }}:{{ POSTGRES_PASSWORD }}@postgres:5432/{{ POSTGRES_DB }}"
        DJANGO_ROOT: '{{ DJANGO_ROOT }}'
        DJANGO_VENV: '{{ DJANGO_VENV }}'
      links:
      - postgres
      - postgres:postgresql
      ports:
      - '{{ DJANGO_PORT }}'
      working_dir: '{{ DJANGO_ROOT }}'
      user: '{{ DJANGO_USER }}'
      command: ['{{ DJANGO_VENV }}/bin/gunicorn', '-w', '2', '-b', '0.0.0.0:{{ DJANGO_PORT }}', 'project.wsgi:application']
      entrypoint: ['/usr/bin/dumb-init', '/usr/bin/entrypoint.sh']
      volumes:
        - "static:/static"
      dev_overrides:
        command: ['{{ DJANGO_VENV }}/bin/python', 'manage.py', 'runserver', '0.0.0.0:{{ DJANGO_PORT }}']
        volumes:
        - '/Users/jginsberg/Development/ansible/ansible-container-template/django-template:{{ DJANGO_ROOT }}'
        - "static:/static"
        expose: "{{ DJANGO_PORT }}"
        environment:
          DEBUG: "1"

This container image uses Centos 7 as its base. For `12-factor compliance <https://12factor.net/config>`_, the
Django container sets the database server connection string in an environment variable. In development, the app's
source is exported into the container as a volume so that changes to the code can be detected and instantly integrated
into the development container, however in production, the full Django project's code is part of the container's
filesystem. Note that in both development and production, `Yelp's dumb-init <https://github.com/Yelp/dumb-init>`_ is
used for PID 1 management, which is an excellent practice.

As such, Nginx server runs in production but does not in development orchestration.

.. code-block:: yaml

  nginx:
    from: centos:7
    roles:
      - nginx
    ports:
    - '{{ DJANGO_PORT }}:8000'
    user: nginx
    links:
    - django
    command: ['/usr/bin/dumb-init', 'nginx', '-c', '/etc/nginx/nginx.conf']
    volumes:
      - "static:/static"
    dev_overrides:
      ports: []
      command: /bin/false
      volumes: []

In development, Gulp's webserver listens on port 80 and proxies requests to Django, whereas
in production we want Nginx to have that functionality.

.. note::

    The Django and Nginx server share a named volume, so that static assets collected
    from Django can be served by Nginx. Versus the Docker-engine-specific ``volumes_from``
    directive, this approach is far more cross-platform.

Finally, we set up a PostgreSQL database server using a stock image from Docker Hub:

.. code-block:: yaml

  postgres:
    from: postgres:9.6
    environment:
      POSTGRES_USER: "{{ POSTGRES_USER }}"
      POSTGRES_PASSWORD: "{{ POSTGRES_PASSWORD }}"
      POSTGRES_DB: "{{ POSTGRES_DB }}"

You can use distribution base images like CentOS, Ubuntu, or Fedora for the build process
to customize, or you can use pre-built base images from a container registry like Docker Hub
without modification.

Bundled with the project are roles for the Django and Nginx services. In your project,
you can edit these roles to modify the functionality of the ones provided as well as
create additional roles, even common ones between the two. For each service,
Ansible Container will create a new image layer for each role.

So add additional Django apps, write your own, and develop your project. When
you're ready, check out the options provided to :doc:`deploy <reference/deploy>`
your app into one of the supported production container platforms.
