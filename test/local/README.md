# Test Local

This little project runs the unit and integration tests in a container.

It requires mounting a local copy of the ansible-container project to a path on the container that exactly matches the 
host path. Notice in ansible/container.yml the local copy of ansible-container is assumed to live at 
/projects/ansible-container, and it mounts that path to the container as /projects/ansible-container. The host and 
container paths match, and things work. If the paths don't match, it won't work as the Docker daemon (which is 
running on the host) will complain that it cannot find the path to mount the project.

Once you work out how to mount the local copy of ansible-container, the following will execute tests: 

```
$ cd ansible-continer/test/local
$ ansible-container build 
$ ansible-container run
```
