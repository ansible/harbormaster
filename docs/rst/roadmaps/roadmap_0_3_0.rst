Roadmap for release 0.3.0
=========================

**Target delivery: Early December 2016**

- **Build Cache** (Jag @j00bar)
  - One of the niceties of Dockerfile is that Docker Engine re-uses cached layers to accelerate rebuilds. We should be able to create
    something similar using a custom Ansible execution strategy.
  - Build and test new execution strategy
  - Add CLI option to enable the new strategy in the build command
  - Tracked on issue `#143 <https://github.com/ansible/ansible-container/issues/143>`_.

- **Docker Compose v2 Support** (House @chouseknecht)
  - Proposal document `<./../../proposals/compose-v2.md>`_.
  - Enables support of features in Docker engine such as volumes and networks
  - Allow for use of Compose v2 file format and directives
  - Tracked on issue `#67 <https://github.com/ansible/ansible-container/issues/67>`_.

- **Docker v1.12 Support** (House @chouseknecht)
  - Tracked on issue `#99 <https://github.com/ansible/ansible-container/issues/99>`_.
  - Tracked on issue `#147 <https://github.com/ansible/ansible-container/issues/147>`_.
