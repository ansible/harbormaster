[![Build Status](https://travis-ci.org/ansible/ansible-container.svg)](https://travis-ci.org/ansible/ansible-container)
[![Code Coverage](https://codecov.io/gh/ansible/ansible-container/coverage.svg)](https://codecov.io/gh/ansible/ansible-container)

# Ansible Container

Ansible Container is a tool to build Docker images and orchestrate containers 
using only Ansible playbooks. 

## To install Ansible Container

Ansible Container is undergoing rapid development. For now, Ansible Container can only be installed from source. See [INSTALL.md](./INSTALL.md) for details.

## How it works

The `ansible-container init` command creates a directory `ansible` with files to get you started. Read the comments and edit to suit your needs.

The `ansible-container build` command creates images from the Ansible playbooks in the `ansible` directory.

The `ansible-container run` command launches the containers specified in `container.yml`. The format is nearly identical to `docker-compose`.

The `ansible-container push` command pushes the project's images to a container registry of your choice.

The `ansible-container shipit` command will export the necessary playbooks and roles to deploy your containers to a supported cloud provider.

## Getting started

For examples and a tour of ansible-container 
[visit our docs site](http://docs.ansible.com/ansible-container/).

## Get Involved

   * Read [Community Information](http://docs.ansible.com/community.html) for all kinds of ways to contribute to and interact with the project, including mailing list information and how to submit bug reports and code to Ansible.  
   * All code submissions are done through pull requests.  Take care to make sure no merge commits are in the submission, and use `git rebase` vs `git merge` for this reason.  If submitting a large code change (other than modules), it's probably a good idea to join ansible-devel and talk about what you would like to do or add first and to avoid duplicate efforts.  This not only helps everyone know what's going on, it also helps save time and effort if we decide some changes are needed.
   * Users list: [ansible-project](http://groups.google.com/group/ansible-project)
   * Development list: [ansible-devel](http://groups.google.com/group/ansible-devel)
   * Announcement list: [ansible-announce](http://groups.google.com/group/ansible-announce) - read only
   * irc.freenode.net: #ansible-container
