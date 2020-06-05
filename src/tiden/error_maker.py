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

from .logger import get_logger


class FileSystemErrorMaker:
    ssh = None

    def __init__(self, ssh):
        self.ssh = ssh
        self.logger = get_logger('ErrorMaker')

    def util_remote_ls(self, host, remote_path):
        """
        Remote ls command. Returns file names if any.
        :param host: remote host
        :param remote_path: path where ls should be run
        :return: list of file names
        """
        command = ['ls %s' % remote_path]
        results = self.ssh.exec_on_host(host, command)
        self.logger.debug(results)
        files = [file_name for file_name in results[host][0].split('\n') if file_name]
        self.logger.debug(results)
        return files

    def allocate_disc_space(self, host, remote_path, size):
        """
        Allocate file of some size on particular file storage using unix fallocate command.
        :param host: remote host
        :param remote_path: path where file should be crated
        :param size: size of the file
        :return:
        """
        commands = ['fallocate -l %s %s/test_file1.img' % (size, remote_path)]
        self.logger.debug(commands)
        response = self.ssh.exec_on_host(host, commands)
        self.logger.debug(response)
        return '%s/test_file1.img' % remote_path

    def corrupt_file(self, host, remote_file):
        """
        Just write some garbage to remote file using unix command:
        echo "Some garbage" > remote_file
        :param host: remote host
        :param remote_file: remote file or list of files
        :return:
        """
        self.operation_with_remote_files(host, 'echo "Some garbage" >', remote_file)

    def cleanup_file(self, host, remote_path):
        self.operation_with_remote_files(host, 'echo "" >', remote_path)

    def append_file(self, host, remote_path):
        self.operation_with_remote_files(host, 'echo "This should corrupt it" >>', remote_path)

    def remove_file(self, host, remote_path):
        self.operation_with_remote_files(host, 'rm', remote_path)

    def remove_folder(self, host, remote_path):
        self.operation_with_remote_files(host, 'rm -rf', remote_path)

    def make_lfs_readonly(self, host, remote_path):
        self.operation_with_remote_files(host, 'chmod -R 0444', remote_path)

    def operation_with_remote_files(self, host, op, remote_path):
        commands = dict()
        self.logger.debug("Making operation: %s on file: %s ... " % (op, remote_path))

        if isinstance(remote_path, list):
            remote_files = list(remote_path)
        else:
            remote_files = [str(remote_path)]

        for r_file in remote_files:
            if commands.get(host):
                commands[host].append('%s %s' % (op, r_file))
            else:
                commands = {host: ['%s %s' % (op, r_file)]}

        self.logger.debug(commands)
        results = self.ssh.exec(commands)
        self.logger.debug(results)


class IOErrorMaker:
    ignite = None
    ssh = None
    file_system_error = None

    def __init__(self, ign, ssh):
        self.ignite = ign
        self.ssh = ssh
        self.file_system_error = FileSystemErrorMaker(ssh)

    def make_wal_files_read_only(self, node_id=None):
        node_idx, host = self.run_on_ignite_host(node_id)
        node_home = self.ignite.nodes[node_idx]['ignite_home']
        wal_path = '%s/work/db/wal/%s/' % (node_home, self.ignite.get_node_consistent_id(node_idx))
        files = ['%s%s' % (wal_path, file_name)
                 for file_name in self.file_system_error.util_remote_ls(host, wal_path) if file_name]
        self.file_system_error.make_lfs_readonly(host, files)
        return node_idx, files

    def make_binary_meta_read_only(self, node_id=None):
        binary_meta_path = '%s/work/binary_meta/%s/'
        node_idx, remote_path = self.make_ignite_dir_read_only(path_template=binary_meta_path, node_id=node_id)
        return node_idx, remote_path

    def make_metastorage_read_only(self, node_id=None):
        remote_path = '%s/work/db/%s/metastorage'
        node_idx, remote_path = self.make_ignite_dir_read_only(path_template=remote_path, node_id=node_id)
        return node_idx, remote_path

    def make_work_db_read_only(self, node_id=None):
        remote_path = '%s/work/db/%s/'
        self.make_ignite_dir_read_only(path_template=remote_path, node_id=node_id)

    def make_cache_folder_read_only(self, node_id=None):
        remote_path = '%s/work/db/%s/cacheGroup-cache_group_1'
        node_idx, remote_path = self.make_ignite_dir_read_only(path_template=remote_path, node_id=node_id)

        return node_idx, remote_path

    def make_ignite_dir_read_only(self, path_template, node_id=None):
        node_idx, host = self.run_on_ignite_host(node_id)
        node_home = self.ignite.nodes[node_idx]['ignite_home']
        remote_path = path_template % (node_home, self.ignite.get_node_consistent_id(node_idx))
        self.file_system_error.make_lfs_readonly(host, remote_path)

        return node_idx, remote_path

    def delete_work_db(self, node_id=None):
        node_idx, host = self.run_on_ignite_host(node_id)
        cache_path = '%s/work/db/%s/cache-cache_group_1_015/' % (host, self.ignite.get_node_consistent_id(node_idx))
        files = ['%s%s' % (cache_path, file_name)
                 for file_name in self.file_system_error.util_remote_ls(host, cache_path) if file_name]
        self.file_system_error.remove_file(host, files)

    def delete_metastorage(self, node_id=None):
        node_idx, host = self.run_on_ignite_host(node_id)
        remote_path = '%s/work/db/%s/metastorage' % (host, self.ignite.get_node_consistent_id(node_idx))
        self.file_system_error.remove_folder(host, remote_path)

    def corrupt_work_db_files(self, node_id=None):
        node_idx, host = self.run_on_ignite_host(node_id)
        cache_path = '%s/work/db/%s/' % (host, self.ignite.get_node_consistent_id(node_idx))

        files = ['%s%s' % (cache_path, file_name)
                 for file_name in self.file_system_error.util_remote_ls(host, cache_path) if file_name]
        self.file_system_error.corrupt_file(host, files)

    def corrupt_wal_files(self, node_id=None, wal_path=None):
        node_idx, host = self.run_on_ignite_host(node_id)
        if not wal_path:
            wal_path = '%s/work/db/wal/%s/' % (host, self.ignite.get_node_consistent_id(node_idx))

        files = ['%s%s' % (wal_path, file_name)
                 for file_name in self.file_system_error.util_remote_ls(host, wal_path) if file_name]
        self.file_system_error.corrupt_file(host, files)

    def fix_lfs_access(self, node_idx, remote_path):
        if remote_path and node_idx:
            self.file_system_error.operation_with_remote_files(self.ignite.nodes[node_idx]['host'],
                                                               'chmod 755', remote_path)
        else:
            print_red("Could not fix access rights for path %s on node %s" % (remote_path, node_idx))

    def allocate_disc_space_on_node(self, node_id, storage, file_size):
        node_idx, host = self.run_on_ignite_host(node_id)
        file_path = self.file_system_error.allocate_disc_space(host, storage, file_size)
        return file_path

    def cleanup_disc_space_on_node(self, node_id, file_path):
        node_idx, host = self.run_on_ignite_host(node_id)
        self.file_system_error.remove_file(host, file_path)

    def run_on_ignite_host(self, node_id=None):
        server_nodes = self.ignite.get_all_default_nodes() + self.ignite.get_all_additional_nodes()
        node_idx = server_nodes[0]

        if node_id:
            node_idx = node_id

        return node_idx, self.ignite.nodes[node_idx]['host']

