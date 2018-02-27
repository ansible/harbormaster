Roadmap for Release 0.9.0
=========================

Release 0.9.0 represented a complete rethinking of the project's architecture with the goal of creating a flexible framework capable of supporting multiple build and deployment engines. What follows is a summary of the major changes introduced by the release.

Refactor plan
-------------

* The "builder container" will now be referred to as the "conductor".
* Outside of the container on the host OS should be four and precisely four bits of functionality: Building the conductor container, launching the conductor container, `init`, and Project Starbuck (see below).
* The global `setup.py` should specify an `entry_points['console_script']` that invokes a super thin wrapper. All the wrapper should do is:

      1. Parse arguments
      2. Build the conductor container.

          * Does this mean we need Docker for every install?

      3. Launch the conductor container using the specified command.

* The vast majority of all of the Ansible Container logic goes into the conductor. Like, everything. The global `setup.py` file installs this code as data, not as code. There's no way to `import` the Ansible Container logic from the machine `ansible-container` is installed on.
* The build process for the conductor uses the `$PWD` as the build context.
  To build the conductor:

      1. Put the Ansible Container logic payload into the container.
      2. Make a virtualenv.
      3. Run the `setup.py` from the payload.
      4. If a `requirements.txt` is in the build context, collect requirements.
      5. If a `requirements.yml` is in the build context, collect requirements.

Changes to `container.yml`
--------------------------

* All Ansible Container artifacts (`container.yml`, `requirements.yml`, etc.)
  will be moved out of the `ansible/` directory and into the project root.
* The `main.yml` file is no longer a thing. We got rid of it. It's gone.
* The "fidelity to `docker-compose.yml`" preference is hereby abandoned.
* New keys to `container.yml` services:

    * `from` - The base image to use for builds.
    * `roles` - An array of role references to run on top of the base image. Each role will be committed as a layer on the final built image.

* New top-level keys:

    * `settings` which optionally contain:

        * `engine` - the name of the preferred container engine
        * `conductor_base` - the name of a base image from which to build your conductor. The idea here is that if you're building images against a Debian base, needing `python-apt` for instance, you want a Debian conductor.
        * `vault_file` - the relative path to a vault file that should be used by runs of Ansible Container in the conductor.

Changes to `engine.py`
----------------------

* The generic `Engine` class will cover `build`, `run`, and `shipit`.
* The `build` process:

    * The `virtualenv` from the conductor will be exported into each built service. The Python runtime used by Ansible is this `virtualenv` - no need to have a Python binary in the target containers.
    * Per service in `container.yml`

        * Start a container based on the `from` image.
        * Sequentially for each role in `roles`, generate an Ansible playbook in `/tmp` that runs as tasks any `OnBuild` directives from the parent image, applies the role, and runs `ansible-playbook`.
        * Stops the running container and commits the container as an image layer. As part of that commit, any data in `container/meta.yml` is included as part of the commit.

    * Caching becomes a question of calculating role checksums, and skipping role application if unnecessary. No execution strategy needed.

* The `run` process:

    * Generate an Ansible artifact that orchestrates the built images in `/tmp` and run `ansible-playbook` on it.

* There is no `push` command anymore.
* The `deploy` process (previously called `shipit`):

    * Pushes the built images to the configured registry.
    * Re-uses the same code to generate the Ansible artifact that orchestrates the built images, however instead of writing to `/tmp` space, it writes it to a mounted volume, referencing the registry names of the images instead of the local ones.

Adding an import feature
------------------------

An additional `console_script` will be included that digests a Dockerfile and
outputs a container-enabled role and `container.yml`

A Dockerfile has a limited number of directives. They will be translated into
a container-enabled role as follows:

* ``RUN``: translate to a task with the ``command`` module; breaking up ``&&`` commands as best you can into separate ``command`` tasks.
* ``ADD`/`COPY``: translate into ``copy`` or ``synchronize`` tasks
* Every other directive except ``FROM`` will be added to ``container/meta.yml``

Any comments in the Dockerfile should be preserved in the appropriate places in
the ``tasks/main.yml`` of the outputted role.

Additionally, a ``container.yml`` will be generated simply containing the one
service, with the contents of the ``FROM`` directive as the ``from`` key and the
role name as the only entry in the ``roles`` array.

Misc.
-----

* Come up with a better way to organize templates and other supporting files for each engine.