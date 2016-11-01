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

export AC_PYTHON_VERSION=$(python -c "import platform; print('.'.join(platform.python_version_tuple()[0:2]))")
image_exists=$(docker images local-test-"${AC_PYTHON_VERSION}":latest | wc -l)
if [ "${image_exists}" -le 1 ]; then
   ansible-container --project "${source_root}/test/local" --debug build --local-builder --with-variables ANSIBLE_CONTAINER_PATH="${source_root}"
fi

ansible-container --project "${source_root}/test/local" --debug run
status=$(docker inspect --format="{{ .State.ExitCode }}" ansible_test-"${AC_PYTHON_VERSION}"_1)
exit "${status}"
