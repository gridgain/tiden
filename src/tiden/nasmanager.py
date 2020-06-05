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

from .util import log_put, log_print, print_blue, print_red
from .sshpool import SshPool
from .tidenexception import TidenException


class NasManagerException(TidenException):
    pass


class NasManager:

    # private SshPool to work with NAS
    ssh = None

    # NAS local root available for Tiden
    share_root = None

    # NAS IP address
    share_host = None

    # NAS mount point at non-NAS hosts
    share_mount_home = None

    folder_remove_timeout = 60

    def __init__(self, config):
        self.config = config
        self._init()

    def _init(self):
        share_config = self.config['environment'].get('share_storage', {})
        self.share_host = share_config.get('host')

        if 'folder_remove_timeout' in share_config:
            self.folder_remove_timeout = int(share_config['folder_remove_timeout'])

        self.share_root = share_config.get('root')
        self.share_home = share_config.get('home')

        if not self.share_host or not self.share_home or not self.share_root:
            print_red('WARNING: NasManager environment.share_storage configuration missing!')
            return

        config = {
            'ssh': {
                'threads_num': 1,
                'hosts': [
                    self.share_host
                ],
                'default_timeout': SshPool.default_timeout,
                'username': self.config['environment'].get('username'),
                'private_key_path': self.config['environment'].get('private_key_path'),
                'home': self.share_root,
            },
        }

        if self.config['environment'].get('env_vars'):
            config['ssh']['env_vars'] = self.config['environment']['env_vars']

        # Make SSH connection pool
        connection_mode = self.config['connection_mode']
        if 'ansible' == connection_mode:
            try:
                from tiden.ansiblepool import AnsiblePool

                self.ssh = AnsiblePool(config['ssh'])
            except ImportError as e:
                log_put('Error: unable to import AnsiblePool: %s' % e)
                exit(1)
        elif 'paramiko' == connection_mode:
            self.ssh = SshPool(config['ssh'])
        elif 'local' == connection_mode:
            try:
                from tiden.localpool import LocalPool
                self.ssh = LocalPool(config['ssh'])
            except ImportError as e:
                log_put('Error: unable to import LocalPool: %s' % e)
                exit(1)
            except NotImplementedError as e:
                log_put('Error: %s' % e)
                exit(1)

        if self.ssh:
            self.ssh.connect()

    def get_share_mount_point(self):
        return self.share_home

    def get_share_root(self):
        return self.share_root

    def is_configured(self):
        return self.ssh is not None

    def remove_shared_folder(self, folder):
        if not self.is_configured():
            raise NasManagerException('Shared folder not configured')

        folder = folder.strip()
        if folder == '' or folder == '/':
            print_red('WARNING: attempt to remove NAS root!')
            return False

        snapshot_storage = folder.replace(self.share_home, self.share_root)
        command = 'if [ -d "{ss}" ]; then ' \
                  '  rm -fr {ss}; ' \
                  'fi && echo "Done"'.format(ss=snapshot_storage)
        print_blue('Going to remove shared storage: %s.' % snapshot_storage)
        result = self.ssh.exec([command], timeout=self.folder_remove_timeout)
        log_print(result)
        return 'Done' in result[self.share_host][0]

    def create_shared_folder(self, folder, cleanup=True):
        """
        creates shared folder and return its absolute path
        :param folder: folder name
        :param cleanup: set to False if directory should not be recreated
        :return:
        """
        if not self.is_configured():
            raise NasManagerException('NasManager (shared folder) is not configured')

        snapshot_storage = self.get_share_root() + '/' + folder
        log_print('Going to create shared storage: {}'.format(snapshot_storage), color='debug')
        cleanup_str = '  echo "Cleaning up {ss}"; ' \
                      '  rm -fr {ss}; ' \
                      '  echo "Recreating {ss}"; ' \
                      '  mkdir -p {ss} 2>&1; '
        check_and_create = [
            'if [ -d "{ss}" ]; then ',
            '  echo "Recreating {ss}"; ',
            'else '
            '  echo "Creating {ss}";'
            '  mkdir -p {ss} 2>&1; '
            'fi; '
            'echo "Result code: $?";'
        ]
        command = check_and_create
        if cleanup:
            command.pop(1)
            command.insert(1, cleanup_str)

        command = ''.join(command).format(ss=snapshot_storage)
        result = self.ssh.exec([command])
        log_print(result, color='debug')

        return self.share_home + '/' + folder

    def touch_file(self, file):
        if not self.is_configured():
            raise NasManagerException('NasManager (shared folder) is not configured')

        shared_file = self.get_share_root() + '/' + file
        log_print('Going to touch shared file: %s.' % shared_file)
        command = 'touch {sf}; ' \
                  'echo "Result code: $?";'.format(sf=shared_file)
        result = self.ssh.exec([command])
        # log_debug(result)
        return self.share_home + '/' + file

    def delete_file(self, file):
        if not self.is_configured():
            raise NasManagerException('NasManager (shared folder) is not configured')

        shared_file = self.get_share_root() + '/' + file
        print_blue('Going to delete shared file: %s.' % shared_file)
        command = 'rm -f {sf}; ' \
                  'echo "Result code: $?";'.format(sf=shared_file)
        result = self.ssh.exec([command])
        log_print(result)

