#!/bin/bash
set -eux
# need https://github.com/lxc/lxc/commit/74cdd7236633846fdee8a9efe6c483c9b6c36e9f
# apk update
# apk add py-pip git gcc python-dev musl-dev libffi-dev openssl-dev bash
yum update -y
yum install -y epel-release
yum install -y "@Development Tools" ansible git python-setuptools python-devel python-pip
yum clean all
pip install -q --no-cache-dir ansible==2.1.1.0 ruamel.yaml
mkdir -p /etc/ansible/roles
test '(! -f /ansible/requirements.txt)' || pip install --no-cache-dir -r /ansible/requirements.txt
rm -rf /ansible/
echo 'Build script success'
