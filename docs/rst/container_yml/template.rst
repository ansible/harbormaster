Jinja Templating
================

**Revised in 0.9.0**

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
        image: '{{ web_image }}'
        ports: '{{ web_ports }}'
        command: ['sleep', '10']
        dev_overrides:
            environment:
            - DEBUG='{{ debug }}'
    registries: {}

Place expressions inside of quotes, as above.

Variable definitions are needed for Jinja to resolve expressions. In the above example, definitions are required for ``web_image``, ``web_reports``,
and ``debug``.

.. note::

    Resolving Jinja expressions to render the final ``container.yml`` is done inside the ``conductor`` container.


There are three ways to provide variable values:

* Role defaults
* Passing a YAML or JSON file with the ``--vars-file`` option
* Environment variables
* Top-level ``defaults`` section in ``container.yml``

See `Passing environment variables`_ , `Top-level defaults`_, `Passing variable files`_, and `Variable precedence`_ for
a deeper discussion of variables. For the purpose of understanding how template rendering works, we'll consider a file.

Use the ``--vars-file`` option to provide the path of a file containing variable definitions, where the file format can be YAML or JSON.
For example, the following passes a YAML file, ``devel.yaml``, to the build command:

.. code-block:: bash

    $ ansible-container --vars-file devel.yaml build

Suppose ``devel.yaml`` contains the following variable definitions:

 .. code-block:: yaml 

    ---
    debug: 1
    web_ports:
      - 8000:8000
    web_image: "python:2.7"

Variables can be defined as simple string, integer, or float types, or they can be complex data structures.

Before the ``build`` command can be executed, Jinja is called to perform template rendering. Ansible Container reads the contents of the variable file, ``devel.yaml`` and passes it to Jinja along with a copy
of ``container.yml``. Jinja performs the transformation, returning a copy of ``container.yml`` with all of the expressions replaced by actual values.

The following is the transformed ``container.yml``:

.. code-block:: yaml

    version: "2"
    services:
      web:
        from: "python:2.7"
        ports:
          - 8000:8000
        command: ['sleep', '10']
        dev_overrides:
            environment:
              - DEBUG=1
    registries: {}

Passing variable files
----------------------

Pass the path to a file containing variable definitions using the ``--vars-file`` option. The file path must be one of
the following:

* Absolute file path
* Relative to the project path
* Relative to the ``ansible`` folder

When ``--vars-file`` is passed, Ansible Container checks if the path is an absolute path to a file. If not, it checks for the
file relative to the project path, which is the current working directory or a path specified using the ``--project`` option.
If the file is still not found, it looks for the file relative to the ``ansible`` folder within the project path.

Variable files can also be specified using the ``vars_files`` directive under ``settings`` in ``container.yml``. For example:

.. code-block:: yaml

    version: '2'
    settings:
      conductor:
        base: 'centos:7'
      vars_files:
      - vars.yml
      - /data/more_vars.yml
    services:
    ...

YAML vs JSON
````````````
The filename extension determines how the file is parsed. If the name ends with ``.yaml`` or ``.yml``, contents are parsed
as YAML, otherwise contents are parsed as JSON.

Passing environment variables
-----------------------------

Variable definitions can also be provided as environment variables. Create ``AC_*`` variables in the Ansible Container environment
that correspond to Jinja expressions in ``container.yml``. For example, to provide a value for the Jina expression
``{{ web_image }}``, define ``AC_WEB_IMAGE`` in the environment:

.. code-block:: bash

    $ export AC_WEB_IMAGE=centos:7

Ansible Container will detect the environment variable, remove ``AC_`` from the name, convert the remainder to lowercase,
and send the result to Jinja. Thus, ``AC_WEB_IMAGE`` becomes ``web_image``, and gets transposed in ``container.yml`` to
``centos:7``.

It is often necessary to manage variables outside the project (e.g. in a CI/CD context, build/dev environment, etc).
Environmental variables from the shell/parent process can be expanded inside the following sections.

* A service's ``environment`` section, making them available to the container process.
* Values inside ``vars-files`` and the ``defaults`` section, making them available to roles and playbooks in the 
  ``ansible-container`` workflow.

.. code-block:: yaml

    defaults:
        env: '$CI_ENVIRONMENT_NAME'             # Default 'env' here from the environment 
                                                # unless set in a 'var-file'

    services:
        web:
            environment:
                - ENV_NAME={{ env }}            # Set the ENV_NAME docker ENV variable for the container
                - HTTP_PROXY=$HTTP_PROXY        # Allow container process(es) to use the same proxy
                - HTTPS_PROXY=$HTTP_PROXY       # settings as those of a build/CI environment
                - POSTGRES_DB_NAME=$CI_ENV-foo  # Expand to 'dev-foo', 'test-foo', 'prod-foo', etc

Top-level defaults
------------------

Use the top-level ``defaults`` section to define default values, as demonstrated in the following example:

.. code-block:: yaml

    version: '2'
    defaults:
      web_image: centos:7
      web_ports:
        - 8000:80
      debug: 0
    services:
      web:
        from: {{ web_image }}
        roles:
        - role: apache
        ports: {{ web_ports }}
        command: ['sleep', '10']
        dev_overrides:
            environment:
            - DEBUG={{ debug }}
    registries: {}


Variable precedence
-------------------

Prior to resolving variables at the service level, a global set of variables is formed using environment variables, top-level ``defaults``, and any variable files. The order of precedence here is given first to environment variables, then variable files, and finally to top-level ``defaults``. In other words, top-level ``defaults`` receive the lowest precedence, and environment variables receive the highest.

At the service level, role variables and role metadata come into play. Precedence is given first to values defined for the service in ``container.yml``, then to the role's metadata found in ``meta/container.yml``, then to role defaults in ``defaults/meta.yml``, and finally to global variables.

