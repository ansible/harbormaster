# -*- coding: utf-8 -*-
from __future__ import absolute_import
import logging

logger = logging.getLogger(__name__)

import json
import os
import re
import subprocess
import shlex
import urlparse
import tarfile
import glob
import shutil
import functools

try:
    import ruamel.yaml
    from ruamel.yaml.comments import CommentedMap, CommentedSeq
except ImportError:
    raise ImportError('This engine requires you "pip install \'ruamel.yaml>=0.13.14\'" to import projects.')

from ..common.exceptions import AnsibleContainerConductorException
from ..common.utils import create_role_from_templates

# Known issues:
# * In a Dockerfile, ENV and ARG params don't apply to directives before their
#   declaration. In our importer, they do.
# * We try to split multi-command RUN into multiple tasks. This only works if
#   the Dockerfile is reasonably well formed.

def debug_parsing(fn):
    @functools.wraps(fn)
    def __wrapped__(self, payload, comments, **kwargs):
        logger.debug(u'Parsing payload "%s"', payload)
        to_return = fn(self, payload, comments, **kwargs)
        logger.debug(u'Parser: "%s" becomes %s',
                     payload, to_return)
        return to_return
    return __wrapped__

def _simple_meta_parser(meta_key):
    def __wrapped__(self, payload, comments):
        if isinstance(payload, list):
            self.meta[meta_key] = CommentedSeq(payload)
        elif isinstance(payload, dict):
            self.meta[meta_key] = CommentedMap(payload.items())
        else:
            self.meta[meta_key] = payload
        if comments:
            self.meta.yaml_set_comment_before_after_key(meta_key,
                                                        before=u'\n'.join(comments))
        logger.debug(u'Parser: meta: %s -> %s', meta_key, self.meta[meta_key])
        return []
    return __wrapped__

