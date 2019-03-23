# Refactor Deployment Artifacts

## Summary

Produce a portable, better organized deployment artifact that uses an Ansible role, and the new Ansible 2.5 K8s modules.

## Details

Deployment currently generates the following artifacts:

- Single, monolithic playbook containing all tasks, and all K8s object configurations inline
- Copy of the `ansible.kubernetes-modules` role

This proposal is to replace the current artifacts with the following:

- Playbook that executes a role
- Role containing K8s object configuration files separate from playbook tasks

The generated role will include the following:

- Task files that group tasks by function (e.g., start, stop, destroy, etc.)
- A separate configuration file for each K8s object
- README.md file for the role, providing how-to information, and contents descriptions

Additional details include:

- The playbook name and role name will match the project name
- Tasks will be tagged, so that the playbook can be used to perform an action based on tag, as it does today
- New modules available in Ansible 2.5 will be used, rather than the `ansible.kubernetes-modules` role.

Artifacts will be written to the following directory structure:

```
ansible-deployment/
  project-name.yml
  project-name/
    README.md
    config/
      deployments/
      routes/
      services/
      pvcs/
      secrets/
      ...
    tasks/
      main.yml
      start.yml
      stop.yml
      destroy.yml
```