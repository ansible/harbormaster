# Supporting Multiple Containers Per Service in Kubernetes and OpenShift

## Table of Contents
- [Reasoning](#Reasoning)
- [Declaring Multiple Containers Per Service](#declaring-multiple-containers-per-service)
- [Declarations and Generated Templates](#declarations-and-generated-templates)

## Reasoning

Some services are composed of multiple containers that are coupled and share resources to form a single cohesive service. Common cases of this are sidecar and ambassador containers. Within Ansible Container currently it is a single container per service, which allows for the generation of the images used within these services. However these images are built separately and deployed to a server. However, the container.yml file is not able to act as a single source-controlled piece of code to define the state of the deployable application.

## Declaring Multiple Containers Per Service

To achieve this the service section will accept a new property, containers, which will allow for the declaration of 1-N containers per service. The addition of this property will allow for the maintenance of existing applications by using an check when building and deploying the service; e.g. `if 'containers' in service`.

### Multiple Containers Declaration Example

```yaml
services:
  web:
    containers:
      - from: centos:7
        entrypoint: [/usr/bin/entrypoint.sh]
        working_dir: /
        user: apache
        command: [/usr/bin/dumb-init, httpd, -DFOREGROUND]
        ports:
          - 8000:8080
          - 4443:8443
        roles:
          - apache-container
        volumes:
          - static-content:/var/www/static
        container_name: apache
      - from: centos:7
        command: [/usr/bin/dumb-init, file-refresher, --out-dir, /var/www/static]
        entrypoint: [/usr/bin/entrypoint.sh]
        user: refresher
        roles:
          - apache-file-refresher
        volumes:
          - static-content:/var/www/static
        container_name: apache-file-refresher
volumes:
  static-content:
    docker: {}
    k8s:
      force: false
      state: present
      access_modes:
      - ReadWriteOnce
      requested_storage: 1Gi
      metadata:
        annotations: 'volume.beta.kubernetes.io/mount-options: "discard"'
```

## Declarations and Generated Templates

In order to maintain backwards compatibility, declaring a service with a single container will remain the same, a single object representing the service.

### Docker

#### Case Management

Given that Docker may only have one container per service, in the case that the `containers` directive is encountered the following cases could occur:

- Containers is a list of container declarations
  - In the case that there is a list of container declarations and the engine for deployment is Docker, Ansible Container would create each container as a seperate service using the following naming convention for the service: `{service-name}-{container-name}`

    **Example Template**
    ```yaml
    services:
      web-apache:
        entrypoint:
        - /usr/bin/entrypoint.sh
        working_dir: /
        user: apache
        command: 
        - /usr/bin/dumb-init
        - httpd
        - -DFOREGROUND
        image: apache:latest
        exposes:
        - 8000
        - 4443
        volumes:
        - static-content:/var/www/static
      web-apache-file-refresher:
        command: 
        - /usr/bin/dumb-init
        - file-refresher
        - --out-dir
        - /var/www/static
        entrypoint: 
        - /usr/bin/entrypoint.sh
        user: refresher
        image: apache-file-refresher:latest
        volumes:
        - static-content:/var/www/static
    ```
- Containers is a container declaration object
  - In the case that there is a single container object under the `containers` declaration. The service deployment would execute as it does currently.
- Containers is not declared, in place is the standard container declaration
  - If containers is not declared, but a container declaration is under the service, the execution would continue as normally

### Kubernetes

#### Case Management

- Containers is a list of container declarations
  - In the case that there is a list of container declarations, then the service would be generated with a list of containers in it's spec
- Containers is a container declaration object
  - In the case that there is a single container object under the `containers` declaration. The service deployment would execute as it does currently.
- Containers is not declared, in place is the standard container declaration
  - If containers is not declared, but a container declaration is under the service, the execution would continue as normally

Using the services declaration presented in [Multiple Containers Declaration Example](#multiple-containers-declaration-example) the following would be generated for deploying the service to Kubernetes.

#### Generated Template

```yaml
k8s_v1beta1_deployment:
  state: present
  force: false
  resource_definition:
    apiVersion: extensions/v1beta1
    kind: deployment
    metadata:
      name: apache
      labels:
        app: web
        service: apache
      namespace: web
  spec:
    template:
      metadata:
        labels:
          app: web
          service: apache
      spec:
        containers:
          - name: apache
            securityContext: {}
            state: present
            volumeMounts:
              - readOnly: false
                mountPath: /var/www/static
                name: static-content
            image: apache:latest
          - name: apache-file-refresher
            securityContext: {}
            state: present
            volumeMounts:
              - readOnly: false
                mountPath: /var/www/static
                name: static-content
            image: apache-file-refresher:latest
        volumes:
          - name: static-content
            persistentVolumeClaim:
              claimName: static-content
        replicas: 1
        strategy:
          type: RollingUpdate
```