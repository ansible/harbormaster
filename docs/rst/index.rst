Welcome to ansible-container!
=============================
Ansible Container provides an Ansible-centric workflow for building, running, testing, and deploying containers.

Ansible Container enables you to build container images and orchestrate them using only Ansible playbooks. Describe
your application in a single YAML file and, rather than using a Dockerfile, list Ansible roles that make up your
container images. Ansible Container will take it from there.

With Ansible Container, you no longer have to build and configure containers differently than you do traditional
virtual machines or bare-metal systems. You can now apply the power of Ansible and re-use your existing Ansible content
for your containerized ecosystem. Use templates, copy files, drop in encrypted data, handle errors, add conditionals, and more.
Everything Ansible brings to orchestrating your infrastructure can now be applied to the image build process.

But Ansible Container does not stop there. Use Ansible Container to run the application, and push images to private and
public registries. When you are ready to deploy to the cloud, use it to generate an Ansible playbook that automates the
deployment.


.. toctree::
   :maxdepth: 2

   installation
   getting_started
   conductor
   migrating
   registry_auth
   reference/index
   container_yml/index
   roles/index
   Roadmap<roadmaps/index>
   community/index
   openshift/index

