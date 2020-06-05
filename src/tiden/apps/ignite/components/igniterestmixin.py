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

from copy import deepcopy
from re import search

from .ignitelogdatamixin import IgniteLogDataMixin
from ....util import json_request, deprecated, log_print, json_request_with_errors
from ....tidenexception import TidenException


class IgniteRESTMixin(IgniteLogDataMixin):
    """
    Provides useful wrappers over Ignite HTTP REST protocol
    """
    auth_creds = {}

    def __init__(self, *args, **kwargs):
        # print('IgniteRESTMixin.__init__')
        super(IgniteRESTMixin, self).__init__(*args, **kwargs)

        # used by get_xxx method via REST
        self.auth_creds = {}

        self.add_node_data_log_parsing_mask(
            name='REST',
            node_data_key='rest_port',
            remote_regex='\[GridJettyRestProtocol\] Command protocol successfully started',
            local_regex='port=([0-9]+)\]',
            force_type='int',
        )

    def enable_authentication(self, login, password):
        """
        Use provided credentials for REST authentication
        :param login:
        :param password:
        :return:
        """
        self.auth_creds = {
            'authentication_enabled': True,
            'auth_login': login,
            'auth_password': password,
        }

    def disable_authentication(self):
        """
        Use non-authenticated REST access
        :return:
        """
        self.auth_creds = {}

    def get_auth_creds(self):
        return self.auth_creds

    def build_rest_url(self, node_id=None, **kwargs):
        """
        Build HTTP REST URL to access cluster via either specific or first alive node
        :param node_id:
        :param kwargs: REST command arguments
        :return:
        """
        if node_id is not None and node_id in self.nodes.keys() and 'rest_port' in self.nodes[node_id].keys():
            node_ids = [node_id]
        else:
            node_ids = self.get_alive_default_nodes() + self.get_alive_additional_nodes()

        assert len(node_ids), "No alive nodes found in grid !"

        for node_id in node_ids:
            if 'host' in self.nodes[node_id] and 'rest_port' in self.nodes[node_id] and 'PID' in self.nodes[node_id]:
                node_ip = self.nodes[node_id]['host']
                rest_port = self.nodes[node_id]['rest_port']
                url = "http://%s:%s/ignite" % (node_ip, rest_port)
                url += "?" + "&".join([k + '=' + str(v) for k, v in kwargs.items()])
                return url
        raise TidenException('No alive server nodes found')

    def get_cache_names(self, cache_name_prefix='', node_id=None):
        cache_names = []
        json_data = json_request(self.build_rest_url(node_id, cmd='top', attr='true'), auth_creds=self.get_auth_creds())
        if int(json_data['successStatus']) == 0:
            for cache_data in json_data['response'][0]['caches']:
                if cache_name_prefix == '' or cache_data['name'].startswith(cache_name_prefix):
                    cache_names.append(cache_data['name'])

        return cache_names

    @deprecated
    def get_node_info(self, node_idx=None):
        result = {}
        json_data = json_request(self.build_rest_url(node_idx, cmd='node', attr='true'), auth_creds=self.get_auth_creds())
        if int(json_data['successStatus']) == 0:
            for node in json_data['response']:
                m = search('^node_([^_]+)_([0-9]{1,5})$', node['consistentId'])
                if m:
                    node_id = int(m.group(2))
                    if node_idx is None or node_idx == node_id:
                        result[node_id] = deepcopy(node)
        return result

    # @deprecated
    def get_entries_num(self, cache_names, log=False):
        current_size = 0
        for cache_name in cache_names:
            # Get cache size for given cache name
            json_data = json_request(self.build_rest_url(cmd='size', cacheName=cache_name),
                                     auth_creds=self.get_auth_creds())
            if int(json_data['successStatus']) == 0:
                current_size += int(json_data['response'])
            self.logger.debug(json_data)
        if log:
            log_print("Found %s entries in %s cache(s)" % (current_size, len(cache_names)))
        return current_size

    def log_cache_entries(self, cache_prefix='cache_'):
        cache_names = self.get_cache_names(cache_prefix)
        entry_num = self.get_entries_num(cache_names)
        log_print("Found %s entries in %s cache(s)" % (entry_num, len(cache_names)), 2)

    def get_alive_node_ids(self):
        result = {}
        json_data = json_request(self.build_rest_url(cmd='top', attr='true'), auth_creds=self.get_auth_creds())
        if int(json_data['successStatus']) == 0:
            for node in json_data['response']:
                m = search('^node_([^_]+)_([0-9]{1,5})$', node['consistentId'])
                if m:
                    node_id = int(m.group(2))
                    node_id8 = node['nodeId']
                    result[node_id] = node_id8.upper()
        return result

    def get_nodes_num(self, node_type):
        result = {
            'client': 0,
            'server': 0,
            'all': 0,
        }

        alive_nodes = self.get_all_default_nodes() + self.get_alive_additional_nodes()
        for node_id in alive_nodes:
            try:
                url = self.build_rest_url(node_id, cmd='top', attr='true')
                json_data = json_request_with_errors(url, auth_creds=self.get_auth_creds())
            except Exception:
                log_print('REST URL %s is unreachable for node %s. Skipping' % (url, node_id), color='red')
                continue

            if int(json_data['successStatus']) == 0:
                for node in json_data['response']:
                    m = search('^node_([^_]+)_([0-9]{1,5})$', node['consistentId'])
                    if m:
                        node_id = int(m.group(2))
                        result['all'] += 1
                        if self.is_default_node(node_id) or self.is_additional_node(node_id):
                            result['server'] += 1
                result['client'] = result['all'] - result['server']
                return result[node_type]

