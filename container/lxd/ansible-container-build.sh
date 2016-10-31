#!/bin/bash
set -eux
apk update
apk add py-pip git gcc python-dev musl-dev libffi-dev openssl-dev
pip install -q --no-cache-dir ansible==2.1.1.0 ruamel.yaml
mkdir -p /etc/ansible/roles
test '(! -f /ansible/requirements.txt)' || pip install --no-cache-dir -r /ansible/requirements.txt
rm -rf /ansible/
echo 'Build script success'
