destroy
=======

**New in version 0.9**

.. program:: ansible-container destroy

Stop then delete all containers for the services in *container.yml*, then destroy any built images for services. This will delete all service images, running
containers, and the conductor image.

.. option:: --production

By default, any `dev_overrides` specified in ``container.yml`` will be used and included in the orchestration playbook. Use this flag to ignore `dev_overrides`, and run containers using the production configuration. If containers were started using the `--production` option, then it's a good idea to use this option with the `destroy` command.
