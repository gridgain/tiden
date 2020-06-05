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

from .sshpool import SshPool
from .util import log_print
from .logger import get_logger
import sys
from os import path, makedirs, environ
from datetime import datetime
from shutil import copy, copy2, copyfile
import subprocess

if 'win' in sys.platform and not 'darwin' in sys.platform:
    raise NotImplementedError("LocalPool not yet supported for Windows")

debug_local_pool = False


class LocalPool(SshPool):
    """
    Local pool emulates N hosts by faking config['environment']['home'] to unique local directory per each 'host'.
    All commands are actually executed locally (POSIX compatible shell required!).
    NB: this may result in unexpected behaviour, use with caution, beware of hedgehogs!
    """
    def __init__(self, ssh_config, **kwargs):
        super(LocalPool, self).__init__(ssh_config, **kwargs)
        for host in self.hosts:
            assert host.startswith('127.0'), "Mixing local and remote hosts is not supported!"

    @staticmethod
    def _now():
        return datetime.now().strftime("[%Y:%m:%d %H:%M:%S]")

    def trace_info(self):
        pass

    def connect(self):
        if debug_local_pool:
            print("%s: connect()" % (
                LocalPool._now(),
            ))
        for host in self.hosts:
            makedirs(path.join(self.home, host), exist_ok=True)

    def upload_on_host(self, host, files, remote_dir):
        if debug_local_pool:
            print("%s: upload_on_host(%s, %s, %s)" % (
                LocalPool._now(),
                host,
                files,
                remote_dir
            ))
        host_home = path.join(self.home, host)
        if self.home in remote_dir:
            remote_dir = remote_dir.replace(self.home, host_home)
        for local_file in files:
            remote_path = remote_dir + '/' + path.basename(local_file)
            # print(local_file, remote_path)
            copy2(local_file, remote_path)

    def download_from_host(self, host, remote_path, local_path):
        if debug_local_pool:
            print("%s: download_from_host(%s, %s, %s)" % (
                LocalPool._now(),
                host,
                remote_path,
                local_path,
            ))
            host_home = path.join(self.home, host)
            if self.home in remote_path:
                remote_path = remote_path.replace(self.home, host_home)
                copy2(remote_path, local_path)
        return {}

    def exec_on_host(self, host, commands):
        if debug_local_pool:
            print("%s: exec_on_host(%s, %s)" % (
                LocalPool._now(),
                host,
                commands,
            ))
        output = []
        host_home = path.join(self.home, host)
        timeout = 60
        env = environ.copy()
        if self.config.get('env_vars'):
            env.update(self.config['env_vars'])

        for command in commands:
            try:
                # remove trailing redirect to stderr because we do it via stderr argument to check_output already
                if command.endswith('2>&1'):
                    command = command[:-(len('2>&1'))]
                if self.home in command:
                    command = command.replace(self.home, host_home)
                get_logger('tiden').debug('%s >> %s' % (host, command))

                proc_args = ['/usr/bin/env']
                proc_args.extend(command.split(" "))

                stdout = subprocess.check_output(
                    command,
                    shell=True,
                    # args=proc_args,
                    # executable=proc_args[0],
                    env=env,
                    cwd=host_home,
                    timeout=timeout,
                    stderr=subprocess.STDOUT
                ).decode('utf-8')

                output.append(stdout) #.strip())
                get_logger('tiden').debug('<< %s' % output)
            except Exception as e:
                get_logger('tiden').error("%s" % e)

        return {host: output}

    def get_process_and_owners(self):
        return self.jps()

    def jps(self):
        """
        jps is hacked to execute on single 'host' and reorder PIDs per 'host' basing on cwd of the process.
        process must be either started from host directory (config['environment']['home']/<host>/) or have host
        directory in cmdline. otherwise it will left bound to first host.
        :return:
        """
        if debug_local_pool:
            print("%s: jps()" % (
                LocalPool._now(),
            ))
        first_host = self.hosts[0]
        raw_results = super(LocalPool, self).jps(hosts=[first_host])
        results = []
        for result in raw_results:
            bound_to_host = None
            proc_pid = int(result['pid'])
            cwd = self.exec_on_host(first_host, ['ls -l /proc/%d/cwd' % (proc_pid + 1)])
            if len(cwd) == 0 or first_host not in cwd.keys() or len(cwd[first_host]) == 0:
                # something wrong with process, it might have died, skip it
                continue
            cwd = cwd[first_host][0]
            cmdline = self.exec_on_host(first_host, ['cat /proc/%d/cmdline | tr "\\0" " "' % (proc_pid+1)])
            if len(cmdline) == 0 or first_host not in cmdline.keys() or len(cmdline[first_host]) == 0:
                # something wrong with process, it might have died, skip it
                continue
            cmdline = cmdline[first_host][0]

            for host in self.hosts:
                host_home = path.join(self.home, host)
                if host_home in cwd:
                    bound_to_host = host
                    break
                if host_home in cmdline:
                    bound_to_host = host
                    break
            if bound_to_host is None:
                bound_to_host = first_host
            results.append({'host': bound_to_host, 'pid': result['pid'], 'name': result['name']})
        return results

    def killall(self, name, sig=-9):
        """
        killall is also hacked to be executed on first host only
        :param name:
        :param sig:
        :return:
        """
        if debug_local_pool:
            print("%s: killall(%s, %d)" % (
                LocalPool._now(),
                name,
                sig,
            ))
        return super(LocalPool, self).killall(name, sig=sig, hosts=[self.hosts[0]])

    # === after goes simple delegates, the only actual meaning of them is to dump debug info.

    def upload(self, files, remote_path):
        if debug_local_pool:
            print("%s: upload(%s, %s)" % (
                LocalPool._now(),
                files,
                remote_path,
            ))
        return super(LocalPool, self).upload(files, remote_path)

    def download(self, remote_path, local_path, prepend_host=True):
        if debug_local_pool:
            print("%s: download(%s, %s, prepend_host=%s)" % (
                LocalPool._now(),
                remote_path,
                local_path,
                prepend_host,
            ))
        return super(LocalPool, self).download(remote_path, local_path, prepend_host=prepend_host)

    def exec(self, commands, **kwargs):
        if debug_local_pool:
            if len(kwargs) > 0:
                print("%s: exec(%s, %s)" % (
                    LocalPool._now(),
                    commands,
                    ",".join([str(key)+":"+str(val) for key, val in kwargs])
                ))
            else:
                print("%s: exec(%s)" % (
                    LocalPool._now(),
                    commands
                ))
        return super(LocalPool, self).exec(commands, **kwargs)

    def dirsize(self, dir_path, *args):
        if debug_local_pool:
            print("%s: dirsize(%s, %s)" % (
                LocalPool._now(),
                dir_path,
                ",".join(args)
            ))
        return super(LocalPool, self).dirsize(dir_path, *args)

    def not_uploaded(self, files, remote_path):
        if debug_local_pool:
            print("%s: not_uploaded(%s, %s)" % (
                LocalPool._now(),
                files,
                remote_path
            ))
        return super(LocalPool, self).not_uploaded(files, remote_path)

    def available_space(self):
        if debug_local_pool:
            print("%s: available_space()" % (
                LocalPool._now(),
            ))
        return super(LocalPool, self).available_space()

