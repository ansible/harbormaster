Ansible Container Changes by Release
====================================

0.9.3 - Active development
--------------------------


0.9.2 - Released 12-Sep-2017
----------------------------

Major changes
`````````````
- Pre-baked conductor images for major releases of CentOS, Fedora, Debian, Ubuntu and Alpine
- Added support for ``secrets``, which uses Ansible Vault to seed secret objects in Docker, K8s, and OpenShift
- Added support for mulit-container pods

Minor changes
`````````````
- Split ``--no-cache`` option for the ``build`` command into two options: ``--no-conductor-cache`` and ``--no-contianer-cache``
- Added ``repository_prefix`` attribute to a registry defined in ``registry`` section of ``container.yml`` 
- Added ``conductor`` directive to ``settings`` section of ``container.yml``
- Added ``pull_from`` attribute to a registry defined in ``registry`` section of ``container.yml``
- Added ``--vars-files`` option to ``stop`` and ``restart`` commands
- Pull missing images during ``build``
- Added ``vars_files`` directive to ``settings`` section of ``container.yml`` 
- Support for multiple roles paths
- Install the ``sudo`` package to Debian based conductors
- Add environment variables defined via ``--with-variable``, or the ``environment`` section of ``settings.conductor`` in ``container.yml``, to the conductor image
- Add full role definition string to the cache fingerprint, making the build cache a little more accurate
- Added ``--src-mount-path`` option to ``build`` command
- Added ``--volume-driver`` option to ``build`` command

Deprecations
````````````
None.

Closed Pull Requests
````````````````````
- `715 Updates Jinja template doc <https://github.com/ansible/ansible-container/pull/715>`_
- `712 Update ROADMAP.rst to reflect 1.0.0 correctly <https://github.com/ansible/ansible-container/pull/712>`_
- `702 Require the Docker >= 2.4.0 Python library (#564) <https://github.com/ansible/ansible-container/pull/702>`_
- `699 Adds changelog <https://github.com/ansible/ansible-container/pull/699>`_
- `698 Add CLI options to specify /src mount path and volume driver <https://github.com/ansible/ansible-container/pull/698>`_
- `695 Removes service level defaults from cache fingerprint <https://github.com/ansible/ansible-container/pull/695>`_
- `690 Mount secrets consistent with Kubernetes <https://github.com/ansible/ansible-container/pull/690>`_
- `689 Add conductor environment during build <https://github.com/ansible/ansible-container/pull/689>`_
- `687 Fixes bugs related to secrets <https://github.com/ansible/ansible-container/pull/687>`_
- `686 Require Pip >= 6.0 for the match_markers method (#543) <https://github.com/ansible/ansible-container/pull/686>`_
- `684 Install the sudo package on Debian based operating systems <https://github.com/ansible/ansible-container/pull/684>`_
- `678 Build cache fix <https://github.com/ansible/ansible-container/pull/678>`_
- `676 Remove broken "self" before Docker engine's "repository_prefix" reference <https://github.com/ansible/ansible-container/pull/676>`_
- `675 Adds install docs <https://github.com/ansible/ansible-container/pull/675>`_
- `674 Update split in docker pull <https://github.com/ansible/ansible-container/pull/674>`_
- `672 Fixes #658 by adding ~/.ansible/roles to conductor ANSIBLE_ROLES_PATH <https://github.com/ansible/ansible-container/pull/672>`_
- `670 WIP - buildah support <https://github.com/ansible/ansible-container/pull/670>`_
- `668 Remove unused docker-compose templates <https://github.com/ansible/ansible-container/pull/668>`_
- `667 Support multiple roles paths <https://github.com/ansible/ansible-container/pull/667>`_
- `665 Support secrets vault <https://github.com/ansible/ansible-container/pull/665>`_
- `664 Allow for ${PWD} in settings.volumes <https://github.com/ansible/ansible-container/pull/664>`_
- `663 Allow for ${PWD} in settings.volumes <https://github.com/ansible/ansible-container/pull/663>`_
- `662 Only break when key is not present <https://github.com/ansible/ansible-container/pull/662>`_
- `661 Fixes #147 COMPOSE_HTTP_TIMEOUT regression <https://github.com/ansible/ansible-container/pull/661>`_
- `660 Fixes #147 COMPOSE_HTTP_TIMEOUT regression <https://github.com/ansible/ansible-container/pull/660>`_
- `657 Fix chardet package conflict <https://github.com/ansible/ansible-container/pull/657>`_
- `655 Fixes missing build files when using --project-path <https://github.com/ansible/ansible-container/pull/655>`_
- `654 Fix pip install commands with extra_requires <https://github.com/ansible/ansible-container/pull/654>`_
- `652 When pulling images, default tag to 'latest' <https://github.com/ansible/ansible-container/pull/652>`_
- `651 Adds var_file to settings in container.yml <https://github.com/ansible/ansible-container/pull/651>`_
- `650 Fix k8s image path <https://github.com/ansible/ansible-container/pull/650>`_
- `647 Revert "When registry_prefix == '', don't override with project_name" <https://github.com/ansible/ansible-container/pull/647>`_
- `646 When registry_prefix == '', don't override with project_name <https://github.com/ansible/ansible-container/pull/646>`_
- `645 Pull missing images during build <https://github.com/ansible/ansible-container/pull/645>`_
- `639 Add proposal for Multiple Containers per Pod <https://github.com/ansible/ansible-container/pull/639>`_
