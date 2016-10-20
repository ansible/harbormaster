[![Build Status](https://travis-ci.org/ansible/ansible-container.svg)](https://travis-ci.org/ansible/ansible-container)
[![Code Coverage](https://codecov.io/gh/ansible/ansible-container/coverage.svg)](https://codecov.io/gh/ansible/ansible-container)

# Ansible Container

Ansible Container is a tool to build Docker images and orchestrate containers using only Ansible playbooks.

## How it works

Use Ansible Container to manage container lifecycle from development, through testing, to production:

* `ansible-container init`

  Creates a directory *ansible* with files to get you started. Read the comments and edit to suit your needs.

* `ansible-container install`

  Downloads Ansible-Container-ready roles from Ansible Galaxy and installs them in your project.

* `ansible-container build`

  Creates images from your Ansible playbooks.

* `ansible-container run`

  Launches the containers specified in the orchestration document, *container.yml*, for testing the built images. The 
  format of *container.yml* is nearly identical to Docker Compose.

* `ansible-container push`

  Pushes the project's images to a container registry of your choice.

* `ansible-container shipit`

  Generates the necessary playbook and role to deploy your containers on a supported cloud provider.

## Installing

Install using *pip*, the Python package manager:

    $ sudo pip install ansible-container
    
Or, to install without root privileges, use [virtualenv](https://virtualenv.pypa.io/en/stable/) to first create a 
Python sandbox:
    
    $ virtualenv ansible-container
    $ source ansible-container/bin/activate
    $ pip install ansible-container

For more details, prerequisite, and instructions on installing the latest development release, please view our 
[Installation Guide](https://docs.ansible.com/ansible-container/installation.html).


## Getting started

For examples and a tour of Ansible Container [visit our docs site](https://docs.ansible.com/ansible-container/).

If you just can't wait, the following provides a quick install and run of the demo app.

Assuming you already installed Ansible Container, start by creating an empty project folder, and then initialize it with a Container App from [Ansible Galaxy](https://galaxy.ansible.com):

```
$ mkdir demo
$ cd demo
$ ansible-container init j00bar.django-gulp-nginx
```

From the project directory, build the images:

```
$ ansible-container build
```

And finally, from the project directory, run the app:

```
$ ansible-container run
```

The demo web server is available at port 8080. If you're running Docker Machine, for example, you can access the 
site using the IP address of the Docker Machine host like so:

```
$ open http://$(docker-machine ip default):8080/admin
```
(Replace *default* with the name of your Docker Machine host.)

## Get Involved

* Visit [Community Information and Contributing](https://docs.ansible.com/ansible-container/community/index.html) 
  for all kinds of ways to contribute to and interact with the project. We welcome your feedback and ideas!
* Review [CONTRIBUTORS.md](./CONTRIBUTORS.md), if you're considering submitting code.
* [Join the  mailing list](https://groups.google.com/forum/#!forum/ansible-container)
* [Open an issue](https://github.com/ansible/ansible-container/issues)
* Join the #ansible-container channel on irc.freenode.net.  

## Branch Information

 * The *develop* branch is the release actively under development.
 * The *master* branch corresponds to the latest stable release available at [PyPi](https://pypi.org/project/ansible-container/).
 * Submit pull requests for bug fixes and new features to *develop*.
 * View [the roadmap](./ROADMAP.rst) for a list of features currently under development.
 * Contributors welcome! Get started by reviewing [CONTRIBUTORS.md](./CONTRIBUTORS.md).

## Authors

View [AUTHORS](./AUTHORS) for a list contributors to Ansible Container. Thanks everyone!

Ansible Container is an [Ansible by Red Hat](https://ansible.com) sponsored project.
