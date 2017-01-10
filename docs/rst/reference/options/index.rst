
optional arguments
==================

Use the following optional arguments with the ``ansible-container`` command: 

.. option:: -h, --help

Show help message and exit.

.. option:: --debug

Enable debug output.

.. option:: --engine ENGINE_NAME

Select your container engine and orchestrator. Defaults to *docker*.

.. option:: --no-selinux

Stops the 'Z' option from being added to any volumes that get automatically mounted to the build container. For example, the base path to the project is automatically mounted as */ansible-container:Z*.

.. option:: --project BASE_PATH, -p BASE_PATH

Specify a path to your project. Defaults to the current working directory.

.. option:: --var-file

**New in version 0.2.0**

Path to a YAML or JSON formatted file providing variables for Jinja2 template rendering in container.yml. Provide an absolute
file path, or a path relative to the *project BASE_PATH* or relative to *project BASE_PATH/ansible*. If the file
extension is one of 'yml' or 'yaml', the file will be parsed as YAML. Otherwise, it is parsed as JSON.