class DockerfileParser(object):
    path = None
    docker_file_path = None
    parsed = False

    # These directives support JSON arrays as arguments
    supports_json = {
        'RUN',
        'CMD',
        'ADD',
        'COPY',
        'ENTRYPOINT',
        'VOLUME',
        'SHELL',
    }

    # These directives support environment variable substitution
    supports_env = {
        'ADD',
        'COPY',
        'ENV',
        'EXPOSE',
        'LABEL',
        'USER',
        'WORKDIR',
        'VOLUME',
        'STOPSIGNAL',
        'ONBUILD'
    }

    def __init__(self, path, default_vars=None, bundle_files=False):
        self.path = path
        self.service_name = os.path.basename(self.path)
        file_name = u'Dockerfile'
        self.docker_file_path = os.path.normpath(os.path.join(self.path,
                                                              file_name))
        self.default_vars = default_vars or {}
        self.bundle_files = bundle_files

    def assert_dockerfile_exists(self):
        if not os.path.exists(self.docker_file_path):
            raise AnsibleContainerConductorException(u"Failed to find %s",
                                                     self.docker_file_path)

    def lines_iter(self):
        '''
        Returns contents of the Dockerfile as an array, where each line in the file is an element in the array.
        :return: list
        '''
        # Convert unicode chars to string
        byte_to_string = lambda x: x.strip().decode(u'utf-8') if isinstance(x, bytes) else x.strip()

        # Read the entire contents of the Dockerfile, decoding each line, and return the result as an array
        with open(self.docker_file_path, u'r') as f:
            for line in f:
                yield byte_to_string(line)

    def preparse_iter(self):
        """
        Comments can be anywhere. So break apart the Dockerfile into significant
        lines and any comments that precede them. And if a line is a carryover
        from the previous via an escaped-newline, bring the directive with it.
        """
        to_yield = {}
        last_directive = None
        lines_processed = 0
        for line in self.lines_iter():
            if not line:
                continue
            if line.startswith(u'#'):
                comment = line.lstrip('#').strip()
                # Directives have to precede any instructions
                if lines_processed == 1:
                    if comment.startswith(u'escape='):
                        self.escape_char = comment.split(u'=', 1)[1]
                        continue
                to_yield.setdefault('comments', []).append(comment)
            else:
                # last_directive being set means the previous line ended with a
                # newline escape
                if last_directive:
                    directive, payload = last_directive, line
                else:
                    directive, payload = line.split(u' ', 1)
                if line.endswith(self.escape_char):
                    payload = payload.rstrip(self.escape_char)
                    last_directive = directive
                else:
                    last_directive = None
                to_yield['directive'] = directive
                to_yield['payload'] = payload.strip()
                yield to_yield
                to_yield = {}

    def __iter__(self):
        self.escape_char = u'\\'
        self.variables = CommentedMap()
        for k, v in self.default_vars.iteritems():
            self.variables[k] = v
        self.meta = CommentedMap()
        self.shell = None
        self.user = None
        self.working_dir = None
        self.parsed = False

        lines = self.lines_iter()
        lines_processed = 0
        for preparsed in self.preparse_iter():
            directive = preparsed['directive']
            if directive in self.supports_json:
                try:
                    payload = json.loads(preparsed['payload'])
                except ValueError:
                    payload = preparsed['payload']
            else:
                payload = preparsed['payload']
            payload_processor = getattr(self, 'parse_%s' % (directive,))

            if directive in self.supports_env:
                if isinstance(payload, list):
                    payload = [self.do_variable_syntax_substitution(s)
                               for s in payload]
                else:
                    payload = self.do_variable_syntax_substitution(payload)

            for task in payload_processor(payload,
                                          comments=preparsed.get('comments', [])):
                yield task
        logger.debug('Parsing complete!')
        logger.debug('Meta is:\n%s', self.meta)
        logger.debug('Vars are:\n%s', self.variables)
        self.parsed = True

    @property
    def container_yml(self):
        if not self.parsed:
            raise ValueError(u'Finish parsing the Dockerfile first')
        safe_service_name = self.service_name.replace(u'-', u'_')
        container_yml = CommentedMap()
        container_yml['settings'] = CommentedMap()
        container_yml['settings']['conductor_base'] = self.meta['from']
        container_yml['services'] = CommentedMap()
        container_yml['services'][safe_service_name] = CommentedMap()
        container_yml['services'][safe_service_name]['roles'] = CommentedSeq(
            [safe_service_name])
        return container_yml

    PLAIN_VARIABLE_RE = re.compile(ur'(?<!\\)\$(?P<var>[a-zA-Z_]\w*)')
    BRACED_VARIABLE_RE = re.compile(ur'(?<!\\)\$\{(?P<var>[a-zA-Z_]\w*)\}')
    DEFAULT_VARIABLE_RE = re.compile(ur'(?<!\\)\$\{(?P<var>[a-zA-Z_]\w*)'
                                     ur':(?P<plus_minus>[+-])(?P<default>[^}]+)\}')

    def do_variable_syntax_substitution(self, string):
        def simple_variable_sub(match_obj):
            var_name = match_obj.group('var')
            if var_name in self.meta.get('environment', []):
                return u"{{ lookup('env', '%s') }}" % var_name
            else:
                return u"{{ %s }}" % var_name
        string = self.PLAIN_VARIABLE_RE.sub(simple_variable_sub, string)
        string = self.BRACED_VARIABLE_RE.sub(simple_variable_sub, string)

        def default_variable_sub(match_obj):
            var_name = match_obj.group('var')
            default = match_obj.group('default')
            if var_name in self.meta.get('environment', []):
                var_string = "lookup('env', '%s')" % var_name
            else:
                var_string = var_name
            if match_obj.group('plus_minus') == '-':
                # Use the default as a default
                return u"{{ %s | default('%s') }}" % (var_string, default)
            else:
                # If the variable is defined, use the default else blank
                return u"{{ %s | defined | ternary('%s', '') }}" % (var_string,
                                                                    default)
        string = self.DEFAULT_VARIABLE_RE.sub(default_variable_sub, string)
        return string

    parse_FROM = _simple_meta_parser('from')

    @debug_parsing
    def parse_RUN(self, payload, comments):
        task = CommentedMap()
        if comments:
            task['name'] = u' '.join(comments)
        if isinstance(payload, list):
            task['command'] = subprocess.list2cmdline(payload)
        else:
            task['shell'] = payload.rstrip(u';').rstrip(u'&&').rstrip()
            if self.shell:
                task.setdefault('args', {})['executable'] = self.shell
        if self.user:
            task['remote_user'] = self.user
        if self.working_dir:
            task.setdefault('args', {})['chdir'] = self.working_dir
        return [task]

    parse_CMD = _simple_meta_parser('command')

    def parse_LABEL(self, payload, comments):
        kv_pairs = shlex.split(payload)
        first = True
        for k, v in [kv.split('=', 1) for kv in kv_pairs]:
            self.meta.setdefault('labels', CommentedMap())[k] = v
            if comments and first:
                self.meta['labels'].yaml_set_comment_before_after_key(
                    k, before=u'\n'.join(comments))
        return []

    parse_MAINTAINER = _simple_meta_parser('maintainer')

    def parse_EXPOSE(self, payload, comments):
        # Ensure all variable references are quoted, so we can use shlex
        payload = re.sub(ur'(\{\{[^}]+\}\})', ur'"\1"', payload)
        ports = shlex.split(payload)
        self.meta.setdefault('ports', CommentedSeq()).extend(ports)
        self.meta.yaml_set_comment_before_after_key('ports',
                                                    before=u'\n'.join(comments))
        return []

    def parse_ENV(self, payload, comments):
        # It's possible this is a single environment variable being set using
        # the syntax that doesn't require an = sign
        if u'=' not in payload.split(u' ', 1)[0]:
            k, v = payload.split(u' ', 1)
            self.meta.setdefault('environment', CommentedMap())[k] = v
            self.meta['environment'].yaml_set_comment_before_after_key(k,
                                                                       before=u'\n'.join(comments))
        else:
            # Ensure all variable references are quoted, so we can use shlex
            payload = re.sub(ur'=(\{\{[^}]+\}\})', ur'="\1"', payload)
            kv_parts = shlex.split(payload)
            kv_pairs = [part.split(u'=', 1) for part in kv_parts]
            self.meta.setdefault('environment', CommentedMap()).update(kv_pairs)
            self.meta['environment'].yaml_set_comment_before_after_key(kv_pairs[0][0],
                                                                       before=u'\n'.join(comments))
        return []

    @debug_parsing
    def parse_ADD(self, payload, comments, url_and_tarball=True):
        if isinstance(payload, list):
            dest = payload.pop()
            src_list = payload
        else:
            _src, dest = payload.split(u' ', 1)
            src_list = [_src]
        if dest.endswith('/'):
            dest_path = dest
        else:
            dest_path = os.path.dirname(dest)

        tasks = CommentedSeq()
        # ADD ensures the dest path exists
        tasks.append(
            CommentedMap([
                ('name', u'Ensure %s exists' % dest_path),
                ('file', CommentedMap([
                    ('path', dest_path),
                    ('state', 'directory')]))
        ]))

        for src_spec in src_list:
            # ADD src can be a URL - look for a scheme
            if url_and_tarball and urlparse.urlparse(src_spec).scheme in ['http', 'https']:
                task = CommentedMap()
                if comments:
                    task['name'] = u' '.join(comments)
                task['get_url'] = CommentedMap([
                    ('url', src_spec), ('dest', dest), ('mode', 0600)])
                tasks.append(task)
            else:
                real_path = os.path.join(self.path, src_spec)
                if url_and_tarball:
                    # ADD src can be a tarfile
                    try:
                        _ = tarfile.open(real_path, mode='r:*')
                    except tarfile.ReadError:
                        # Not a tarfile.
                        pass
                    else:
                        task = CommentedMap()
                        if comments:
                            task['name'] = u' '.join(comments)
                        task['unarchive'] = CommentedMap([
                            ('src', src_spec),
                            ('dest', dest)])
                        tasks.append(task)
                        continue
                # path specifiers can be fnmatch expressions, so use glob
                for abs_src in glob.iglob(real_path):
                    src = os.path.relpath(abs_src, self.path)
                    task = CommentedMap()
                    if comments:
                        task['name'] = u' '.join(comments + [u'(%s)' % src])
                    if os.path.isdir(real_path):
                        task['synchronize'] = CommentedMap([
                            ('src', src),
                            ('dest', dest),
                            ('recursive', 'yes')])
                    elif os.path.isfile(real_path):
                        task['copy'] = CommentedMap([
                            ('src', src),
                            ('dest', dest)])
                    else:
                        continue
                    tasks.append(task)
        for task in tasks:
            if self.user:
                task['remote_user'] = self.user
        return tasks

    def parse_COPY(self, payload, comments):
        return self.parse_ADD(payload, comments=comments, url_and_tarball=False)

    parse_ENTRYPOINT = _simple_meta_parser('entrypoint')

    def parse_VOLUME(self, payload, comments):
        if not isinstance(payload, list):
            payload = payload.split(u' ')
        self.meta.setdefault('volumes', CommentedSeq()).extend(payload)
        self.meta.yaml_set_comment_before_after_key('volumes',
                                                    u'\n'.join(comments))
        return []

    def parse_USER(self, payload, comments):
        self.meta['user'] = payload
        self.meta.yaml_set_comment_before_after_key('user',
                                                    before=u'\n'.join(comments))
        self.user = payload
        return []

    def parse_WORKDIR(self, payload, comments):
        self.meta['working_dir'] = payload
        self.meta.yaml_set_comment_before_after_key('working_dir',
                                                    u'\n'.join(comments))
        self.working_dir = payload
        return []

    def parse_ARG(self, payload, comments):
        # ARG can either be set with a default or not
        if u'=' in payload:
            arg, default = payload.split(u'=', 1)
        else:
            arg, default = payload, u'~'
        self.variables[arg] = default
        self.variables.yaml_set_comment_before_after_key(arg,
                                                         u'\n'.join(comments))
        return []

    parse_ONBUILD = _simple_meta_parser('onbuild')

    parse_STOPSIGNAL = _simple_meta_parser('stop_signal')

    parse_HEALTHCHECK = _simple_meta_parser('healthcheck')

    def parse_SHELL(self, payload, comments):
        self.meta['shell'] = CommentedSeq(payload)
        self.meta.yaml_set_comment_before_after_key('shell',
                                                    u'\n'.join(comments))
        self.shell = u' '.join(payload)
        return []


