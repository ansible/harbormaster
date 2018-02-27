## Running tests

Unit and integration tests live here. When a pull request is submitted, tests are automatically executed on Travis to test the submitted code.

Running tests locally requires cloning the Ansible Container repo, and setting up your environment to run from source. See the [Installation
 Guide](https://docs.ansible.com/ansible-container/installation.html) for assistance.

You will also need the latest Ansible installed from source. See Ansible's [running from source guide](http://docs.ansible.com/ansible/intro_installation.html#running-from-source) for assistance.

Test execution is initiated by running the following: 

```
# Set your working directory
$ cd ansible-container

# Start tests
$ python ./setup.py test 
```

Test execution occurs exactly the same way on Travis as it does in a local development environment. So if tests run successfully in your local
environment, they *should* run successfully on Travis.

Thanks for trying out Ansible Container!
