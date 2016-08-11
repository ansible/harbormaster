# How to Contribute

This is a very young project, and the codebase is moving quickly -- but there are plenty of ways to help.

## Ask questions and file issues

Please use the Github issue tracker for all issues with, and questions about, the project. 

If you have any questions, please file an issue and we'll answer it as soon as we can. Make your question or issue
clear in the title, and be sure to look through the issues just in case someone else has asked the same questions.

## Pull requests

Pull requests are always welcome. We may not necessarily accept them, but we will happy to discuss them with you. Please
observe the following when submitting a PR:

- Follow the [gitflow](ihttps://github.com/nvie/gitflow) branching model.
- Submit PRs against the *develop* branch.
- New features should include unit and integration tests. 

## Provide examples

Examples of working Ansible Container playbooks will be very useful! Please feel free to provide Pull Requests linking
to examples from your own repos in [EXAMPLES.md](./EXAMPLES.md) or submit them to [ansible-container-examples](https://github.com/ansible/ansible-container-examples).

## Running tests

Unit and integration tests are found in the *test* directory. Running tests locally requires having ansible-container installed. Execute tests from within 
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

