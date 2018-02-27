The Conductor Container
=======================

The heavy lifting in Ansible Container is done by a specialized container called
the Conductor. It prepackages all of the things you'll need to build, run, and
deploy your application, including an Ansible runtime, associated libraries and
command-line utilities like a Docker client, and a Python runtime.

When you launch a build, the Conductor container communicates back out through
the container engine to the target containers you're building, so you don't need
`sshd` in your target containers or to worry about key exchange or authentication.
It mounts its Python runtime into your target containers during build, so you don't
even need Python in your target containers for Ansible modules to execute.

Because you're reusing the libraries and Python executable from your Conductor
in your target containers, the distribution of your Conductor really ought to
match the distribution of your target containers. If you're building CentOS 7
target containers, you should use a Conductor based on Centos 7 also. You must
specify your Conductor base image in the :ref:`settings` as part of your
``container.yml``.

Because rebuilding a Conductor image means downloading a bunch of dependencies,
Ansible Container offers ready-built images for the most popular Linux distributions
from which you can build your project's Conductor container image. This is done
transparently; if you specify ``centos:7`` as your ``conductor_base``, then the
ready-built image will be pulled from Docker Hub and used. We offer ready-built
base images for:

  * CentOS 7
  * Fedora 24, 25, and 26
  * Debian Jessie, Stretch, and Wheezy
  * Ubuntu Precise, Trusty, Xenial, and Zesty
  * Alpine 3.4 and 3.5

Baking your own Conductor base
------------------------------

You don't have to use our ready-built Conductor base images. You can build your
own, if you like, or you can build your own derivative of ours. Any Conductor base
image should:

1. It should be named ``container-conductor-$DISTRO-$TAG:$ANSIBLE_CONTAINER_VERSION``,
   so if you're building a Conductor base for OpenSuse 42.3 using Ansible Container
   1.0rc1, your Conductor base image should be named ``container-conductor-opensuse-42.3:1.0rc1``.
2. It should have the very latest Ansible and all of its dependencies.
3. It should have Ansible Container inside of it, as well as the requirements
   defined in ``container/conductor-build/conductor-requirements.txt``.
4. It should have all of the roles required in:
   ``container/conductor-build/conductor-requirements.yml``.
5. It should have the latest Docker CE commandline utilities.


