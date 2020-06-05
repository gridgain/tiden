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

from .util import *
from .tidenexception import TidenException

import time
from datetime import datetime
from requests import post
from json import dumps, loads


class ZabbixApiException(TidenException):
    pass


class ZabbixApi():
    zapi = None
    auth_key = None
    logger = get_logger('tiden')
    logger.set_suite('[ZabbixApi]')

    def __init__(self, url, login, passwd):
        self.url = '%s/api_jsonrpc.php' % url
        self.login = login
        self.passwd = passwd
        # just to fail fast make login request here
        request = {
            'req_type': 'user.login',
            'req_body': {
                "user": self.login,
                "password": self.passwd
            }
        }
        self.auth_key = self.get_request(request)

    def collect_metrics_from_servers(self, servers, metrics, start_time, stop_time=None):
        host_ids = self.get_hosts(servers)
        data = {}

        for metric_name in metrics:
            for host, host_id in host_ids:
                self.logger.debug('%s %s' % (host, host_id))
                metric_id, value_type = self.get_metric_id_by_description(host_id, metric_name)
                self.logger.debug('Metric_id = %s' % metric_id)
                m_history = self.get_cpu_metrics_history(
                    metric_id, value_type,
                    time_from=start_time, time_till=stop_time)
                if data.get(metric_name):
                    data[metric_name].update({host: m_history})
                else:
                    data[metric_name] = {host: m_history}

        return data

    def get_hosts(self, servers):
        host_names = ['lab%s' % id.split('.')[-1] for id in servers]
        hostid_name = []

        request = {
            'req_type': 'host.get',
            'req_body': {'monitored_hosts': '1', 'output': ['hostid', 'name']}
        }

        results = self.get_request(request)
        for result in results:
            if result.get('name') in host_names:
                hostid_name.append((result.get('name'), result.get('hostid')))

        return hostid_name

    def get_all_metric(self, host_id, metric_pattern):
        metric_id, value_type = None, None
        request = {
            'req_type': 'item.get',
            'req_body': {'hostids': [host_id], 'search': metric_pattern}
        }
        result = self.get_request(request)
        self.logger.debug('get_all_metric result is: \n%s' % result)

        if len(result) == 1 and result[0].get('itemid'):
            metric_id = result[0].get('itemid')
            value_type = result[0].get('value_type')

        return metric_id, value_type

    def get_metric_id_by_description(self, host_id, metric_name):
        metric_id, value_type = None, None

        request = {
            'req_type': 'item.get',
            'req_body': {'hostids': [host_id], 'search': {'description': metric_name}}
        }
        result = self.get_request(request)
        self.logger.debug('get_metric_id result is: \n%s' % result)

        if len(result) == 1 and result[0].get('itemid'):
            metric_id = result[0].get('itemid')
            value_type = result[0].get('value_type')

        return metric_id, value_type

    def get_mem_metrics_history(self, metric_id, time_from, time_till=None):
        m_history = {}
        time_from_timestamp = self.util_get_time(time_from.timetuple())
        time_till_timestamp = self.util_get_time(datetime.now().timetuple())

        if time_till:
            time_till_timestamp = time.mktime(time_till)

        request = {
            'req_type': 'history.get',
            'req_body': {
                'history': 0,
                'itemids': metric_id,
                'time_from': time_from_timestamp,
                'time_till': time_till_timestamp
            }
        }
        results = self.get_request(request)
        self.logger.debug('get_mem_metrics_history result is: \n%s' % results)

        if len(results) > 0:
            for result in results:
                if result.get('clock') and result.get('value'):
                    m_history = self._append_dict(m_history, 'timestamp',
                                                  datetime.fromtimestamp(int(result['clock'])).
                                                  strftime('%Y-%m-%d %H:%M:%S'))
                    m_history = self._append_dict(m_history, 'values', int(result['value']))
        self.logger.debug('history is: \n%s' % m_history)

        return m_history

    def get_cpu_metrics_history(self, metric_id, value_type, time_from, time_till=None):
        m_history = {}
        time_from_timestamp = self.util_get_time(time_from.timetuple())
        time_till_timestamp = self.util_get_time(datetime.now().timetuple())

        if time_till:
            time_till_timestamp = int(time.mktime(time_till.timetuple()))

        request = {
            'req_type': 'history.get',
            'req_body': {
                'history': value_type,
                'itemids': metric_id,
                'time_from': time_from_timestamp,
                'time_till': time_till_timestamp
            }
        }
        results = self.get_request(request)
        self.logger.debug('get_cpu_metrics_history result is: \n%s' % results)

        if len(results) > 0:
            for result in results:
                if result.get('clock') and result.get('value'):
                    m_history = self._append_dict(m_history, 'timestamp',
                                                  datetime.fromtimestamp(int(result['clock'])).
                                                  strftime('%Y-%m-%d %H:%M:%S'))
                    m_history = self._append_dict(m_history, 'values', float(result['value']))
        self.logger.debug('history is: \n%s' % m_history)

        return m_history

    @staticmethod
    def _append_dict(ext_dict, key, value):
        if ext_dict.get(key):
            ext_dict[key].append(value)
        else:
            ext_dict[key] = [value]
        return ext_dict

    def get_request(self, request):
        result = []

        self.logger.debug(request)
        response = self.do_request(request['req_type'], request['req_body'])
        self.logger.debug(response)

        if response.get('result'):
            result = response.get('result')

        return result

    def do_request(self, method, params=None):
        """
        Do request to Zabbix.

        :param method: ZabbixAPI method, like: `item.get`.
        :param params: ZabbixAPI method arguments.

        """
        request_json = {
            'jsonrpc': '2.0',
            'method': method,
            'params': params or {},
            'id': '1',
        }

        if self.auth_key and method not in ['user.login']:
            request_json['auth'] = self.auth_key

        res = post(
            self.url,
            dumps(request_json),
            headers={'Content-Type': 'application/json-rpc'}
        )

        self.logger.debug(res)

        try:
            res_json = loads(res.text)
        except ValueError as e:
            raise ZabbixApiException("Cannot parse response: %s" % e)

        if 'error' in res_json:
            err = res_json['error']
            raise ZabbixApiException({'message': 'Got error:\n %s\n for request:\n%s' % (err, request_json),
                                      'reason': err.get('data')})

        return res_json

    @staticmethod
    def util_get_time(time_timetuple):
        return int(time.mktime(time_timetuple))

