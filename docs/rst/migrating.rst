Migrating to Ansible Container
==============================

Starting a new project is pretty easy. But what if you've already got an
existing project you'd like to use with Ansible Container?

Migrating from a Dockerfile
---------------------------

If you have an existing project that you're containerizing by building from a
Dockerfile, you can translate that Dockerfile into an Ansible Container project
and Ansible role using the ``import`` command.

The ``import`` command will examine your Dockerfile and translate its directives
into an equivalent Ansible container-enabled role. ``RUN`` directives
will be split and turned into ``shell`` or ``command`` tasks. ``ADD`` or ``COPY``
directives will be turned into ``copy``, ``synchronize``, or ``get_url`` tasks.
And other directives will be converted into role default variables or container
metadata.

When you run the ``build`` process against the resulting project, pay attention to the output that Ansible provides. It will offer suggestions for how you can better leverage built-in Ansible modules to refine your tasks. For example, if your Dockerfile contained a directive to ``RUN yum install``, Ansible will give you a suggestion that you might wish to make use of the built-in ``yum`` module bundled with Ansible instead.

What comes out of running ``import`` will get you there most of the time, but it always makes sense to walk through what was generated to give it a sanity check.

By way of an example, let's imagine you have a directory named ``node`` that contains the following Dockerfile for a simple Node service:

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

To migrate the above to an Ansible Container project, start by creating a new project directory. You'll run the ``import`` command from within this new directory in order to keep generated artifacts separate from the existing project. For example, create a new directory named ``acnode`` next to the existing ``node`` directory, and set your working directory to ``acnode``, as follows:

.. code-block:: console

    $ mkdir acnode
    $ cd acnode

Now from within the ``acnode`` directory, run ``ansible-container import ../node`` to perform the import. Once completed, you will see output similar to the following that explains what the import did, and describes each file it produced:

.. code-block:: console

    $ ansible-container import ../node
    
    Project successfully imported. You can find the results in:
    ~/acnode
    A brief description of what you will find...

    container.yml 
    -------------

    The container.yml file is your orchestration file that expresses what services you have and how to build/run them.

    settings:
      conductor_base: node:7.9.0
    services:
      node:
        roles:
        - test

    I added a single service named node for your imported Dockerfile.
    As you can see, I made an Ansible role for your service, which you can find in:
    ~/acnode/roles/node

    acnode/roles/test/tasks/main.yml
    --------------------------------

    The tasks/main.yml file has your RUN/ADD/COPY instructions.

    - shell: mkdir -p /app
    - name: Ensure /app/ exists
      file:
        path: /app/
        state: directory
    - copy:
      src: package.json
      dest: /app/
    - shell: npm install && npm cache clean
      args:
        chdir: /app
    - name: Ensure /app/ exists
      file:
        path: /app/
        state: directory
    - synchronize:
      src: .
      dest: /app/
      recursive: yes


    I tried to preserve comments as task names, but you probably want to make
    sure each task has a human readable name.

    ~/roles/node/meta/container.yml
    -------------------------------

    Metadata from your Dockerfile went into meta/container.yml in your role.
    These will be used as build/run defaults for your role.

    from: node:7.9.0
    working_dir: /app
    environment:
      NODE_ENV: '{{ NODE_ENV }}'
    command:
    - npm
    - start


    I also stored ARG directives in the role's defaults/main.yml which will used as
    variables by Ansible in your build and run operations.

    Good luck!
    Project imported.

The original Dockerfile was translated into a role, as described in the above example output. You'll find the role in ``acnodes/roles/node``. Since the original project directory is named ``node``, the resulting role is also named ``node``. Here are the tasks added to its ``tasks/main.yml``:

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

The ``ARG NODE_ENV dev`` becomes a variable in the role's ``defaults/main.yml`` file:

.. code-block:: yaml

    playbook_debug: false
    NODE_ENV dev: '~'


The remaining directives become container-enabled role metadata in the
``meta/container.yml`` file:

.. code-block:: yaml

    from: node:7.9.0
    working_dir: /app
    environment:
      NODE_ENV: '{{ NODE_ENV }}'
    command:
    - npm
    - start

Additionally, the ``import`` command creates a ``container.yml`` file that defines a single service named ``node``:

.. code-block:: yaml

    settings:
      conductor_base: node:7.9.0
    services:
      node:
        roles:
        - mynodeapp

Note in the above that the default :ref:`conductor_container` base image matches the ``FROM`` in the Dockerfile. It's best to ensure that your Conductor derives from the same distribution as your target containers, so since the `node container derives from Debian Jessie <https://github.com/nodejs/docker-node/blob/a82c9dcd3f85ff8055f56c53e6d8f31c5ae28ed7/7.9/Dockerfile#L1>`_ it would make sense to change the ``conductor_base`` key value to ``debian:jessie``.

Migrating from Ansible Container 0.4.x and earlier
--------------------------------------------------

As pre-1.0 projects are apt to do, releases 0.4.x and earlier had a much different structure and approach. Those releases did not specify Ansible Roles in the ``container.yml`` file, had a separate ``main.yml`` file, and put all of the Ansible Container artifacts in a separate ``ansible/`` subdirectory.

There is not an automated process for this, however in most cases, you can follow these steps:

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
