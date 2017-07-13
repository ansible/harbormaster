# Adding Secrets and Ansible Vault Support

## Objectives

- Support secrets in the Docker, K8s, and OpenShift engines
- Use Ansible Vault as the source for secret data
- Avoid doing the following:
    - storing secrets in unencrypted files
    - exposing secrets within container.yml
    - exposing secrets in generated playbooks
- Only decrypt vault files within the Conductor container
- Perform decryption by handing off to `ansible-playbook`, so that decryption occurs only within the context of a playbook run.

## Using a vault file

A vault file will only be decrypted within the Conductor container, and the decryption will be handled by Ansible. Specifically, decryption will occur by passing vault files and credentials to `ansible-playbook`.

The decrypted contents of a vault will only be available at playbook runtime. They will not be available within ``container.yml``.

Consider the following vault file:

```yaml
---
db_username: mysql
db_password: openSesame!
private_key: |
  -----BEGIN PRIVATE KEY-----
  MIIEvAIBADANBgkqhkiG9w0BAQEFAASCBKYwggSiAgEAAoIBAQD5koXgI24E360f
  nhxCfOPVORzFW1CN7u/zOQdvKoIStogF0UQifDCnY/POEjoBmzBrg/UyAmsqLIli
  xMtRIuvEhwaGEUQPoZNCaRW+1XtJ3kDvr9MVTlJTcNGOlGe/E+HyAKBq5vinxzzM
  9ba8M9Nc1PQ93B1OTUY1QGHVYRvSFYDJ5Fnz23xKeNsnY3hmRkV7CDZXSdy9nbmy
  1X9uz7z5bG7PKUVD3JZjI75CHAEDJKtscBv9ez/z16YTxwahIL3CXfqBq8peyAZ0
  n4Mzj4Lt8Cwaw2Kw3w3gMhbhf4fy284+hYqHe9uqYJC6dJJSKDIXqoLSD+e8aN+v
  BAEQcAWXAgMBAAECggEAbmHJ6HqDHJC5h3Rs11NZiWL7QKbEmCIH6rFcgmRwp0oo
  GzqVQhNfiYmBubECCtfSsJrqhbXgJAUStqaHrlkdogx+bCmSyr8R3JuRzJerMd6l
  Jd3EJ...
  -----END PRIVATE KEY-----
```

Because a vault cannot be decrypted directly by Ansible Container, Referencing variable names via template strings within `container.yml` will not be supported. For example, the following `container.yml` would result in an error:

```yaml
version: '2'
services:
  db:
    environment:
      MYSQL_USERNAME: '{{ db_username }}'
      MYSQL_PASSWORD: '{{ db_password }}'
    command: ['/start-db.sh']
```

The only reference that will be supported is in the top-level `secrets` directive, where the secrets are represented as `key:value` pairs, and the value is variable defined in a vault. The following example will work:

```yaml
version: '2'
services:
  db:
    command: ['/start-db.sh']
    secrets:
      mysql:
        docker:
        - mysql_uername
        - mysq_password

secrets:
  # Each secret key is associated to a vault variable
  mysql:
    username: db_username   # variable defined in vault
    password: db_password
```


### Specifying vault files and passwords

The following CLI options will be added to support vault files:

--vault-file
> Accepts a file path to a vault.

--vault-password-file
> Accepts a file path to a vault password file.

--ask-vault-pass
> Will prompt the user for a password.

If no password is specified using the command line options, the process will check for ANSIBLE_VAULT_PASSWORD_FILE in the environment, and if found, attempt to use the file it points to.

The actual vault will be mounted to the conductor. If there is a password file, it too will be mounted to the conductor. If the user is prompted for a password, the entered value will be passed to the conductor as part of the base64 encoded command parameters.

### Specifying vault files via container.yml

In addition to command line support it will also be possible to specify one ore more vault files, and a password file, within the `settings` section of `container.yml`. For example:

```yaml
version: '2'

settings:
  vault_files:
  - /path/to/vault_a.yml
  - /path/to/vault_b.yml
  vault_password_file: /path/to/my/password.txt

services:
...
```

**Note**
> Precedence will be given to the CLI options.

## How secrets actually work

Before considering how we inject secrets into `container.yml`, it's valuable to understand how Docker handles secrets vs. how K8s handles them. And to that end, the following will attempt to provide a brief explanation of how secrets work on each platform.

