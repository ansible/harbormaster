# Adding Stateful Sets Support

## Objectives

 - Support Stateful Sets for Kubernetes and OpenShift deployments
 - Ensure only a Stateful Set or Deployment is generated

## What is a Stateful Set?

From the Kubernetes documentation, "A StatefulSet is a Controller that provides a unique identity to its Pods. It provides guarantees about the ordering of deployment and scaling."
See the [Kubernetes Stateful Set Documentation](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/) for more information.

Stateful sets share commonality with deployments but offer a few differences. For service declarations, either a deployment or stateful set should be delcared but not both. The choice influences what object is created in Kubernetes/OpenShift and how the attached volumes are generated. Deployments use volume delcarations while Stateful Sets use `volumeClaimTemplates`.

## Delcaring Stateful Sets

A section will be added that allows for declaring properties of a Stateful set. If both the statefulset and deployment sections are found declared for a service an error will be thrown. A Stateful Set declaration might look like the following:

```
services:
  web:
    command: []
    entrypoint: []
    volumes:
      - puppet-data:/etc/puppet
    openshift:
      state: present
      statefulset:
        force: false
        replicas: 2
        termination_grace_period_seconds: 10
        volumeClaimTemplates:
          - name: www
            storage_class: anything
            access_modes: ["ReadWriteOnce"]
            storage: 1Gi
```

This will result in the following generated template:

```
apiVersion: apps/v1beta1
kind: StatefulSet
metadata:
  name: web
spec:
  serviceName: "web"
  replicas: 2
  template:
    metadata:
      labels:
        app: web
    spec:
      terminationGracePeriodSeconds: 10
      containers:
      - name: web
        image: web
        ports:
        - containerPort: 80
          name: web
        volumeMounts:
        - name: www
          mountPath: /usr/share/web
  volumeClaimTemplates:
  - metadata:
      name: www
      annotations:
        volume.beta.kubernetes.io/storage-class: anything
    spec:
      accessModes: [ "ReadWriteOnce" ]
      resources:
        requests:
          storage: 1Gi
```

