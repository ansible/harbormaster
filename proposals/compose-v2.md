# Add Support for Compose V2

Table of contents: 

- [Purpose](#purpose)
- [Guidelines for container.yml](#guidelines)
- [Implementing Compose V2](#compose)
- [Specification for container.yml](#specification)
- [References](#references)

<h2 id="purpose">Purpose</h2>

- Add support for Docker Compose v2
- Provide a specification for `container.yml`
- Establish guidelines for maintaining `container.yml`

<h2 id="guidelines">Guidelines for container.yml</h2>

- A primary goal for `container.yml` is to provide a single source of orchestration for the project, which means it must always:

    - Accurately describe orchestration for each environment in the application lifecycle: development, testing, production
    - Support ${} environment variable substitution
    - Support Jinja templating
    - Be forward compatible such that a `container.yml` that worked in prior version of Ansible Container continues to work in a newer version. 

- One benefit to using Ansible Container is that the orchestration is based on Docker Compose, and to maintain that benefit `container.yml` must:

    - Support the foundational elements of Docker Compose that describe expected container state and container relationships
    - Provide clear documentation on which Compose directives are supported, and which are not
    - Handle an encounter with unsupported directives in a way that is clear and non-destructive
    - Not change or deviate from the original meaning or intent of a directive
    - Maintain a structure in `container.yml` that feels and looks very close to Compose
    - Minus any new sections (e.g. dev_overrides, options, defaults, etc.) the remaining document should pass docker-compose validation

- If Ansible Container is to remain relevant it must evolve to supports cloud work flows and objects, the following will inform how new functionality is 
added:

    - Original Compose directives cannot be re-purposed
    - New directives must be added to new sections of the document (i.e. *dev_overrides* and *options*) and not inserted into existing sections or existing directive
    structures
    - A directive must carry the same meaning across environments. For example, the *ports* directive is used to map container ports to the outside world, with the 
    intention of making a service running inside a container accessible. The implementation between a laptop development environment and deployment to a cloud 
    orchestration platform is different, but the meaning and intended outcome is the same.

-  **If it doesn't map to the cloud, it's not supported.**

    - Overall, as we consider which directives to support, we need to remember that one of our stated objectives is to manage the container lifecycle from laptop 
    development to cloud deployment. For that to work, an application cannot be built with directives that only work on the laptop or provide functionality that cannot 
    be replicated in the cloud. And so as a general rule, if a directive does not map to cloud orchestration, it cannot be supported.

<h2 id="compose">Implementing Compose V2</h2>

Compose v2 will be implemented when:

- *Version* can be set to 2
- In development, when unsupported directives are included in *container.yml*, they are detected, the user is notified, and execution is halted 
- In development, minus custom directives the remaining contents of `container.yml` passes validation by docker-compose and successfully executes
- In production, supported directives generate valid configuration for each supported cloud platform

### Generating configuration for supported cloud platforms

#### Shipit 

The `shipit` command will continue to be supported, and will continue to generate a deployment playbook and role. All supported directives will be implemented in `shipit`, and 
documentation describing mapping details will be developed. 

#### Kompose

An engine that sits next to the current docker engine will be built for [Kompose](https://github.com/kubernetes-incubator/kompose). It will do the following: 

- provide an option to convert `container.yml` to configuration file(s) stored on the file system
- provide a `run` option that deploys the application to a selected platform
- provide a `stop` option that deletes the application form the selected platform

Details regarding how `container.yml` maps to cloud configuration will be handled by the Kompose binary. However, mapping documentation seems to be non-existant, so if time 
permitsm we will develop a reference and submit upstream. If directives we believe should be supported are not, we will add support and submit the code upstream. Details will 
be worked out and documented as development progresses and we learn more about Kompose.

<h2 id="specification">Specification for container.yml</h2>

The following details provide at least a beginning specification for `container.yml`. More details will be added and incorporated into the docs site as development of 
the `shipit` command and a `kompose` engine progress.  

### Supported directives

The following tables track which Compose directives are supported. All directives from V1 and V2 are included for consideration. See notes below for implementation
details.

#### Top-level Directives 

| Directive         | Definition                                        | Supported      |
| ---------         | ----------                                        |      :---:     |  
| Version           | Specify the Compose version, either 1 or 2        | &#10004;       |
| volumes           | Create named, persistent volumes                  | &#10004;       |
| networks          | Create named, persistent networks                 |                | 

#### Directives 

| Directive         | Definition                                        | Supported      |
| ---------         | ----------                                        |      :---:     |  
| build             | Run Dockerfile based build                        |                |
| cap_add, cap_drop | Add or drop container capabilities                | &#10004;       | 
| command           | Command executed by the container at startup      | &#10004;       |
| container_name    | Custom container name                             | &#10004;       |
| cpuset            | CPUs in which to allow execution                  |                |
| cpu_shares        | CPU shares (relative weight)                      |                |
| cpu_quota         | Limit the CPU CFS (Completely Fair Scheduler) quota |               | 
| devices           | Map devices                                       |                |
| depends_on        | Express dependency between services               |                |
| dns               | Custom DNS servers                                |                |   
| dns_search        | Custom DNS search                                 |                |
| domainname        | Set the FQDN                                      |                |
| entrypoint        | Override the default entrypoint                   | &#10004;       |
| env_file          | Add environment variables from a file             |                |
| environment       | Add environment variables                         | &#10004;       |
| expose*           | Expose ports without exposing them to the host    | &#10004;       |
| extends           | Extend another service, in the current file or another, optionally overriding configuration |    |
| external_links    | Link to containers started outside this project   |                |
| extra_hosts       | Add hostname mappings                             | &#10004;       |
| hostname          | Set the container hostname                        |                |
| image             | The base image to start from                      | &#10004;       |
| ipc               | Configure IPC settings                            |                |
| labels            | Add meta data to the container                    | &#10004;       |
| links             | Link services                                     | &#10004;       |
| logging           | Logging configuration                             |                |
| log_driver        | Specify a log driver (V1 only)                    |                |
| log_opt           | Specify logging options as key:value pairs (V1 only) |             |
| mac_address       | Set the mac address                               |                |
| mem_limit         | Memory limit                                      |                |
| memswap_limit     | Total memory limit (memory + swap)                |                |
| net               | Network mode (V1 only)                            |                |
| network_mode      | Network mode                                      |                |
| networks          | Networks to join                                  |                |
| pid               | Sets the PID mode to the host PID mode, enabling between container and host OS. |
| port              | Expose ports                                      | &#10004;       |
| privileged        | Run in privileged mode                            | &#10004;       |
| read_only         | Mount the container's file system as read only    | &#10004;       |
| restart           | Restart policy to apply when a container exits    | &#10004;       |
| security_opt      | Override default labeling scheme                  |                |
| shm_size          | Size of /dev/shm                                  |                |
| stdin_open        | Keep stdin open                                   | &#10004;       |
| tty               | Allocate a psuedo-tty                             |                |
| stop_signal       | Sets an alternative signal to stop the container  |                |
| tmpfs             | Mount a temporary volume to the container         | &#10004;       |
| ulimits           | Override the default ulimit                       |                |
| user              | Username or UID used to execute internal container processes | &#10004;       |
| volumes           | Mounts paths or named volumes                     | &#10004;       |
| volume_driver     | Specify a volume driver                           |                |
| volumes_from      | Mount one or more volumes from one container into another |        |
| working_dir       | Path to set as the working directory              | &#10004;       |


### Handling unsupported directives

A validation module will be created to evaluate `container.yml` prior to command execution If unsupported directives are found, the module will
 notify the user and stop execution.
 
### Directive implementation notes

Today a deployment is created for each service defined in `container.yml`, and the deployment contains a single pod, and the pod contains a single container. Properties 
of the service defined in `container.yml` are mapped to the container definition. Note, that this *may* change as we explore and learn more about [kompose](https://github.com/kubernetes-incubator/kompose).

Below are some notes regarding how specific attributes are mappped to the deployment, pod and container.

#### expose

In development this exposes ports internally. 

In the cloud, an exposed port translates to a service, and a service will be created for each exposed port. The cloud service will have the same name as the `container.yml` 
service, and it will listen on the port and forward requests to the exact same port on the pod.

#### links

In development links allow containers to communicate directly without having to define a network.

In the cloud, *links* are not supported, so by themselves they are ignored. However, containers can communicate using services, so to enable communication between two 
containers, add the *expose* directive. See *expose* above.

#### extra_hosts

When run in development, adds a hosts entry to the container.

In the cloud, this will create an External IP service. See [Kubernetes external IPs](http://kubernetes.io/docs/user-guide/services/#external-ips for details) for details. 

#### volumes

In development, the volumes directive mounts host paths or named volumes to the container. In V2 of compose a named volume must be defined in the top-level volumes directive. In V1, if 
a named volume does not exist, it is automatically created.

In the cloud, host paths result in the creation of an *[emptyDir](http://kubernetes.io/docs/user-guide/volumes/#emptydir)*, and a named volume will result in the creation of a 
persistent volume claim (PVC). The resulting emptyDir or PVC will then be mounted to the container using the specified path.

Ansible Container will follow the [Portable Configuration pattern](http://kubernetes.io/docs/user-guide/persistent-volumes/#writing-portable-configuration), which means:

- It will not create persistent volumes 
- It will support an *options* directive (which will be defined during development) to provide a storage class name. 

<h2 id="references">References</h2>

- [Kubernetes object definitions](http://kubernetes.io/docs/api-reference/v1/definitions/)
- [Kompose user guide](https://github.com/kubernetes-incubator/kompose/blob/master/docs/user-guide.md)