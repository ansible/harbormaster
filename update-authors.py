#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import, print_function

import logging

logger = logging.getLogger(__name__)

import subprocess
from collections import defaultdict

user_scores = defaultdict(int)

git_log = subprocess.check_output("git log --shortstat --no-merges --pretty='%aN <%aE>'",
                                  shell=True)
log_entries = git_log.strip().split('\n')
while log_entries:
    author = log_entries.pop(0)
    _ = log_entries.pop(0)
    commit_line = log_entries.pop(0)
    commit_parts = [s.strip() for s in commit_line.split(', ')]
    commit_data = {'files': 0, 'insertions': 0, 'deletions': 0}
    for clause in commit_parts:
        count, action = clause.split(' ', 1)
        if action.endswith('(+)'):
            user_scores[author] += int(count)
        elif action.endswith('(-)'):
            user_scores[author] += int(count)
        else:
            user_scores[author] += int(count)

sorted_user_scores = sorted(user_scores.items(), key=lambda tpl: tpl[1], reverse=True)

print("Ansible Container has been contribued to by the following authors:\n"
      "This list is automatically generated - please file an issue for corrections)\n")
for author, _ in sorted_user_scores:
    print(author)
