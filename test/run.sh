#!/bin/bash
#
# run.sh 
#
# Run unit and integration tests via container. Provides a one mechanism for running tests locally and 
# on Travis.
#
#

set -o nounset -o errexit

source_root=$(python -c "from os import path; print(path.abspath(path.join(path.dirname('$0'), '..')))")
export ANSIBLE_CONTAINER_PATH=${source_root}

docker_version=$(docker version --format '{{json .}}' | python -c "import sys, json; print(json.load(sys.stdin)['Server']['ApiVersion'])")
: "${DOCKER_API_VERSION:=$docker_version}"

testing_image_exists=$(docker images ansible/ansible-container-testing | wc -l)
if [ "${testing_image_exists}" -le 1 ]; then
    docker pull ansible/ansible-container-testing:latest
fi

image_exists=$(docker images local-test:latest | wc -l)
if [ "${image_exists}" -le 1 ]; then
   ansible-container --project-path "${source_root}/test/local" --debug build \
     --with-variables ANSIBLE_CONTAINER_PATH="${source_root}"
fi

ansible-container --project-path "${source_root}/test/local" --debug run
status=$(docker inspect --format="{{ .State.ExitCode }}" ansible_test_1)
exit "${status}"
