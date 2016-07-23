[![Build Status](https://travis-ci.org/ansible/ansible-container.svg)](https://travis-ci.org/ansible/ansible-container)
[![Code Coverage](https://codecov.io/gh/ansible/ansible-container/coverage.svg)](https://codecov.io/gh/ansible/ansible-container)

# Ansible Container

Ansible Container is a tool to build Docker images and orchestrate containers 
using only Ansible playbooks. 

## To install Ansible Container

Ansible Container is undergoing rapid development. For now, Ansible Container can only be installed from source. See [INSTALL.md](./INSTALL.md) for details.

## How it works

The `ansible-container init` command creates a directory `ansible` with files to get you started. Read the comments and edit to suit your needs.

The `ansible-container build [playbook-name]` command creates images from the Ansible playbooks in the `ansible` directory.
`main` is used as default playbook-name.

The `ansible-container run` command launches the containers specified in `container.yml`. The format is nearly identical to `docker-compose`.

The `ansible-container push` command pushes the project's images to a container registry of your choice.

The `ansible-container shipit` command will export the necessary playbooks and roles to deploy your containers to a supported cloud provider.

## Getting started

For examples and a tour of ansible-container 
[visit our docs site](http://docs.ansible.com/ansible-container/).
