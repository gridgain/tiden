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

from tiden.tidenplugin import TidenPlugin
from time import time
from tiden.tidenfabric import TidenFabric

TIDEN_PLUGIN_VERSION = '1.0.0'


class ServerShareCheck(TidenPlugin):

    shared_file_name = 'check_share.%s.tmp' % time()
    shared_file_path = None
    failed_hosts = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def before_tests_run(self, *args, **kwargs):
        if not self._check_nas_manager_configured():
            return False
        self._create_shared_file()
        check_result = self._is_shared_file_found_at_all_hosts()
        if not check_result:
            self.log_print(
                'ERROR: configured shared folder not mounted at [%s]' % ','.join(self.failed_hosts),
                color='red'
            )
        else:
            self.log_print('Shared folder is mounted at all hosts', color='green')
        self._delete_shared_file()
        return check_result

    def _check_nas_manager_configured(self):
        nas_manager = TidenFabric().getNasManager()
        return nas_manager.is_configured()

    def _create_shared_file(self):
        nas_manager = TidenFabric().getNasManager()
        self.shared_file_path = nas_manager.touch_file(self.shared_file_name)

    def _is_shared_file_found_at_all_hosts(self):
        command = 'ls -la {sf} | grep "{sf}" 2>/dev/null'.format(sf=self.shared_file_path)
        result = self.ssh.exec([command])
        num_files = 0
        self.failed_hosts = []
        for host in result.keys():
            if result[host] and self.shared_file_path in result[host][0]:
                num_files += 1
            else:
                self.failed_hosts.append(host)

        return num_files == len(self.ssh.hosts)

    def _delete_shared_file(self):
        nas_manager = TidenFabric().getNasManager()
        nas_manager.delete_file(self.shared_file_name)
