Multi-Container Pods
====================

**New in 0.9.2**

When deploying to K8s or OpenShift, it's sometimes desirable to group multiple containers into a single pod. One benefit is that all containers within a pod share the same network namespace and port space, allowing communication via *localhost*.

A common scenario is a ``sidecar``, where a secondary container is added to a pod in order to provide a proxy to an external service or storage device. With the proxy located in the same pod, the primary pod can access the external service using *localhost* and a port number.

Using the new ``containers`` directive within a service definition, you can provide an array of containers that comprise a service. The ``containers`` directive is optional, and most cases won't require it. However, when you encounter a scenario that calls for multiple containers co-existing in the same pod, employ the ``containers`` directive.

Consider the following example that defines a Django server container and a database proxy container within a single service:

.. code-block:: yaml

    version: '2'
    settings:
      conductor:
        base: 'centos:7'
      project_name: 'demo'
    services:
      django:
        containers:
        - container_name: server
          from: centos:7
          roles:
          - role: django
            user: django
            group: django
            os_packages:
            - 'https://centos7.iuscommunity.org/ius-release.rpm'
            allowed_hosts:
            - '*'
          expose:
          - '{{ django_port }}'
          user: django
          working_dir: /funnels/chat
          command: ['/usr/bin/dumb-init', '/venv/bin/gunicorn', '-w', '2', 'chat.wsgi:application', '--bind', '0.0.0.0:8000',
            '--access-logfile', '-', '--error-logfile', '-', '--log-level', 'debug']
          entrypoint: [/usr/bin/entrypoint.sh]
          environment:
            DJANGO_LOG_LEVEL: INFO
            POSTGRES_DB: '{{ postgres_db }}'
            POSTGRES_HOST: '{{ postgres_host }}'
            POSTGRES_PORT: '{{ postgres_port }}'
          dev_overrides:
            links:
            - postgres
            volumes:
            - ${PWD}:/funnels:rw
            command: ['/usr/bin/dumb-init', '/venv/bin/python', 'manage.py', 'runserver', '0.0.0.0:{{ django_port }}']
            depends_on:
            - postgres
            environment:
              DEBUG: 'True'
              DJANGO_LOG_LEVEL: DEBUG
              POSTGRES_DB: '{{ postgres_db }}'
              POSTGRES_HOST: '{{ postgres_host }}'
              POSTGRES_PORT: '{{ postgres_port }}'
          secrets:
            postgres:
              docker:
                - postgres_user
                - postgres_password
              k8s:
                - mount_path: '/run/secrets/postgres'
                  read_only: true

        - container_name: db-proxy
          from: 'gcr.io/cloudsql-docker/gce-proxy:1.09'
          command:
          - '/cloud_sql_proxy'
          - '--dir=/cloudsql'
          - '-instances={{ postgres_connection_name }}=tcp:{{ postgres_port }}'
          - '-credential_file=/run/secrets/cloudsql/instance_credentials'
          dev_overrides:
            command: ['/bin/true']
          secrets:
            cloudsql:
              k8s:
                - mount_path: '/run/secrets/cloudsql'
                  read_only: false

The above defines a ``django`` service consisting of two containers: ``server``, and ``db-proxy``. When deployed using the ``k8s`` and ``openshift`` engines, the two containers will be placed in a single pod that backs the ``django`` service.

Notice that each container definition contains the ``container_name`` directive. This is because each container is required to have a name. Other than that, all of the directives used to define a container are exactly the same as what you normally use to define a service, including the ``from`` directive used to set the base image.

When running the containers in a local development environment, via the ``run`` command and the ``docker`` engine, the following containers are created:

.. code-block:: bash

    CONTAINER ID        IMAGE                                 COMMAND                  PORTS                    NAMES
    b700f8ab1f46        demo-django-server:20170825095031     "/usr/bin/entrypoi..."   8000/tcp                 demo_django-server_1
    4b9db10571c7        gcr.io/cloudsql-docker/gce-proxy:1.09 "/bin/true"                                       demo_django-db-proxy_1
    ...

Note the image name for the first container. Running a ``build`` on the above example results in image names that follow the pattern: project_name + '-' + service name + '-' + container name. Notice also that the container names follow the pattern: project name + '_' + service name + '-' + container name.

Running the ``deploy`` command with the ``k8s`` engine results in the following deployment configuration:

.. code-block:: yaml


    apiVersion: extensions/v1beta1
    kind: deployment
    metadata:
        name: django
        labels:
            app: demo
            service: django
        namespace: demo
    spec:
        template:
            metadata:
                labels:
                    app: demo
                    service: django
            spec:
                containers:
                  - name: django-server
                    securityContext: {}
                    state: present
                    volumeMounts:
                      - readOnly: true
                        mountPath: /run/secrets/postgres
                        name: postgres
                    env:
                      - name: DJANGO_LOG_LEVEL
                        value: INFO
                      - name: POSTGRES_HOST
                        value: localhost
                      - name: POSTGRES_PORT
                        value: '5432'
                      - name: POSTGRES_DB
                        value: chat
                    workingDir: /demo/chat
                    args:
                      - /usr/bin/dumb-init
                      - /venv/bin/gunicorn
                      - -w
                      - '2'
                      - chat.wsgi:application
                      - --bind
                      - 0.0.0.0:8000
                      - --access-logfile
                      - '-'
                      - --error-logfile
                      - '-'
                      - --log-level
                      - debug
                    command:
                      - /usr/bin/entrypoint.sh
                    image: us.gcr.io/demo-175910/demo-django-server:20170820192044
                  - name: django-db-proxy
                    securityContext: {}
                    state: present
                    volumeMounts:
                      - readOnly: false
                        mountPath: /run/secrets/cloudsql
                        name: cloudsql
                    args:
                      - /cloud_sql_proxy
                      - --dir=/cloudsql
                      - -instances=demo-175910:us-central1:chat-staging=tcp:5432
                      - -credential_file=/run/secrets/cloudsql/instance_credentials
                    image: gcr.io/cloudsql-docker/gce-proxy:1.09
                volumes:
                  - secret:
                        secretName: postgres
                    name: postgres
                  - secret:
                        secretName: cloudsql
                    name: cloudsql

Here the containers are grouped together under a single deployment, with the deployment name set to match the service name, and the container names follow the pattern: service name + '-' + container name.
