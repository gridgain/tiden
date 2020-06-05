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

from tiden.localpool import LocalPool
import os.path


def test_local_pool_exec_on_host_rm_one_file(local_config):
    pool = LocalPool(local_config['ssh'])
    home_path = local_config['environment']['home']
    host = local_config['ssh']['hosts'][0]
    host_home_path = os.path.join(home_path, host)
    file_path = os.path.join(host_home_path, 'test')
    os.makedirs(host_home_path, exist_ok=True)
    with open(file_path, 'w') as f:
        f.close()

    pool.exec_on_host(host, ["rm -rf %s/test" % local_config['environment']['home']])
    assert not os.path.exists(file_path)


def test_local_pool_exec_on_host_rm_files_by_mask(local_config):
    pool = LocalPool(local_config['ssh'])
    home_path = local_config['environment']['home']
    host = local_config['ssh']['hosts'][0]
    host_home_path = os.path.join(home_path, host)
    file1_path = os.path.join(host_home_path, 'test')
    file2_path = os.path.join(host_home_path, 'test')
    os.makedirs(host_home_path, exist_ok=True)
    with open(file1_path, 'w') as f:
        f.close()
    with open(file2_path, 'w') as f:
        f.close()

    pool.exec_on_host(host, ["rm -rf %s/*" % local_config['environment']['home']])
    assert not os.path.exists(file1_path)
    assert not os.path.exists(file2_path)