### Docker and secrets

Here's how to create and use a secret in Docker:

```bash
# Create a secret
$ echo "opensesame" | docker secret create redis_password -

# Grant a service access to the secret
$ docker service  create --name="redis" --secret="redis_password" redis:alpine
```

The above will create a container, and mount the secret as a volume to `/run/secrets/redis_password`. A process within the container can read the secret value from the file.

From Docker compose, existing secrets (those already created using the `docker secret` command) can be accessed as `external` secrets. Or, a new secret can be created by first storing the secret in an unencrypted file, and providing the path to the file. Here's an example:

```yaml
version: '3'
services:
  redis:
    ...
    secrets:
    - redis_password

secrets
  redis_password:
    external: true     # Set 'external: true', if the secret was previously created using `docker secret`
```

Or, alternatively:

```yaml
version: '3'
services:
  redis:
    ...
    secrets:
    - redis_password

secrets
  redis_password:
    file: ./redis-password.txt   # The secret does not yet exist. It will be created by reading the password from a non-encrypted file
```

The `secrets` directive at the service level also has a long form. The following demonstrates:

```yaml
version: '3'
services:
  redis:
    ...
    secrets:
    - source: redist_password
      target: redis_secret
      uid: '103'
      gid: '103'
      mode: 0440
```

**NOTE**
> Ansible Container will not support the external file approach. Asking users to store secrets in an unencrypted files is a bad idea. It also contradicts the goal of having Ansible vault be the source of secrets.

> External secrets, or those created using the `docker secret` directive, fit the desired pattern, as they can easily be seeded from a vault. However, there is not currently an Ansible module for interacting with Docker's secret API. The `command` or `shell` module can be used initially, but longer term a module will be needed.


### Kubernetes and secrets

For context, the following summarizes how secrets are handled by K8s.

Secrets take on the form of *key:value* pairs. The following configuration file creates a secret:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: mysecret
type: Opaque
data:
  username: YWRtaW4=
  password: MWYyZDFlMmU2N2Rm
```

The values for `username` and `password` in the above are base64 encoded. It's expected that the user will provide the values already encoded.

Use the secret in a pod by creating a volume, and then creating a volumeMount that mounts the volume to a container. The following configuration file demonstrates:

```yaml
apiVersion: 'v1'
  kind: Pod
  metadata:
    name: mypod
    namespace: myns
  spec:
    containers:
      - name: mypod
        image: redis
        volumeMounts:
          - name: foo
            mountPath: /etc/foo
            readOnly: true
    volumes:
      - name: foo
        secret:
          secretName: mysecret
```

In this scenario, the user can specify the path where the secret is mounted. Also, notice that *myscret* is a dictionary containing multiple keys. The path to the *username* value, for example, would be `/etc/foo/username`. This is a bit different, and more complex, than Docker's approach.

It's also possible for the user to modify the path where secrets are mounted. Consider the following:

```yaml
apiVersion: 'v1'
  kind: Pod
  metadata:
    name: mypod
    namespace: myns
  spec:
    containers:
      - name: mypod
        image: redis
        volumeMounts:
          - name: foo
            mountPath: /etc/foo
            readOnly: true
    volumes:
      - name: foo
        secret:
          secretName: mysecret
          items:
            - key: username
              path: my-group/my-username
```

By adding `items` to the `volumes` definition above, the path to access the *username* is `/etc/foo/my-group/my-username`, and the password is no longer available, because it was not enumerated in `items`.

Alternatively, secrets can be made available to a pod as an environment variables. Here's an example:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: secret-env-pod
spec:
  containers:
    - name: mycontainer
      image: redis
      env:
        - name: SECRET_USERNAME
          valueFrom:
            secretKeyRef:
              name: mysecret
              key: username
        - name: SECRET_PASSWORD
          valueFrom:
            secretKeyRef:
              name: mysecret
              key: password
  restartPolicy: Never
 ```

## Secrets in container.yml

The following describes an approach to representing secrets in `container.yml`. It attempts to cover all of the options and variations required by each engine.

### Service level secrets

At the service level, we need the ability to specify engine specific attributes that control how a secret manifests in a container. For example, in the case of Docker there is a short form and long form for specifying a secret. In the case of K8s, a secret can be mounted as a volume, or it can be surfaced as an environment variable, and each option brings a set of attributes that users will want to set.

