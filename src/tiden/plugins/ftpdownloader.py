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

from tiden.tidenplugin import TidenPlugin, TidenPluginException
from tiden.util import log_print, get_host_list

from re import search

TIDEN_PLUGIN_VERSION = '1.0.0'


class FtpDownloader(TidenPlugin):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.artifacts = {}
        self.current_artifact = None

        if self.options.get('host') and self.options.get('login') and self.options.get('password'):
            self.download_url = 'ftp://{}:{}@{}'.format(
                self.options.get('login'),
                self.options.get('password'),
                self.options.get('host')
            )
        else:
            raise TidenPluginException('FTP credentials have not found in FtpDownloader plugin configuration.')

        for artifact_name, artifact in self.config['artifacts'].items():
            # artifact = self.config['artifacts'][artifact_name]

            if artifact['glob_path'].startswith('ftp'):
                log_print('Artifact {} ({}) will be downloaded from FTP'.
                          format(artifact_name, artifact['glob_path']), color='blue')

                self.artifacts[artifact_name] = {
                    'file_name': artifact['glob_path'].split('/')[-1],
                    'path_on_host': '{}/{}'.format(self.config['remote']['suite_var_dir'], artifact_name),
                    'ftp_url': '{}/{}'.format(self.download_url, artifact['glob_path'][4:]),
                    'artifact_on_host': '{}/{}'.format(
                        self.config['remote']['artifacts_dir'],
                        artifact['glob_path'].split('/')[-1]
                    )
                }

                if artifact.get('repack'):
                    self.artifacts[artifact_name]['repack'] = True

                if artifact.get('remote_unzip'):
                    self.artifacts[artifact_name]['unzip'] = True

            else:
                log_print('Artifact {} ({}) will be uploaded from local host'.
                          format(artifact_name, artifact['glob_path']), color='blue')
                continue

    def after_hosts_setup(self, *args, **kwargs):
        for artifact in self.artifacts:
            self.current_artifact = artifact
            remote_path = self._remote_download()
            self.config['artifacts'][artifact]['remote_path'] = remote_path

            if self.artifacts[artifact].get('repack'):
                self._repack(artifact)

            if self.config['artifacts'][self.current_artifact].get('type') == 'ignite':
                self._extract_additional_info()

    def _extract_additional_info(self):
        any_host = self.config['environment']['server_hosts'][-1]
        libs_folder = '{}/libs'.format(self.config['artifacts'][self.current_artifact]['remote_path'])
        lib_files = self.ssh.ls(hosts=[any_host], dir_path=libs_folder)
        lib_files = lib_files.get(any_host)

        for file_prefix in ['ignite', 'gridgain']:
            core_file = [lib for lib in lib_files if '{}-core'.format(file_prefix) in lib]

            unzip_property_file = {
                any_host: ['cd {}; unzip {} {}.properties; tail {}.properties'
                               .format(libs_folder, core_file[0], file_prefix, file_prefix)]
            }
            output = self.ssh.exec(unzip_property_file)

            info = self._get_info_from_property_file(output[any_host][0])
            self.config['artifacts'][self.current_artifact].update(info)

        all_dirs = self.ssh.ls(hosts=[any_host], dir_path=self.config['artifacts'][self.current_artifact]['remote_path'])
        all_dirs = all_dirs.get(any_host)

        self.config['artifacts'][self.current_artifact]['symlink_dirs'] = all_dirs

    @staticmethod
    def _get_info_from_property_file(buffer):
        """
        Get info from ignite.properties and gridgain.properties files.
        """
        patterns = [
            ('ignite_version', 'ignite.version=(.*)\\n'), ('ignite_build', 'ignite.build=(.*)\\n'),
            ('ignite_rel_date', 'ignite.rel.date=(.*)\\n'), ('ignite_revision', 'ignite.revision=(.*)\\n'),
            ('gridgain_version', 'gridgain.version=(.*)\\n'), ('gridgain_build', 'gridgain.build=(.*)\\n'),
            ('gridgain_revision', 'gridgain.revision=(.*)\\n')
        ]
        info = {}

        for attr, pattern in patterns:
            m = search(pattern, buffer)
            if m:
                info[attr] = m.group(1)
        return info

    def _remote_download(self):
        """
        1. Download file from FTP to one host.
        2. Download from this host to others hosts over scp.
        2. Unzip file to dir = self.config['remote']['suite_var_dir'] + artifact_name
        3. Remove top level dir if needed.
        :return: remote_path
        """
        hosts = get_host_list(
            self.config['environment'].get('server_hosts'),
            self.config['environment'].get('client_hosts')
        )

        first_host = hosts.pop()
        self._download_with_wget(first_host, self._get_art_info('ftp_url'), self.config['remote']['artifacts_dir'])
        self._download_with_scp(first_host, hosts, self._get_art_info('artifact_on_host'))

        # unzip
        remote_path = self._get_art_info('artifact_on_host')

        if self._get_art_info('unzip'):
            artifact_file_name = self._get_art_info('file_name')
            unzip_dir_name = '.'.join(artifact_file_name.split('.')[:-1])
            remote_path = self._get_art_info('path_on_host')
            artifact_full_path = '{}/{}'.format(self.config['remote']['artifacts_dir'], artifact_file_name)

            unzip_cmd = self._unzip_command(artifact_full_path, remote_path)
            self.ssh.exec(unzip_cmd)

            # This hack need to remove top level directory
            self.ssh.exec(['mv {r_path}/{unzip_dir}/* {r_path}; rm -rf {r_path}/{unzip_dir}'.format(
                r_path=remote_path,
                unzip_dir=unzip_dir_name

            )])
        return remote_path

    @staticmethod
    def _unzip_command(artifact_full_path, remote_path):
        """
        Create command to unzip (or untar) artifact

        :param artifact_full_path: full path for artifact on remote host
        :param remote_path:     artifact remote host path
        :return:                unzip command
        """

        unzip_cmd = "unzip -u -q {} -d {}".format(artifact_full_path, remote_path)

        tar_formats = [".tar", '.tar.gz', '.tgz']
        found_formats = [fmt for fmt in tar_formats if artifact_full_path.endswith(fmt)]
        if found_formats:
            unzip_cmd = "mkdir {dir_name}; tar -xf {artifact_path} -C {dir_name} --strip-components 1".format(
                dir_name=remote_path,
                artifact_path=artifact_full_path,
            )

        return unzip_cmd

    def _download_with_wget(self, host, ftp_url, dir_to):
        download_with_wget = {host: ['cd {}; wget {}'.format(dir_to, ftp_url)]}
        self.ssh.exec(download_with_wget)

    def _download_with_scp(self, host_from, hosts_to, artifact_full_path):
        download_from_host = {}
        for host in hosts_to:
            download_from_host[host] = ['scp {}:{} {}'.format(host_from, artifact_full_path, artifact_full_path)]
        self.ssh.exec(download_from_host)

    def _get_art_info(self, key):
        return self.artifacts[self.current_artifact].get(key)

    def _repack(self, artifact):
        """
        Apply repack rules to deployed artifact.
        :param artifact:
        :return:
        """
        repack_rules = self.config['artifacts'][artifact].get('repack')

        repack_command = ['cd {}'.format(self.config['artifacts'][artifact]['remote_path'])]
        for rule in repack_rules:
            args = rule.split(' ')
            args = [arg.replace('self:', self.config['artifacts'][artifact]['remote_path']) for arg in args]

            if args[0] == 'delete':
                repack_command.append('rm -rf {}'.format(args[1]))
            elif args[0] == 'move':
                repack_command.append('mv {} {}'.format(args[1], args[2]))
            elif args[0] == 'copy':
                repack_command.append('cp {} {}'.format(args[1], args[2]))
            elif args[0] == 'mkdir':
                repack_command.append('mkdir {}'.format(args[1]))

        self.ssh.exec(repack_command)
