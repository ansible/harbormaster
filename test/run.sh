#!/bin/bash
#
# run.sh 
#
# Run unit and integration tests via container. Provides a one mechanism for running tests locally and 
# on Travis.
#
#
source_root=$(python -c "from os import path; print(path.abspath(path.join(path.dirname('$0'), '..')))")
export ANSIBLE_CONTAINER_PATH=${source_root}

image_exists=$(docker images local-test:latest | wc -l)
if [ "${image_exists}" -le "1" ]; then
   ansible-container --project "${source_root}/test/local" build --with-variables ANSIBLE_CONTAINER_PATH="${source_root}"
fi

ansible-container --project "${source_root}/test/local" run
