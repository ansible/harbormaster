
Optional Arguments
==================

Use the following optional arguments with the ``ansible-container`` command: 

.. option:: -h, --help

Show help message and exit.

.. option:: --debug

Enable debug-level logging for all ``ansible-container`` actions, both inside and outside of the ``conductor``.

.. note::

    If you're only interested in debugging the Ansible playbook being executed, consider passing ``-- -vvvv`` to increase ``ansible-playbook`` verbosity, without increasing the logging level of ``ansible-container``.

.. option:: --devel

Enable ``developer mode`` by bind mounting locally installed ``ansible-container`` code to the ``conductor``. Useful when working on the ``ansible-container`` codebase, as it allows testing changes without rebuilding the ``conductor`` image.

Instead of building ansible-container Python source into the ``conductor``, this option mounts the ``ansible-container`` codebase from the host machine for every command. Mounting the source every time means you don't have to rebuild the conductor container to update the code, speeding up the dev-test-run cycle immensely.

.. option:: --engine ENGINE_NAME

Select your container engine and orchestrator. Valid options are: ``docker``, ``k8s``, ``openshift``. Defaults to ``docker``.

.. option:: --project-path BASE_PATH, -p BASE_PATH

Specify a path to your project. Defaults to current working directory.

.. option:: --project-name PROJECT_NAME, -n PROJECT_NAME

Specify an alternate name for your project. Defaults to the base name of the project path.

.. option:: --vars-files VARS_FILES, --var-file VARS_FILES, --vars-file VARS_FILES

One or or more YAML or JSON formatted files providing variables for Jinja2 style variable substitution in ``container.yml``.

.. option:: --no-selinux

Disables the 'Z' option from being set on volumes automatically mounted to the ``conductor`` container.

.. option:: --config-file CONFIG_FILE, -c CONFIG_FILE

**New in version 0.9.3**

Configuration filename. Use to provide a path to a configuration file. Defaults to ``container.yml``.
