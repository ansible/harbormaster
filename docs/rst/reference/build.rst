build
=====

.. program::ansible-container build

The ``ansible-container build`` command starts the Conductor container, and runs the Ansible roles for each service in ``container.yml``. For each service, it starts a container using the ``from`` image, and then generates and executes a playbook for each role.

Each playbook runs inside the Conductor, and executes tasks on the service container, using the Docker connection plugin. When finished, a commit is performed on the service container, the container is stopped, and an image is created for the service. At the end of a successful run of this command, a built image will exist for each custom service (i.e., a service defined with one or more Ansible roles). This is analogous to ``docker build``.

During a build, your project's contents are provided as a build context in the Conductor container at the file path ``/src``. Any files or patterns specified in a ``.dockerignore`` file will not be included in this build context.

.. option:: --flatten

By default, Ansible Container commits the changes your playbook made to the base image, but it retains the original layers from that base image. Specifying this option, Ansible Container flattens the union filesystem of your image to a single layer. This does break caching, so builds won'e be able to reuse cached layers and will fully rebuild your services even if you haven't changed anything.

.. note::

    The image is flattened by exporting the container to a tar file and re-importing the tar
    file as a new image. A side effect of performing this operation is a loss of image metadata.

.. option:: --no-purge-last

By default, upon successful completion of a build, the previously latest builds for
your hosts are deleted and purged from the engine. Specifying this option, the prior builds
are retained.

.. option:: --save-conductor-container

Leave the Ansible Conductor Container intact upon build completion. Use for debugging and testing.

.. option:: --services

Rather than performing an orchestrated build, only build the specified set of services.

.. option:: --no-cache

A shortcut for --no-conductor-cache and --no-container-cache.

.. option:: --no-conductor-cache

The process that builds the Conductor image uses the build engine's built-in caching mechanisms during rebuilds. The default engine is Docker. Use this option to disable the engine's build cache, and force a full build of the conductor image.

.. option:: --no-container-cache

During the build of each service image, a hash of each Ansible role is associated with the image layer produced when the role is first executed. If the role hash does not change between builds, then the associated image layer is used, and the role is not executed. Use this option to disable this caching mechanism, and force the execution of all roles.

.. option:: --with-variables WITH_VARIABLES [WITH_VARIABLES ...]

Define one or more environment variables in the Conductor container. Format each variable as a key=value string.

.. option:: --with-volumes WITH_VOLUMES [WITH_VOLUMES ...]

Mount one or more volumes to the Conductor container. Specify volumes as strings using the Docker volume format.

.. option:: --src-mount-path SRC_MOUNT_PATH

Specify the host path that should be mounted to the conductor at /src. Defaults to the directory from which ansible-container was invoked.

.. option:: --volume-driver VOLUME_DRIVER

Specify volume driver to use when mounting named volumes to the Conductor.

.. option:: --roles-path ROLES_PATH [ROLES_PATH ...]

If using roles not found in the ``roles`` directory within the project, use this option to specify one or more local paths containing the roles. The specified path(s) will be mounted to the conductor container, making the roles available to the build process.

.. option:: --use-local-python

Ansible Container will mount the ``/usr`` volume from the conductor container into the target container as ``/_usr`` and use the Python runtime from ``/_usr`` to run Ansible modules. Use this option to prevent this behavior, and force it to use the Python runtime found locally on the target container.

.. option:: ansible_options

You may also provide additional commandline arguments to give Ansible in executing your playbook. Use this option with care, as there is no real sanitation or validation of your input. It is recommended you only use this option to limit the hosts you build against (for example, if you only want to rebuild one container), to add extra variables, or to specify tags.

Note that for proper parsing, you will likely have to use ``--`` to separate the ansible-container options from the ansible-playbook options.

Caveats
```````

Ansible ordinarily connects to hosts it is managing via the SSH protocol. Ansible Container uses the latest Docker connection plugin to communicate from the Conductor container to the other containers. Since not all modules presently function with the Docker connection plugin, it limits the modules your playbook may rely on. As examples:

* The `become` methods do not work with Ansible Container, as `su` is disallowed in the Docker connection plugin (see `#16226 <https://github.com/ansible/ansible/pull/16226>`_), and `sudo` requires a TTY. Instead, use the `remote_user` parameter.

Also, remember that the ``ansible-playbook`` executable runs on your Conductor container, not your local host, and thus operates in the filesystem and network context of the build container.

If you run into the following error during build, you are likely using overlay or overlay2 docker storage backend.

.. code-block:: bash

    Traceback (most recent call last):
      File "/usr/lib/python2.7/site-packages/pip/basecommand.py", line 215, in main
        status = self.run(options, args)
      File "/usr/lib/python2.7/site-packages/pip/commands/install.py", line 342, in run
        prefix=options.prefix_path,
      File "/usr/lib/python2.7/site-packages/pip/req/req_set.py", line 778, in install
        requirement.uninstall(auto_confirm=True)
      File "/usr/lib/python2.7/site-packages/pip/req/req_install.py", line 754, in uninstall
        paths_to_remove.remove(auto_confirm)
      File "/usr/lib/python2.7/site-packages/pip/req/req_uninstall.py", line 115, in remove
        renames(path, new_path)
      File "/usr/lib/python2.7/site-packages/pip/utils/__init__.py", line 267, in renames
        shutil.move(old, new)
      File "/usr/lib64/python2.7/shutil.py", line 299, in move
        rmtree(src)
      File "/usr/lib64/python2.7/shutil.py", line 256, in rmtree
        onerror(os.rmdir, path, sys.exc_info())
      File "/usr/lib64/python2.7/shutil.py", line 254, in rmtree
        os.rmdir(path)
    OSError: [Errno 39] Directory not empty: '/usr/lib/python2.7/site-packages/chardet'

Unfortunately, there is `a bug <https://github.com/moby/moby/issues/12327>`_ present in pip which prevents installation of different versions.

You can resolve this issue by switching to a different graph backend, e.g. `devicemapper`.

.. code-block:: bash

    $ docker info | grep Storage
    Storage Driver: devicemapper
