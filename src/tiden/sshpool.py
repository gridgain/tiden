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

from hashlib import md5
from multiprocessing.dummy import Pool as ThreadPool
from time import sleep

from paramiko import AutoAddPolicy, SSHClient, SSHException
from paramiko.buffered_pipe import PipeTimeout
import socket
from re import search, split
from .util import log_print, log_put, log_add, get_logger
from os import path
from .tidenexception import RemoteOperationTimeout,TidenException
from random import choice


class AbstractSshPool:
    def __init__(self, ssh_config=None, **kwargs):
        self.config = ssh_config if ssh_config is not None else {}
        self.hosts = self.config.get('hosts', [])

    def get_random_host(self):
        return choice(self.hosts)

    def trace_info(self):
        raise NotImplementedError

    def available_space(self):
        raise NotImplementedError

    def connect(self):
        raise NotImplementedError

    def download(self, remote_path, local_path, prepend_host=True):
        raise NotImplementedError

    def exec(self, commands, **kwargs):
        raise NotImplementedError

    def exec_on_host(self, host, commands, **kwargs):
        raise NotImplementedError

    def jps(self, jps_args=None, hosts=None, skip_reserved_java_processes=True):
        raise NotImplementedError

    def dirsize(self, dir_path, *args):
        raise NotImplementedError

    def upload(self, files, remote_path):
        raise NotImplementedError

    def not_uploaded(self, files, remote_path):
        raise NotImplementedError

    def killall(self, name, sig=-9, skip_reserved_java_processes=True, hosts=None):
        raise NotImplementedError


