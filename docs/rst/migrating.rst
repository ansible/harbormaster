Migrating to Ansible Container
==============================

Starting a new project :ref:`from an Ansible Galaxy project template <example-project>`
is pretty easy. But what if you've already got an existing project you'd like
to use with Ansible Container?

Migrating from a Dockerfile
---------------------------

If you have an existing project that you're containerizing by building from a
Dockerfile, you can translate that Dockerfile into an Ansible Container project
and Ansible role using the ``import`` command.

The ``import`` command will examine your Dockerfile and translate its directives
into an Ansible container-enabled role that is its equivalent. ``RUN`` directives
will be split and turned into ``shell`` or ``command`` tasks. ``ADD`` or ``COPY``
directives will be turned into ``copy``, ``synchronize``, or ``get_url`` tasks.
And other directives will be converted into role default variables or container
metadata.

When you run your build process, pay attention to the output that Ansible provides
offering suggestions for how you can better leverage built-in Ansible modules to
refine your tasks. For example, if your Dockerfile contained a directive to
``RUN yum install``, Ansible will give you a suggestion that you might wish to
make use of the built-in ``yum`` module bundled with Ansible instead.

What comes out of running ``import`` will get you there most of the time, but
it always makes sense to walk through what was generated to give it a sanity
check.

By way of an example, let's imagine a Dockerfile for a simple NodeJS project:

.. code-block:: dockerfile

    FROM node:7.9.0

    RUN mkdir -p /app
    WORKDIR /app

    ARG NODE_ENV dev
    ENV NODE_ENV $NODE_ENV
    COPY package.json /app/
    RUN npm install && npm cache clean
    COPY . /app/

    CMD [ "npm", "start" ]

If we run ``ansible-container import`` in the directory with this Dockerfile,
it will translate it to a role with these tasks:

.. code-block:: yaml

    - shell: mkdir -p /app
    - name: Ensure /app/ exists
      file:
        path: /app/
        state: directory
    - shell: npm install && npm cache clean
      args:
        chdir: /app
    - name: Ensure /app exists
      file:
        path: /app
        state: directory
    - synchronize:
        src: .
        dest: /app/
        recursive: yes

The ``ARG NODE_ENV dev`` becomes a variable in the role's ``defaults/main.yml``
while the remaining directives become container-enabled role metadata in the
``meta/container.yml`` file:

.. code-block:: yaml

    from: node:7.9.0
    working_dir: /app
    environment:
      NODE_ENV: '{{ NODE_ENV }}'
    command:
    - npm
    - start

Additionally, the ``import`` command left us with a functioning skeleton of the
project's ``container.yml`` that we can build upon:

.. code-block:: yaml

    settings:
      conductor_base: node:7.9.0
    services:
      nodejs:
        roles:
        - mynodeapp

Note that the default :ref:`conductor_container` base image is the same as the
NodeJS service from the Dockerfile. It's best to ensure that your Conductor
derives from the same distribution as your target containers, so since the
`node container derives from Debian Jessie <https://github.com/nodejs/docker-node/blob/a82c9dcd3f85ff8055f56c53e6d8f31c5ae28ed7/7.9/Dockerfile#L1>`_
it would make sense to change the ``conductor_base`` key value to ``debian:jessie``.

Migrating from Ansible Container 0.4.x and earlier
--------------------------------------------------

As pre-1.0 projects are apt to do, releases 0.4.x and earlier had a much different
structure and approach. Those releases did not specify Ansible Roles in the
``container.yml`` file and had a separate ``main.yml`` file, as well as putting
all of the Ansible Container artifacts in a separate ``ansible/`` subdirectory.

There is not an automated process for this, however in most cases, you can follow
these steps:

1. Move the contents of ``ansible/`` one directory-level up. The ``requirements.txt``
   file needs to be renamed to ``ansible-requirements.txt``, so as not to conflict
   with Python projects that have their own standard ``requirements.txt`` file.
2. Abstract the ``main.yml`` playbook into one or more roles. There are many helpful
   guides to this process, such as `this one <https://www.digitalocean.com/community/tutorials/how-to-use-ansible-roles-to-abstract-your-infrastructure-environment#abstracting-a-playbook-to-a-role>`_.
3. Modify your ``container.yml`` file.

   * Add a ``settings`` section with a key ``conductor_base``, specifying the base
     distribution for your :ref:`conductor_container`. This should probably match
     the distribution you're using to build your target containers.
   * For each service, add a ``roles`` key with a list of all the roles that go
     into building that service.
   * For each service, the ``image`` key should be renamed ``from``.

For example, each container with a settings list might look like:

.. code-block:: yaml

    settings:
      conductor_base: centos:7
    services:
      webapp:
        roles:
        - python2
        - mywebapp
      redis:
        roles:
        - redis

If you are having difficulty, please :ref:`reach out for help <ask_a_question>`.
