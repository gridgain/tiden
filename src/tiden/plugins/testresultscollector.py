#!/usr/bin/env python3
#
# Copyright 2017-2020 GridGain Systems.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from tiden.tidenplugin import TidenPlugin, TidenPluginScope
from time import time
from re import search
from os import listdir, makedirs
from os.path import join, isfile
from zipfile import ZipFile
from tiden.util import is_enabled

TIDEN_PLUGIN_VERSION = '1.0.0'


class TestResultsCollector(TidenPlugin):

    default_exclude_masks = ['*.bin', '*.dat', '*.jar', '*.wal', '*.zip', '*.tar', 'work/*']

    remote_commands = [
        "zip --symlinks -r _logs.zip -i {include_mask} -x {exclude_mask}"
    ]

    download_masks = [
        "_logs.zip"
    ]

    # default behaviour is backward compatible: collect test results at test method level
    # can be overridden by `plugins.yaml`
    scope = TidenPluginScope.METHOD

    unpack_logs = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.options.get('remote_commands'):
            self.remote_commands = self.options['remote_commands']

        if self.options.get('download_masks'):
            self.download_masks = self.options['download_masks']

        self.scope = TidenPluginScope.from_options(self.name, self.options, self.scope)

        if self.scope == TidenPluginScope.METHOD:
            self.include_masks = ['./*']
            self.exclude_masks = self.default_exclude_masks.copy()
        elif self.scope == TidenPluginScope.CLASS:
            self.include_masks = ['./Test*', './*/work/log/*']
            self.exclude_masks = self.default_exclude_masks.copy()
            self.exclude_masks.extend(['./*/work/log/ignite*.log', './*/work/log/*.lck'])
        elif self.scope == TidenPluginScope.RUN:
            self.include_masks = ['./test_*']
            self.exclude_masks = self.default_exclude_masks.copy()
            self.exclude_masks.extend(['./*/work/log/ignite*.log', './*/work/log/*.lck'])

        if self.options.get('include_masks'):
            self.include_masks = self.options['include_masks']

        if self.options.get('exclude_masks'):
            self.exclude_masks = self.options['exclude_masks']

        if self.options.get('unpack_logs'):
            self.unpack_logs = is_enabled(self.options['unpack_logs'])

    def after_test_method_teardown(self, *args, **kwargs):
        if self.scope == TidenPluginScope.METHOD:
            self._collect_test_results(
                self.scope.scoped_remote_dir(self.config),
                self.include_masks,
                self.exclude_masks,
                self.scope.scoped_local_dir(self.config)
            )

    def after_test_class_teardown(self, *args, **kwargs):
        if self.scope == TidenPluginScope.CLASS:
            self._collect_test_results(
                self.scope.scoped_remote_dir(self.config),
                self.include_masks,
                self.exclude_masks,
                self.scope.scoped_local_dir(self.config)
            )

    def after_tests_run(self, *args, **kwargs):
        if self.scope == TidenPluginScope.RUN:
            self._collect_test_results(
                self.scope.scoped_remote_dir(self.config),
                self.include_masks,
                self.exclude_masks,
                self.scope.scoped_local_dir(self.config)
            )

    def _collect_test_results(self, remote_dir, include_masks, exclude_masks, local_dir):
        """
        Execute remote commands and download results
        :param remote_dir: starting from this remote directory ...
        :param include_masks: ... compress all files matching these include masks ...
        :param exclude_masks: ... excluding files matching these masks ...
        :param local_dir: ... and download archives to this local directory
        :return:
        """
        started = time()
        self.log_print("Execute remote commands in %s ..." % remote_dir)

        if type(include_masks) != type([]):
            include_masks = list(include_masks)
        if type(exclude_masks) != type([]):
            exclude_masks = list(exclude_masks)

        include_mask = ' '.join(include_masks)
        exclude_mask = ' '.join(exclude_masks)

        cmd = []

        for remote_command in self.remote_commands:
            final_remote_command = 'cd %s; %s' % (remote_dir, remote_command)
            final_remote_command = final_remote_command.replace('{include_mask}', include_mask)
            final_remote_command = final_remote_command.replace('{exclude_mask}', exclude_mask)
            final_remote_command = final_remote_command.replace('\\', '\\\\')
            final_remote_command = final_remote_command.replace('*', '\\*')

            cmd.append(final_remote_command)

        self.ssh.exec(cmd)
        self.log_put("Commands executed in %s sec" % int(time() - started))
        self.log_print()

        started = time()
        # Calculate total size for download
        total_download_size = 0
        for download_mask in self.download_masks:
            remote_file = "%s/%s" % (remote_dir, download_mask)
            res = self.ssh.exec(['stat -c%s {remote_file}'.format(remote_file=remote_file)])
            for host, output in res.items():
                m = search('^([0-9]+)\n', output[0])
                if m:
                    total_download_size += int(m.group(1))
        if total_download_size > 0:
            self.log_put("Download files %s bytes ..." % total_download_size)
            for download_mask in self.download_masks:
                makedirs(local_dir, exist_ok=True)
                self.ssh.download(
                    '%s/%s' % (remote_dir, download_mask),
                    local_dir,
                    prepend_host=True
                )
            self.log_put("Files downloaded in %s sec" % int(time() - started))
            self.log_print()

            if self.unpack_logs:
                log_dir = self.scope.scoped_local_dir(self.config)
                for file in listdir(log_dir):
                    full_path = "%s/%s" % (log_dir, file)
                    if isfile(full_path) and full_path.endswith('.zip'):
                        extract_dir = join(log_dir, file.replace('.zip', ''))
                        with ZipFile(full_path, "r") as old_zip:
                            makedirs(extract_dir, exist_ok=True)
                            old_zip.extractall(extract_dir)
        else:
            self.log_print("WARN: Nothing found to download", color='red')
