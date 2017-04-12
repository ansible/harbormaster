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

docker_version=$(docker version --format '{{json .}}' | python -c "import sys, json; print json.load(sys.stdin)['Server']['ApiVersion']")
: "${DOCKER_API_VERSION:=$docker_version}"

image_exists=$(docker images local-test:latest | wc -l)
if [ "${image_exists}" -le 1 ]; then
   ansible-container --project "${source_root}/test/local" --debug build --local-builder --flatten \
     --with-variables ANSIBLE_CONTAINER_PATH="${source_root}"
fi

ansible-container --project "${source_root}/test/local" --debug run
status=$(docker inspect --format="{{ .State.ExitCode }}" ansible_test_1)
exit "${status}"
