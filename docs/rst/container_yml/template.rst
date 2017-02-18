Jinja Templating
================

**New in 0.2.0**

Jinja template rendering is supported in ``container.yml``. If you're unfamiliar with Jinja and template rendering
in general, please visit the `Jinja Documentation Site <http://jinja.pocoo.org/docs/dev/>`_.

.. contents:: Topics

How it works
------------
Your ``container.yml`` may contain Jinja variables and expressions indicated using the default delimiters as
follows:

* ``{% ... %}`` for control statements
* ``{{ ... }}`` for expressions
* ``{# ... #}`` for comments

Here's an example ``container.yml`` containing Jinja expressions:

 .. code-block:: yaml 

    version: "1"
    services:
        web:
            image: {{ web_image }}
            ports: {{ web_ports }}
            command: ['sleep', '10']
            dev_overrides:
                environment:
                - DEBUG={{ debug }}
        db: {{ db_service }}
    registries: {}

Variable definitions are needed for Jinja to execute the control statements, resolve expressions, and return the
contents of the fully rendered template. In the above example, definitions are required for ``web_image``, ``web_reports``,
``debug``, and ``db_service``. Without them an incomplete ``container.yml`` will be rendered.

.. note::

    Rendering the completed ``container.yml`` by resolving Jinja expressions to actual values is the very first thing Ansible
    Container does before starting any process. In the case of the ``build`` command, for example, template rendering happens
    before any containers are started, and it occurs outside of the Ansible Build Container.

There are three ways to provide variable values:

* Pass a YAML or JSON file with the ``--var-file`` option
* Create environment variables
* Add a top-level ``defaults`` section to ``container.yml``

See `Passing environment variables`_ , `Providing defaults`_, `Passing variable files`_, and `Variable precedence`_ for
a deeper discussion of variables. For the purpose of understanding how templating works, we'll use a file.

Using the ``--var-file`` option, the path to a file containing variable definitions can be passed to Ansible Container.
The file format can be YAML or JSON. For example, the following passes a YAML file, ``devel.yaml``, to the build command:

.. code-block:: bash

    $ ansible-container --var-file devel.yaml build

Suppose ``devel.yaml`` contains the following variable definitions:

 .. code-block:: yaml 

    ---
    debug: 1
    web_ports:
      - 8000:8000
    web_image: "python:2.7"
    db_service:
      image: "python:2.7"
      command: sleep 10
      expose:
        - 5432
      environment:
        - POSTGRES_DB_NAME=foobar
        - POSTGRES_USER=admin
        - POSTGRES_PASSWORD=admin

Variables can be defined as simple string, integer, or float types, or they can be complex data structures as in the
above definition for ``db_service``.

Before the ``build`` command can be executed, Jinja is called to perform template rendering, or ``templating`` for short.
Ansible Container reads the contents of the variable file, ``devel.yaml`` and passes it to Jinja along with a copy
of ``container.yml``. Jinja performs the transformation and returns an updated copy of ``container.yml`` with all of
the expressions replaced by actual values. Ansible Container is then able to perform the ``build``. Keep in mind that
all of this happens in memory. The actual ``container.yml`` file is not modified.

The following is the ``container.yml`` returned from Jinja and used to execute the ``build`` of our images:

.. code-block:: yaml

    version: "1"
    services:
        web:
            image: "python:2.7"
            ports:
              - 8000:8000
            command: ['sleep', '10']
            dev_overrides:
                environment:
                  - DEBUG=1
        db:
            image: "python:2.7"
            command: sleep 10
            expose:
              - 5432
            environment:
              - POSTGRES_DB_NAME=foobar
              - POSTGRES_USER=admin
              - POSTGRES_PASSWORD=admin
    registries: {}

Passing variable files
----------------------

Pass the path to a file containing variable definitions using the ``--var-file`` option. The file path must be one of
the following:

* Absolute file path
* Relative to the project path
* Relative to the ``ansible`` folder

When ``--var-file`` is passed, Ansible Container checks if the path is an absolute path to a file. If not, it checks for the
file relative to the project path, which is the current working directory or a path specified using the ``--project`` option.
If the file is still not found, it looks for the file relative to the ``ansible`` folder within the project path.

YAML vs JSON
````````````
The file will be a text file containing variable definitions formatted as either YAML or JSON.
The filename extension determines how the file is parsed. If the name ends with ``.yaml`` or ``.yml``, contents are parsed
as YAML, otherwise contents are parsed as JSON.

Filters and expressions
```````````````````````

Variable files may also include Jinja expressions. And for convenience, variables defined in the ``defaults`` section of
``container.yml`` can be referenced in a variable file.

Suppose that ``container.yml`` defines *smtp_port* as follows:

.. code-block:: yaml

    version: "1"
    defaults:
        smtp_port: 3309

    django:
        environment:
           GALAXY_SMTP_PORT={{ galaxy_smtp_port }}

Then the following would be a valid expression in the variable file:

.. code-block:: yaml

    ---
    galaxy_smtp_port: {{ smtp_port }}

The variable file is templated before ``container.yml``, so any expressions found in the variable file are resolved before
the variable file is used to template ``container.yml``.

Since default variable values are already available in ``container.yml`` this might not seem very useful. Consider, however,
that all of the Jinja control structures and filters are available in a variable file as well. That means given the following
variable file:

.. code-block:: yaml

    ---
    postgres_password: {{ lookup('env', 'POSTGRES_PASSWORD') }}


The value of *postgres_password* will be taken from the environment variable *POSTGRES_PASSWORD* defined at run-time. It can
then be used to override the default defined in the following ``container.yml`` (see `Variable precedence`_ for more about
overriding variable values):

.. code-block:: yaml

    version: "1"
    defaults:
        postgres_password: galaxy

    db:
        image: postgres:9.5.4
        environment:
            POSTGRES_PASSWORD={{ postgres_password }}

    django:
        image: centos:7
        environment:
            POSTGRES_PASSWORD={{ postgres_password }}

 following command



And since Ansible Playbook also applies templating to variable files, we could share the same variable file
with Ansible Container and Ansible Playbook:

..  code-block:: bash

    ansible-container --var-file vars.yml build --with-vars POSTGRES_PASSWORD=${POSTGRES_PASSWORD} \
    -- -e"@/ansible-container/ansible/vars.yml"

Ansible filters and expressions are also available, if Ansible is installed in the same environment where Ansible Container
run. See `Ansible filters and lookups`_.

Passing environment variables
-----------------------------

Variable definitions can also be provided as environment variables. Create ``AC_*`` variables in the Ansible Container environment
that correspond to Jinja expressions in ``container.yml``. For example, to provide a value for the Jina expression
``{{ web_image }}``, define ``AC_WEB_IMAGE`` in the environment:

.. code-block:: bash

    $ export AC_WEB_IMAGE=centos:7

Ansible Container will detect the environment variable, remove ``AC_`` from the name, convert the remainder to lowercase,
and send the result to Jinja. Thus ``AC_WEB_IMAGE`` becomes ``web_image`` and gets transposed in ``container.yml`` to
``centos:7``.


Providing defaults
------------------

Default values for Jinja expressions can also be supplied by adding a top-level ``defaults`` section to ``container.yml``.

Using our original ``container.yml`` example from above, we could add a ``defaults`` section that looks like the
following:

.. code-block:: yaml

    version: "1"
    defaults:
        web_image: centos:7
        web_ports:
          - 8000:80
        debug: 0
        db_service:
            image: postgres:9.5.4
            expose:
              - 5432
            environment:
              - POSTGRES_DB_NAME=example
              - POSTGRES_USER=example
              - POSTGRES_PASSWORD=example
    services:
        web:
            image: {{ web_image }}
            ports: {{ web_ports }}
            command: ['sleep', '10']
            dev_overrides:
                environment:
                - DEBUG={{ debug }}
        db: {{ db_service }}
    registries: {}

If no ``--var-file`` or ``AC_*`` environment variables are provided, then the value found in ``defaults`` will be used to
resolve a Jina expression. For more on precedence see `Variable precedence`_.

Variable precedence
-------------------

Jinja expressions are resolved using variable definitions from the following sources:

* ``AC_*`` environment variables
* top-level ``defaults`` section added to ``container.yml``
* A JSON or YAML file provided using the ``--var-file`` option

You can set variable values using a single source or a combination of all three. Ansible Container gets values from
each source, combines all the definitions into a set, and passes the set to Jinja.

Sources are checked in the following order:

* The top-level ``default`` section in ``container.yml``
* A file passed using the ``--var-file`` option
* ``AC_*`` environment variables

The first source on the list gets the least precedence, and the last source gets the most precedence. In other words,
if the same variable is defined in each source, the value assigned to an ``AC_*`` environment variable wins.

For example, given the following ``defaults`` section in ``container.yml``:

.. code-block:: yaml

    version: "1"
    defaults:
        debug: 1
    ...

And given the following YAML variable file:

.. code-block:: yaml

    ---
    debug: 2

The value assigned to ``{{ debug }}`` would be: 2

If we were also given the environment value ``AC_DEBUG=3``, the value assigned would be: 3


Passing variables to your playbook:
-----------------------------------

The same variables passed to Ansible Container to resolve expressions in ``container.yml`` can also be passed to
Ansible Playbook during the ``build`` process using environment variables or files.

Environment variables
`````````````````````

Given an ``AC_*`` environment variable, you could simply do the following:

.. code-block:: yaml

    $ export AC_FOO=baz
    $ ansible-container build --with-variables AC_FOO=${AC_FOO}

The above adds the variable to the Ansible Builder container environment, and from there you can use a ``lookup`` filter
to access the value in your playbook:

.. code-block:: yaml

    - hosts: all
      vars:
        foo: "{{ lookup('env', 'AC_FOO' }}"
      tasks:
        - Copy file
          copy: src="{{ foo }}" dest=/some/path mode=0666 owner=user group=user

Variable files
``````````````

Given a YAML file containing variable definitions, you could pass it into the Ansible Playbook on the command line:

.. code-block:: bash

    $ ansible-container --var-file vars.yml build -- -e"@/ansible-container/vars.yml"

Or, by using the ``vars_files`` directive in your playbook:

.. code-block:: yaml

    - hosts: all
      vars_files:
         - /ansible-container/vars.yml
      tasks:
        ...

Or, by using the ``include_vars`` module:

.. code-block:: yaml

    - hosts: all
      tasks:
        - include_vars: file=/ansible-container/vars.yml


Using Ansible Vault
-------------------

`Ansible Vault <http://docs.ansible.com/ansible/playbooks_vault.html>`_ provides a way to encrypt and decrypt files, and
Ansible Playbook can also decrypt Vault files and use them as variable files.

To allow Ansible Container to decrypt your Vault, the Vault password file needs to be accessible to the Ansible Container and the option --vault-password-file used in the ansible_options part of the build command.

Either you put the password file in the ansible directory along with container.yml and it will be mounted and available
```
ansible-container build -- --vault-password-file /vault_password
```

Or the password file is in another location, its directory has to be shared with Docker engine in order to be mounted. 
```
ansible-container build --with-volumes /private/vault_password:/etc/vault_password -- --vault-password-file /etc/vault_password
``` 


Ansible filters and lookups
---------------------------

All Ansible Jinja filters and lookups are available for use in Ansible Container. See `Lookups <http://docs.ansible.com/ansible/playbooks_lookups.html#>`_
and `Jinja2 Filters <http://docs.ansible.com/ansible/playbooks_filters.html>`_.

.. note::

    Ansible Jinja filters and lookups are only available if Ansible is installed on the host where Ansible Container runs.
    Template rendering occurs outside of the Ansible Build Container, so access to Ansible filters and lookups requires that
    Ansible be installed locally. If Ansible is not installed, and ``container.yml`` includes references to Ansible filters
    and lookups, an error will occur.