class DockerfileImport(object):
    project_name = None
    import_from = None
    base_path = None

    def __init__(self, base_path, project_name, import_from, bundle_files):
        # The path to write the Ansible Container project to
        self.base_path = base_path
        # The name of the Ansible Container project
        self.project_name = project_name
        # The path containing the Dockerfile and build context
        self.import_from = import_from
        # Whether to bundle files in import_from into the role or to leave them
        # as part of the build context
        self.bundle_files = bundle_files

    @property
    def role_path(self):
        return os.path.join(self.base_path, 'roles', os.path.basename(self.import_from))

    def copytree(self, src, dst, symlinks=False, ignore=None):
        if ignore:
            ignored = ignore(src, os.listdir(src))
        else:
            ignored = []
        for item in os.listdir(src):
            if item in ignored:
                continue
            s = os.path.join(src, item)
            d = os.path.join(dst, item)
            if os.path.isdir(s):
                shutil.copytree(s, d, symlinks, ignore)
            else:
                shutil.copy2(s, d)

    def copy_files_from_src(self):
        if self.bundle_files:
            target = os.path.join(self.role_path, 'files')
        else:
            target = self.base_path
        self.copytree(self.import_from,
                      target,
                      ignore=lambda dir, files: ['Dockerfile']
                      if dir == self.import_from else [])

    def run(self):
        # FIXME: ensure self.base_path is empty
        parser = DockerfileParser(self.import_from,
                                  default_vars={'playbook_debug': False})
        try:
            self.create_role_from_template()
            for data, path in [
                (list(parser), os.path.join(self.role_path, 'tasks', 'main.yml')),
                (parser.variables, os.path.join(self.role_path, 'defaults', 'main.yml')),
                (parser.meta, os.path.join(self.role_path, 'meta', 'container.yml')),
                (parser.container_yml, os.path.join(self.base_path, 'container.yml'))
            ]:
                if not os.path.exists(os.path.dirname(path)):
                    os.makedirs(os.path.dirname(path))
                with open(path, 'w') as ofs:
                    ruamel.yaml.round_trip_dump(data, ofs)
            self.copy_files_from_src()
        except Exception, e:
            #try:
            #    shutil.rmtree(self.base_path)
            #except Exception, e:
            #    pass
            raise
        self.explain_wtf_just_happened()

    def create_role_from_template(self):
        '''
        Create roles/dockerfile-to-ansible path and role structure.
        :return: None
        '''
        description = u"Imported Dockerfile for {}".format(self.project_name)

        create_role_from_templates(role_name=os.path.basename(self.import_from),
                                   role_path=self.role_path,
                                   project_name=self.project_name,
                                   description=description)

    def explain_wtf_just_happened(self):
        logger.info(u'Project successfully imported. You can find the results '
                    u'in:\n%s', self.base_path)
        logger.info(u'A brief description of what you will find...\n\n')
        logger.info(u'container.yml')
        logger.info(u'-------------\n')
        logger.info(u'The container.yml file is your orchestration file that '
                    u'expresses what services you have and how to build/run them.\n')
        with open(os.path.join(self.base_path, 'container.yml')) as ifs:
            logger.info(ifs.read()+u'\n')
        logger.info(u'I added a single service named %s for your imported '
                    u'Dockerfile.', os.path.basename(self.import_from))
        logger.info(u'As you can see, I made an Ansible role for your '
                    u'service, which you can find in:\n%s\n',
                    os.path.join(self.base_path, 'roles',
                                 os.path.basename(self.import_from)))
        tasks_main_yml = os.path.join(self.base_path,
                                      'roles',
                                      os.path.basename(self.import_from),
                                      'tasks',
                                      'main.yml')
        rel_tasks_main_yml = os.path.relpath(tasks_main_yml,
                                             os.path.dirname(self.base_path))
        logger.info(rel_tasks_main_yml)
        logger.info(u'-' * len(rel_tasks_main_yml) + u'\n')
        logger.info(u'The tasks/main.yml file has your RUN/ADD/COPY instructions.\n')
        with open(tasks_main_yml) as ifs:
            logger.info(ifs.read()+u'\n')
        logger.info(u'I tried to preserve comments as task names, but you '
                    u'probably want to make')
        logger.info(u'sure each task has a human readable name.\n')

        meta_container_yml = os.path.join(self.base_path,
                                      'roles',
                                      os.path.basename(self.import_from),
                                      'meta',
                                      'container.yml')
        rel_meta_container_yml = os.path.relpath(meta_container_yml,
                                                 os.path.dirname(self.base_path))
        logger.info(rel_meta_container_yml)
        logger.info(u'-' * len(rel_meta_container_yml) + u'\n')
        logger.info(u'Metadata from your Dockerfile went into '
                    u'meta/container.yml in your role.')
        logger.info(u'These will be used as build/run defaults for your role.\n')
        with open(meta_container_yml) as ifs:
            logger.info(ifs.read()+u'\n')

        logger.info(u'I also stored ARG directives in the role\'s '
                    u'defaults/main.yml which will used as')
        logger.info(u'variables by Ansible in your build and run operations.\n')
        logger.info(u'Good luck!')







