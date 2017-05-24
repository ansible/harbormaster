build
=====

.. program::ansible-container build

The ``ansible-container build`` command spins up the builder container and runs
your playbook against the base images described in the ``container.yml`` file. At
the end of a successful run of this command, in your container engine you will have
images built for each of the containers in your orchestration. This is analogous to
``docker build``.

.. option:: --flatten

By default, Ansible Container commits the changes your playbook made to the base image,
but it retains the original layers from that base image. Specifying this option, Ansible
Container flattens the union filesystem of your image to a single layer. This
does break caching, so builds won'e be able to reuse cached layers and will
fully rebuild your services even if you haven't changed anything.

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

The Conductor container uses your container engine's built-it caching mechanisms during
rebuilds, and Ansible Container will maintain its own per-role cache for your built images.
To disable these caches and ensure a clean rebuild, use this option.

.. option:: --no-container-cache

During builds the contents of the roles are used for caching indivual layers.
To disable these caches and ensure a clean rebuild, use this option.


.. option:: --with-variables WITH_VARIABLES [WITH_VARIABLES ...]

Define one or more environment variables in the Ansible Conductor container. Format each variable as a
key=value string.

.. option:: --use-local-python

Ansible Container will mount the ``/usr`` volume from the conductor container into the target container as ``/_usr``,
and use the Python runtime from ``/_usr`` to run Ansible modules. Use this option to prevent this behavior, and force
it to use the Python runtime found locally on the target container.

.. option:: ansible_options

You may also provide additional commandline arguments to give Ansible in executing your
playbook. Use this option with care, as there is no real sanitation or validation of
your input. It is recommended you only use this option to limit the hosts you build
against (for example, if you only want to rebuild one container), to add extra variables,
or to specify tags.

Note that for proper parsing, you will likely have to use ``--`` to separate the
ansible-container options from the ansible-playbook options.

Caveats
```````

Ansible ordinarily connects to hosts it is managing via the SSH protocol. Ansible Container
uses the latest Docker connection plugin to communicate from the Ansible Builder Container to
the other containers. Since not all modules presently function with the Docker connection plugin, 
it limits the modules your playbook may rely on. As examples:

* The `become` methods do not work with Ansible Container, as `su` is disallowed in the Docker
  connection plugin (see `#16226 <https://github.com/ansible/ansible/pull/16226>`_)
  and `sudo` requires a TTY. Instead, use the `remote_user` parameter.

Also, remember that the ``ansible-playbook`` executable runs on your Conductor container, not
your local host, and thus operates in the filesystem and network context of the build container.