The following shows an approach that provides maximum flexibility at the service level:

Here's the vault file:

```yaml
# vault.yml
---
web_password: mysql
```

And, here's the `container.yml`:

```yaml
version: '2'
settings:
  vault_files:
    - vault.yml
  vault_password_file: /etc/vault/password.txt

services:
  web:
    command: []
    ports: []

    secrets:

      web_secret:  # the source of the secret, defined in top-level secrets

        docker:
          - web_secret_password  # Short form

          - source: web_secret_password   # Or, alternatively, the long form
            target: web_secret
            uid: '103'
            gid: '103'
            mode: 0440

        k8s:
          - mount_path: /etc/foo  # mount as a volume
            name: foo-secrets # Names the volume to match it to the volumeMount
            read_only: true

          # Or, alternatively...

          - mount_path: /etc/foo  # mount as volume, using `items` to pick specific keys and name the volume after the secret 'web_secret'
            read_only: true
            items:
              - key: password
                path: my-group/password

          # Use as environment variable
          - env_variable: WEB_PASSWORD
            key: password

        openshift:
          - mount_path: /etc/foo  # mount as a volume
            name: foo-secrets # Names the volume to match it to the volumeMount
            read_only: true

          # Or, alternatively...

          - mount_path: /etc/foo  # mount as volume, using `items` to pick specific keys and name the volume after the secret 'web_secret'
            read_only: true
            items:
              - key: password
                path: my-group/password

          # Use as environment variable
          - env_variable: WEB_PASSWORD
            key: password

secrets:
  web_secret:
    password: web_password   # variable defined in vault
```

### Top-level secrets

Consider the following example of top-level secrets:

Here's the vault file:

```yaml
# vault.yml
---
web_password: mysql
db_username: foo
db_password: foop0wer!
```

Here's the `container.yml`:

```yaml
...
secrets:
  web_secret:
    password: web_password   # variable defined in vault
  mysql:
    username: db_username
    password: db_password
```

The top-level directive, as demonstrated above, serves only to map key names to variables defined in a vault. Ansible Container will assume that the value is defined in a vault, as it will not actually be able to decrypt and check the vault.

## Managing secrets

### Docker

The Docker engine will combine the secret name with the key name, separated by '_' to create the name of the Docker secret object. For example, in the above, `web_secret` has a `password` key, so the actual Docker secret to be created is `web_secret_password`. Or, in the case of `mysql`, there will be two secrets created: `mysql_username` and `mysql_password`.

All secrets will be treated as `external: true` when the `run` or `deploy` playbook is generated. That means that the first task(s) in the playbook will ensure that the secret(s) exist.

To create and manage Docker secrets we'll need to create an Ansible module for managing secrets. In the interim we likely can use the command module to execute `docker secret` commands.

### K8s and OpenShift

Using the service level `secrets` directive, and the top-level directive, generating object configurations will be straightforward. Plus, there is already an existing module, `kubernetes_v1_secret`, for managing secrets.

See the next section for more details, and an example.

**NOTE**:
>The only variable that my come into play, and that's not covered, is the secret `type`. Currently the only relevant type value is `Opaque`. In the future, other types may be introduced, in which case it would become necessary to expand the top-level directive's attributes.

### Playbook generation

Any vault files will be added to the `var_files` directive on the play. At the task level, no secrets values will be written, but instead, the variable names referenced in the top-level directive will be written as template strings.

For example, given the `container.yml` and vault above, the playbook generated by the Docker engine would look like the following:

```yml
...
var_files:
  - vault.yml

tasks:
  - name: Create mysql_username secret
    shell: echo {{ db_username }} | docker secret create mysql_username
```

The K8s and OpenShift engines will follow the same pattern. Tasks for creating secrets will be added prior to tasks that create deployments. And for tasks that manage secrets, no secret values will be written, but instead the template variable string will be written, including the `base64` filter. The following demonstrates:

```yml
...
var_files:
  - vault.yml

tasks:
  - name: Create mysql_username secret
    k8s_v1_secret:
      resource_definition:
        apiVersion: v1
        kind: Secret
        metadata:
          name: mysql
          namespace: my-project
        type: Opaque
        data:
          username: '{{ db_username | base64 }}'
          password: '{{ db_password | base64 }}'
```
