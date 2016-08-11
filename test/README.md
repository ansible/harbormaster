## Running tests

Unit and integration tests live here. Running tests locally requires having ansible-container installed. Execute tests from within 
the local copy of the ansible-container repo by running *test/run.sh*:

```
$ cd ansible-container
$ ./test/run.sh 
```

If the local-test image does not exist, the script will create it using `ansible-container build` against the *test/local* project. Once the image
is availabe tests are executed within a container via `ansible-container run`. Subsequent runs of the script will use the existing local-test image 
to mount the local copy of ansible-container and execute tests.

This is the same script and test execution that occurs on Travis. So, if tests run successfully in your local environment, they *should* run 
successfully on Travis. 

Thanks for trying out Ansible Container!