class SshPool(AbstractSshPool):
    default_timeout = 400
    no_java_commands = [
        'echo', 'cat', 'grep', 'kill', 'ps', 'ls', 'ln', 'mkdir', 'rm', 'md5sum', 'unzip', 'touch', 'chmod'
    ]

    def __init__(self, ssh_config, **kwargs):
        super(SshPool, self).__init__(ssh_config, **kwargs)
        self.retries = kwargs.get('retries')
        self.username = self.config['username']
        self.private_key_path = self.config['private_key_path']
        self.threads_num = self.config['threads_num']
        self.home = str(self.config['home'])
        if self.retries is None:
            self.retries = 3
        self.clients = {}

        self.trace_info()

    def trace_info(self):
        """
        called at startup to trace pool configuration to logs
        :return:
        """
        log_print('SSH Pool threads: %s' % self.config['threads_num'])

    def available_space(self):
        """
        calculate available disk space per host
        :return:
        """
        total_size = 0
        min_size = None
        threshold = 10
        problem_hosts = set()
        to_gb = lambda x: int(int(x) / 1048576)
        results = self.exec(['df -l'])
        for host in results.keys():
            lines = results[host][0]
            for line in lines.split('\n'):
                storage_items = split('\s+', line)
                if len(storage_items) == 6:
                    match = search('^[0-9]+$', storage_items[3])
                    if (match and
                            self.home.startswith(storage_items[5]) and
                            storage_items[5] != '/'):
                        total_size += int(storage_items[3])
                        if min_size is None:
                            min_size = int(storage_items[3])
                        min_size = min(int(storage_items[3]), min_size)
                        if to_gb(min_size) < threshold:
                            problem_hosts.add('WARNING! host {} has free space less than {}GB ({}GB actual)'
                                              .format(host, threshold, to_gb(min_size)))
        if min_size is None:
            min_size = total_size

        if problem_hosts:
            return str(to_gb(total_size)), problem_hosts
        else:
            return str(to_gb(total_size)), '{} GB'.format(to_gb(min_size))

    def connect(self):
        for host in self.hosts:
            attempt = 0
            log_put("Checking connection to %s ... " % host, 2)
            connected = False
            ssh = None
            if self.private_key_path != '' and self.private_key_path is not None:
                if not path.exists(self.private_key_path):
                    raise TidenException("Private key %s not found" % self.private_key_path)
            while attempt < self.retries and not connected:
                try:
                    attempt += 1
                    ssh = SSHClient()
                    ssh.load_system_host_keys()
                    ssh.set_missing_host_key_policy(AutoAddPolicy())
                    ssh.connect(
                        host,
                        username=self.username,
                        key_filename=self.private_key_path,
                    )
                    ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command('uptime')
                    for line in ssh_stdout:
                        if 'load average' in str(line):
                            log_print('ok', 3)
                            self.clients[host] = ssh
                            attempt = self.retries + 1
                            connected = True
                        break
                except socket.gaierror as e:
                    log_print('', 2)
                    log_print("Error: host '%s' is incorrect \n" % host, color='red')
                    log_print("%s\n" % str(e))
                    exit(1)
                except TimeoutError as e:
                    log_add('T ', 3)
                    if attempt == self.retries:
                        log_print('', 2)
                        log_print("Error: connection timeout to host %s\n" % host, color='red')
                        log_print("%s\n" % str(e))
                        exit(1)
                except SSHException as e:
                    log_add('E ', 3)
                    if attempt == self.retries:
                        log_print('', 2)
                        log_print("Error: SSH error for host=%s, username=%s, key=%s" %
                                  (host, str(self.username), str(self.private_key_path)), 2, color='red')
                        log_print(str(e), 2)
                        exit(1)

    def download(self, remote_path, local_path, prepend_host=True):
        files_for_hosts = []
        for host in self.hosts:
            file = local_path
            if path.isdir(file):
                if prepend_host is True:
                    file = "%s/%s%s" % (file, host, path.basename(remote_path))
                else:
                    file = "%s/%s" % (file, path.basename(remote_path))
                files_for_hosts.append(
                    [host, remote_path, file]
                )
            else:
                files_for_hosts.append(
                    [host, remote_path, file]
                )
        pool = ThreadPool(self.threads_num)
        pool.starmap(self.download_from_host, files_for_hosts)
        pool.close()
        pool.join()

    def download_from_host(self, host, remote_path, local_path):
        try:
            sftp = self.clients.get(host).open_sftp()
            sftp.get(remote_path, local_path)
        except SSHException as e:
            print(str(e))

    def exec(self, commands, **kwargs):
        """
        :param commands: the list of commands to execute for hosts
        :return: the list of lines
        """
        from functools import partial
        commands_for_hosts = []
        output = []
        if isinstance(commands, list):
            for host in self.hosts:
                commands_for_hosts.append(
                    [host, commands]
                )
        elif isinstance(commands, dict):
            for host in commands.keys():
                commands_for_hosts.append(
                    [host, commands[host]]
                )
        else:
            for host in self.hosts:
                commands_for_hosts.append(
                    [host, [commands]]
                )
        pool = ThreadPool(self.threads_num)
        raw_results = pool.starmap(partial(self.exec_on_host, **kwargs), commands_for_hosts)
        results = {}
        for raw_result in raw_results:
            for host in raw_result.keys():
                results[host] = raw_result[host]
        pool.close()
        pool.join()
        return results

    def exec_on_host(self, host, commands, **kwargs):
        """
        Execute the list of commands on the particular host
        :param host:        host or ip address
        :param commands:    the command or the list of commands
        :return:            dictionary:
            <host>: [ <string containing the output of executed commands>, ... ]
        """
        output = []
        client = self.clients[host]
        env_vars = ''
        timeout = kwargs.get('timeout', int(self.config['default_timeout']))

        if self.config.get('env_vars'):
            for env_var_name in self.config['env_vars'].keys():
                val = self.config['env_vars'][env_var_name]
                env_vars += f"{env_var_name}={val};"
        for command in commands:
            try:
                if '2>&1' not in command:
                    command += ' 2>&1'
                if env_vars != '' and command.split()[0] not in self.no_java_commands:
                    command = f"{env_vars}{command}"
                # TODO we should handle stderr
                get_logger('ssh_pool').debug(f'{host} >> {command}')
                stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
                command_output = ''
                for line in stdout:
                    if line.strip() != '':
                        command_output += line
                for line in stderr:
                    if line.strip() != '':
                        command_output += line
                output.append(command_output)
                formatted_output = ''.join(output).encode('utf-8')
                get_logger('ssh_pool').debug(f'{host} << {formatted_output}')
            except SSHException as e:
                if str(e) == 'SSH session not active' and not kwargs.get('repeat'):
                    # reconnect
                    for i in range(10):
                        try:
                            log_print('ssh reconnect')
                            self.connect()
                        except SSHException:
                            sleep(10)
                            continue
                        break
                    kwargs['repeat'] = True
                    return self.exec_on_host(host, commands, **kwargs)
                print(str(e))
            except (PipeTimeout, socket.timeout) as e:
                raise RemoteOperationTimeout(f'Timeout {timeout} reached while executing command:\n'
                                             f'Host: {host}\n'
                                             f'{command}')
        return {host: output}

    @staticmethod
    def _reserved_java_processes():
        """
        These java processes are hidden from jps and killall('java').
        The first item of list must always be 'jps' itself.
        :return:
        """
        return [
            'sun.tools.jps.Jps',
            'jenkins.war',
            'com.intellij.idea.Main',
            'org.jetbrains.idea.maven.server.RemoteMavenServer',
            'org.jetbrains.jps.cmdline.Launcher'
        ]

    def get_process_and_owners(self, hosts=None, skip_reserved_java_processes=True):
        """
        Returns parsed and filtered for output of `ps -ef | grep java` command executed on hosts.
        :param hosts: (optional) array of hosts to run command at
        :param skip_reserved_java_processes: (optional, default True)
        :return: list of dictionaries:
           'host': host
           'owner': java process owner
           'pid': java process pid
        """
        jps_command = ['ps -ef | grep java | grep -v grep']

        if hosts is not None:
            jps_command = {host: jps_command for host in hosts}
        raw_results = self.exec(jps_command)
        results = []
        for host in raw_results.keys():
            for line in raw_results[host][0].splitlines():
                if skip_reserved_java_processes:
                    is_reserved_process = False
                    for proc_name in SshPool._reserved_java_processes():
                        if proc_name in line:
                            is_reserved_process = True
                            break
                    if is_reserved_process:
                        continue
                else:
                    # skip only 'jps'
                    if SshPool._reserved_java_processes()[0] in line:
                        continue
                m = search('^([0-9\w]+)\s+([0-9]+)', line)
                if m:
                    results.append({'host': host, 'owner': m.group(1), 'pid': m.group(2)})
        return results

    def ls(self, hosts=None, dir_path=None, params=None):
        ls_cmd = 'ls' if not params else 'ls {}'.format(params)
        ls_command = ['{}'.format(ls_cmd)] if not dir_path else ['{} {}'.format(ls_cmd, dir_path)]

        if hosts:
            ls_command = {host: ls_command for host in hosts}

        raw_results = self.exec(ls_command)
        results = {}
        for host in raw_results.keys():
            results[host] = raw_results[host][0].split('\n')

        return results

    def jps(self, jps_args=None, hosts=None, skip_reserved_java_processes=True):
        """
        Returns parsed and filtered for output of `jps` command executed on hosts.
        :param jps_args: (optional) array of 'jps' arguments, defaults to '-l' for full main java class name
        :param hosts: (optional) array of hosts to run command at
        :param skip_reserved_java_processes: (optional, default True)
        :return: list of dictionaries:
           'host': host
           'pid': java process pid
           'name': java process name
        """
        jps_command = ['jps']
        if jps_args is not None:
            jps_command.extend(jps_args)
        else:
            jps_command.append('-l')
        jps_command = [" ".join(jps_command)]
        if hosts is not None:
            jps_command = {host: jps_command for host in hosts}
        raw_results = self.exec(jps_command)
        results = []
        for host in raw_results.keys():
            for line in raw_results[host][0].splitlines():
                if skip_reserved_java_processes:
                    is_reserved_process = False
                    for proc_name in SshPool._reserved_java_processes():
                        if proc_name in line:
                            is_reserved_process = True
                            break
                    if is_reserved_process:
                        continue
                else:
                    # skip only 'jps'
                    if SshPool._reserved_java_processes()[0] in line:
                        continue
                m = search('^([0-9]+) (.+)$', line)
                if m:
                    results.append({'host': host, 'pid': m.group(1), 'name': m.group(2)})
        return results

    def dirsize(self, dir_path, *args):
        hosts = self.hosts
        if len(args) == 1:
            hosts = args[0]
        cmd = {}
        for host in hosts:
            cmd[host] = ['du -sb %s' % dir_path]
        result = self.exec(cmd)
        cur_size = 0
        for host in result.keys():
            for line in result[host]:
                m = search('^([0-9]+)\t', line)
                if m:
                    cur_size += int(m.group(1))
        return cur_size

    def upload(self, files, remote_path):
        files_for_hosts = []
        for host in self.hosts:
            files_for_hosts.append(
                [host, files, remote_path]
            )
        pool = ThreadPool(self.threads_num)
        pool.starmap(self.upload_on_host, files_for_hosts)
        pool.close()
        pool.join()

    def upload_for_hosts(self, hosts, files, remote_path):
        files_for_hosts = []
        for host in hosts:
            files_for_hosts.append(
                [host, files, remote_path]
            )
        pool = ThreadPool(self.threads_num)
        pool.starmap(self.upload_on_host, files_for_hosts)
        pool.close()
        pool.join()

    def not_uploaded(self, files, remote_path):
        outdated = []
        for file in files:
            file_name = path.basename(file)
            local_md5 = md5(open(file, 'rb').read()).hexdigest()
            remote_file = "%s/%s" % (remote_path, file_name)
            results = self.exec(['md5sum %s' % remote_file])
            matched_count = 0
            for host in results.keys():
                if len(results[host]) > 0:
                    if '%s ' % local_md5 in results[host][0]:
                        matched_count += 1
            if matched_count < len(results.keys()):
                outdated.append(file)
        return outdated

    def upload_on_host(self, host, files, remote_dir):
        try:
            sftp = self.clients.get(host).open_sftp()
            for local_file in files:
                remote_path = remote_dir + '/' + path.basename(local_file)
                get_logger('ssh_pool').debug('sftp_put on host %s: %s -> %s' % (host, local_file, remote_path))
                sftp.put(local_file, remote_path)
        except SSHException as e:
            print(str(e))

    def killall(self, name, sig=-9, skip_reserved_java_processes=True, hosts=None):
        """
        Kill all java processes that might interfere grid at all hosts of connected pool.

        :param name: name of processes to kill
        :param sig: signal to send, default -9 (SIG_KILL)
        :param skip_reserved_java_processes: (default True) skip known developer/debugger java processes
        :param hosts: hosts where to kill java processes (default None means all hosts)
        :return:
        """
        if name != 'java' or not skip_reserved_java_processes:
            kill_command = [
                'nohup '
                '  sudo '
                '    -n '
                '    killall '
                '      %s '
                '      %s '
                '& > /dev/null 2>&1' % (
                    sig,
                    name
                )]
        else:
            kill_command = [
                'ps -AF '
                '| grep [j]ava 2>/dev/null '
                '| grep -vE "(%s)" 2>/dev/null '
                '| awk "{print \$2}" '
                '| xargs -i{} '
                '    nohup '
                '    sudo '
                '      -n '
                '      /bin/kill '
                '        %s {} '
                '    & >/dev/null 2>&1'
                % (
                    "|".join([s.replace('.', '\.') for s in SshPool._reserved_java_processes()]),
                    sig,
                )
            ]
        if hosts is not None:
            kill_command = {host: kill_command for host in hosts}

        res = self.exec(kill_command)
        # print_blue(res)
        return res

