# Ansible Container

Ansible Container is a tool to build Docker images and orchestrate containers
using only Ansible playbooks. It does this by building a container from which
to execute Ansible and connects to your other containers via the Docker engine
instead of SSH.

And when you're ready to deploy to the cloud, use Ansible Container's *shipit* 
command to generate an Ansible Role that deploys your application. The role is 
generated from your project's docker-compose file, leveraging the time
and work already invested in Docker compose.

## Why? Why not just use standard Docker tools?

1. `Dockerfile` does wrong many of the things Ansible does right.
We're well past the point where we should be managing build processes
with manually maintained series of shell scripts. That's why we wrote Ansible
in the first place.
2. Ansible Container permits orchestration even during the build process, whereas
`docker build` does not. For example, in a Django project, your VCS may contain
a bunch of sources for static assets that need to be compiled and then
collected. With Ansible Container, you can compile the static assets in your Django
container and then collect them into your static file serving container.
3. Many people use Docker for development environments only but then use
Ansible playbooks to push out to staging or production. This allows you to use
the same playbooks and roles in your Docker environment as in your production
environments.
4. Ansible Container does all of this without installing SSH, leaving Ansible
droppings on your built images, or having excess layers to the union filesystem.
5. When you're ready to deploy to the cloud, Docker compose leaves you with only one 
option. Ansible Container's *shipit* command enables the deployment of your app on a 
a number of cloud infrastructures without you having to write a single
line of code.

## To Ansible-Container-ize your project

Run `ansible-container init` in the root directory of your project. This will create
a directory `ansible` with files to get you started. Read the comments and
edit to suit your needs.

## To use Ansible Container

1. `ansible-container build` - This will make your Ansible Container builder and
use Ansible to build the images for your other containers. By the end of this
run, you will have flattened, tagged images in your local Docker engine.

2. `ansible-container run` - This will orchestrate running your images as described
in your `container.yml` file, using the Ansible-Container-built images instead of
the base images.

3. `ansible-container push` - This will push your Ansible-Container-built images to a
registry of your choice.

When you're ready to deploy to the cloud:

4. `ansible-container shipit` - This will read your docker-container.yml file and create an Ansible
role for deploying your project to [OpenShift](https://www.openshift.org/). Additional cloud providers 
are under development, including: Google Container Engine and Amazon EC2 Container Service.

Feel free to see the `test` or `test-v1` projects as an examples.

### As a container

If you want to run ansible-container as a container, a Dockerfile is provided
to build a Fedora based container image.

After building the container image a handy alias like ```docker run --privileged -v `pwd`:/work:Z -v /var/run/docker.sock:/var/run/docker.sock:Z ansible-container build``` will help... 


