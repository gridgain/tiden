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

from ...nodestatus import NodeStatus
from .ignitemixin import IgniteMixin
from ....tidenexception import TidenException
from ....util import encode_enums, write_yaml_file, log_print, read_yaml_file, decode_enums


class IgniteStaticInitMixin(IgniteMixin):
    """
    Encapsulates 'static' Ignite initialization from previously dumped configuration file.
    """
    nodes_config_path = None
    nodes_config_name = 'nodes-config.yaml'
    nodes_config_store_host = None
    is_static_inited = False

    def __init__(self, *args, **kwargs):
        # print('IgniteStaticInitMixin.__init__')
        super(IgniteStaticInitMixin, self).__init__(*args, **kwargs)

        # used by static dump_nodes_config/restore_nodes_config
        self.nodes_config_path = None
        self.nodes_config_name = 'nodes-config.yaml'
        self.nodes_config_store_host = None
        self.is_static_inited = False

        self._parse_static_init_params(kwargs)

    def on_setup(self):
        # TODO:
        pass

    def _parse_static_init_params(self, kwargs):
        """
        Parse kwargs with static nodes config params for dump or restore
        """
        self.nodes_config_path = kwargs.get('nodes_config_path',
                                            self.config.get('environment', {}).get("nodes_config_path", self.nodes_config_path))

        self.nodes_config_name = kwargs.get('nodes_config_name',
                                            self.config.get('environment', {}).get("nodes_config_name",
                                                                           self.nodes_config_name))
        self.nodes_config_store_host = kwargs.get('nodes_config_store_host',
                                                  self.config.get('environment', {}).get("nodes_config_store_host",
                                                                                 self.nodes_config_store_host))
        self.is_static_inited = kwargs.get('static_init', False)

    def dump_nodes_config(self, strict=True, **kwargs):
        """
        Write nodes config in yaml file and upload on selected node for storing
        """
        if kwargs:
            self._parse_static_init_params(kwargs)
        if self.nodes_config_path is None:
            if strict:
                raise TidenException("Can't backup nodes config without nodes_config_path")
            else:
                return

        nodes_config = encode_enums(self.nodes)
        config_local_path = "{}/{}".format(self.config["tmp_dir"], self.nodes_config_name)
        write_yaml_file(config_local_path, nodes_config)

        if self.nodes_config_store_host is None:
            self.nodes_config_store_host = self.nodes[min(self.nodes.keys())]['host']

        remote_path = '{}/{}'.format(self.nodes_config_path, self.nodes_config_name)
        log_print("Dump nodes config on host '{}' to '{}'".format(remote_path, self.nodes_config_store_host))

        self.ssh.upload_on_host(self.nodes_config_store_host, [config_local_path], self.nodes_config_path)

        cmd = "chmod 777 {}".format(remote_path)
        self.ssh.exec_on_host(self.nodes_config_store_host, [cmd])

    def restore_nodes_config(self, **kwargs):
        """
        Download nodes config yaml file from storing place and parse into self.nodes
        """
        if kwargs:
            self._parse_static_init_params(kwargs)
        if self.nodes_config_path is None:
            raise TidenException("Can't restore nodes config without nodes_config_path")

        config_local_path = "{}/{}".format(self.config["tmp_dir"], self.nodes_config_name)
        config_remote_path = "{}/{}".format(self.nodes_config_path, self.nodes_config_name)

        log_print(
            "Restore nodes config from host '{}' path '{}'".format(config_remote_path, self.nodes_config_store_host))
        self.ssh.download_from_host(self.nodes_config_store_host, config_remote_path, config_local_path)

        configs = read_yaml_file(config_local_path)
        self.nodes = decode_enums(configs, available_enums=[NodeStatus])

