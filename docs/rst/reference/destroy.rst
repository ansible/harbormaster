destroy
=======

**New in version 0.9**

.. program:: ansible-container destroy

Stop then delete all containers for the services in *container.yml*, then destroy any built images for services. This will delete all service images, running
containers, and the conductor image.

.. option:: --production

By default, any `dev_overrides` specified in ``container.yml`` will be used and included in the orchestration playbook. Use this flag to ignore `dev_overrides`, and run containers using the production configuration. If containers were started using the `--production` option, then it's a good idea to use this option with the `destroy` command.

.. option:: --roles-path ROLES_PATH [ROLES_PATH ...]

If using roles not found in the ``roles`` directory within the project, use this option to specify one or more local paths containing the roles. The specified path(s) will be mounted to the conductor container, making the roles available to the build process.
