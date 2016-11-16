#!/bin/bash

if [ -s "./requirements.txt" ]; then
    echo "Running pip install of ansible/requirements.txt" 
    pip install --no-cache-dir -q -U -r ./requirements.txt
fi

if [ -f "./requirements.yml" ]; then
    roles=$(python -c "import yaml; roles = yaml.load(open('./requirements.yml', 'r')); print 0 if not roles else len(roles)")
    if [ "${roles}" -gt 0 ]; then
        ansible-galaxy install -r ./requirements.yml
    fi
fi

if [ "${ANSIBLE_ORCHESTRATED_HOSTS}" != "" ]; then
    # shellcheck disable=SC2046
    /usr/local/bin/wait_on_host.py -m 5 $(echo "${ANSIBLE_ORCHESTRATED_HOSTS}" | tr ',' ' ')
fi

"$@"
