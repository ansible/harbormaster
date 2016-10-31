#!/bin/bash
set -eux
apk update
apk add py-pip git gcc python-dev musl-dev libffi-dev openssl-dev
pip install --no-cache-dir -e git+https://github.com/ansible/ansible.git@devel#egg=ansible
test '(! -f /ansible/requirements.txt)' || pip install --no-cache-dir -r /ansible/requirements.txt
rm -rf /ansible/
echo 'Build script success'
