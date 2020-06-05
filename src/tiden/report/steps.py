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

import inspect
from copy import deepcopy
from datetime import datetime
from enum import Enum
from inspect import getfullargspec
from os.path import exists, basename
from re import sub
from time import time
from traceback import format_exc
from uuid import uuid4

from requests import post

from ..util import log_print


def test_name(name):
    def wrap(fn):
        fn.__report_title__ = name
        return fn
    return wrap


def suites(suites_path: list):
    def wrap(fn):
        fn.__report_suites__ = suites_path
        return fn
    return wrap


class InnerReportConfig:

    def __init__(self):
        self.steps = []
        self.title = None
        self.suites: list = []

    def append_steps(self, steps):
        self.steps.append(steps)

    def _pretty_datetime(self, time):
        return datetime.fromtimestamp(time).isoformat().replace('T', ' ')

    def _start_step(self, steps, name, parameters):
        new_steps = []
        step_id = None
        for step_item in deepcopy(steps):
            if step_item['status'] is None:
                step_item['children'], step_id  = self._start_step(step_item.get('children', []), name, parameters)
            new_steps.append(step_item)
        if step_id is None:
            step_id = str(uuid4())
            new_steps.append({
                'name': name,
                'time': {
                    'start': round(time() * 1000),
                    'start_pretty': self._pretty_datetime(time()),
                },
                'stacktrace': None,
                'status': None,
                'step_id': step_id,
                **({'parameters': parameters} if parameters else {})
            })
        return new_steps, step_id

    def start_step(self, name, parameters):
        self.steps, step_id = self._start_step(self.steps, name, parameters)
        return step_id

    def add_attachment(self, attachment):
        self.steps, _ = self.__add_attachment(self.steps, attachment)

    def __add_attachment(self, steps, attachment):
        new_steps = []
        added = False
        for step_item in deepcopy(steps):
            if step_item['status'] is None:
                if step_item.get('children') and not added:
                    step_item['children'], added = self.__add_attachment(step_item['children'], attachment)
                if not added:
                    step_item['attachments'] = step_item.get('attachments', []) + [attachment]
                    added = True
            new_steps.append(step_item)
        return new_steps, added

    def _end_step(self, steps, step_id, status, stacktrace):
        new_steps = []
        for step_item in deepcopy(steps):
            if step_item.get('step_id') != step_id:
                if step_item.get('children'):
                    step_item['children'] = self._end_step(step_item['children'], step_id, status, stacktrace)
            else:
                step_item['status'] = status
                step_item['time']['end'] = round(time() * 1000)
                step_item['time']['end_pretty'] = self._pretty_datetime(time())
                step_item['time']['diff'] = self._make_pretty_diff(
                    step_item['time']['start'],
                    step_item['time']['end']
                )
                step_item['stacktrace'] = stacktrace
                del step_item['step_id']
            new_steps.append(step_item)
        return new_steps

    def end_step(self, step_id, status, stacktrace):
        self.steps = self._end_step(self.steps, step_id, status, stacktrace)

    def _make_pretty_diff(self, start, end):
        diff = round((end - start)/1000)
        if diff > 60:
            minutes = diff // 60
            pretty_diff = f'{diff // 60}m {diff - minutes * 60}s'
        else:
            pretty_diff = f'{diff}s'
        return pretty_diff


class Step:
    def __init__(self, cls, name, parameters=None, **kwargs):
        self.name = name
        self.cls = cls
        self.report_exist = bool(getattr(self.cls, '_secret_report_storage', None))
        self.kwargs = kwargs
        self.parameters = parameters or []
        self.unique = None
        self.status = None
        self.stacktrace = ""

    def __enter__(self):
        if getattr(self.cls, 'config', False) and 'WardReport' in self.cls.config.get('plugins', []):
            log_print(f'Step {self.name} started', color='debug')
        if self.report_exist:
            report: InnerReportConfig = getattr(self.cls, '_secret_report_storage', None)
            self.unique = report.start_step(self.name, self.parameters)
            setattr(self.cls, '_secret_report_storage', report)
        return self

    def failed(self, stacktrace=""):
        self.stacktrace = stacktrace
        self.status = False

    def __exit__(self, exc_type, exc_val, exc_tb):
        if getattr(self.cls, 'config', False) and 'WardReport' in self.cls.config.get('plugins', []):
            log_print(f'Step {self.name} ended', color='debug')
        if self.report_exist:
            report: InnerReportConfig = getattr(self.cls, '_secret_report_storage', None)
            step_result = exc_type is None if self.status is None else self.status
            report.end_step(self.unique, 'passed' if step_result else 'failed',
                            self.stacktrace[:5000] if self.status is not None else format_exc()[:5000])
            setattr(self.cls, '_secret_report_storage', report)
        if exc_type is not None:
            raise exc_val


class AttachmentType(Enum):
    TEXT = 'text/plain'
    JSON = 'text/json'
    FILE = 'file'


def add_attachment(cls, name, data, attachment_type: AttachmentType = AttachmentType.TEXT):
    if exists(data):
        if 'WardReport' in cls.config.get('plugins', []):
            report_config = cls.config['plugins']['WardReport']
            files_receiver_url = report_config['files_url']
            upload_logs = report_config['upload_logs']
            filename = f'{uuid4()}-{basename(data)}'
            if upload_logs:
                post(f'{files_receiver_url}/files/add',
                     files={'file': open(data, 'rb')},
                     headers={'filename': filename})
            data = filename
    attachment = {
        'name': name,
        'source': data,
        'type': attachment_type.value
    }
    report: InnerReportConfig
    if getattr(cls, '_secret_report_storage', None):
        report = getattr(cls, '_secret_report_storage', None)
        report.add_attachment(attachment)
        setattr(cls, '_secret_report_storage', report)
    elif getattr(cls, '_parent_cls', None) and getattr(getattr(cls, '_parent_cls'), '_secret_report_storage', None):
        report = getattr(getattr(cls, '_parent_cls'), '_secret_report_storage', None)
        report.add_attachment(attachment)
        parent_cls = getattr(cls, '_parent_cls')
        setattr(parent_cls, '_secret_report_storage', report)
        setattr(cls, '_parent_cls', parent_cls)


def step(name=None, attach_parameters=False, expected_exceptions: list = None):
    def inner(fn):
        def _inner(*args, **kwargs):
            report: InnerReportConfig = None
            step_id = None
            step_passed = True
            stacktrace = ''
            if name:
                step_name = get_params(name, args, kwargs, fn)
            else:
                step_name = sub('_+', ' ', fn.__name__)
            parameters = []
            if attach_parameters:
                if args:
                    func_args = inspect.getfullargspec(fn)[0]
                    first_key = 1 if 'self' in func_args else 0
                    for i, arg in enumerate(args[first_key:]):
                        parameters.append({'name': f'args.{i}', 'value': str(arg)})
                if len(kwargs) > 0:
                    for kw, kwarg_value in kwargs.items():
                        parameters.append({'name': str(kw), 'value': str(kwarg_value)})
            step_name = f'{step_name[:1].upper()}{step_name[1:]}'
            if args:
                if getattr(args[0], '_secret_report_storage', None):
                    report = getattr(args[0], '_secret_report_storage', None)
                    step_id = report.start_step(step_name, parameters)
                    setattr(args[0], '_secret_report_storage', report)
                elif getattr(args[0], '_parent_cls', None) and getattr(getattr(args[0], '_parent_cls'), '_secret_report_storage', None):
                    report = getattr(getattr(args[0], '_parent_cls'), '_secret_report_storage', None)
                    step_id = report.start_step(step_name, parameters)
                    parent_cls = getattr(args[0], '_parent_cls')
                    setattr(parent_cls, '_secret_report_storage', report)
                    setattr(args[0], '_parent_cls', parent_cls)
            try:
                result = fn(*args, **kwargs)
            except Exception as e:
                stacktrace = format_exc()[:5000]
                step_passed = False
                if expected_exceptions:
                    this_is_expected_exception = False
                    for expected_exception in expected_exceptions:
                        if isinstance(e, expected_exception):
                            this_is_expected_exception = True
                    step_passed = this_is_expected_exception
                raise
            finally:
                if report is not None:
                    if getattr(args[0], '_secret_report_storage', None):
                        report = getattr(args[0], '_secret_report_storage', None)
                        report.end_step(step_id, 'passed' if step_passed else 'failed', stacktrace)
                        setattr(args[0], '_secret_report_storage', report)
                    elif getattr(args[0], '_parent_cls', None) and getattr(getattr(args[0], '_parent_cls'), '_secret_report_storage', None):
                        report = getattr(getattr(args[0], '_parent_cls'), '_secret_report_storage', None)
                        report.end_step(step_id, 'passed' if step_passed else 'failed', stacktrace)
                        parent_cls = getattr(args[0], '_parent_cls')
                        setattr(parent_cls, '_secret_report_storage', report)
                        setattr(args[0], '_parent_cls', parent_cls)
            return result
        return _inner
    return inner


def get_params(base, args, kwargs, fn):
    """
    Format string for step name with method args/kwargs/class params
    In additional {*args} argument can be used in step name. It will include all function args to output
    example:
        @step('Run control_utility, command keys - "{*args}"') ->
                                                    Step Run control_utility, command keys - "--baseline" started
    :param base:        not formatted string
    :param args:        args without definition
    :param kwargs:      function kwargs
    :param fn:          function
    :return:            formatted string
    """

    def get_string_args(base):
        """
        Getting {args} from string

        :param base:    base string
        :return:        list of args
            """
        result = []
        base_name = base
        count = 0

        while count < 20 and "{" in base_name:
            count += 1

            # taking first param with brackets
            start_index = base_name.index("{")
            end_index = base_name.index("}")
            item = base_name[start_index + 1:end_index]

            result.append(item)

            # cut string until last found index
            base_name = base_name[end_index + 1:]
        return result

    if '{' in base:
        format_params = {}

        # get all params from string
        name_args = get_string_args(base)

        # get function args info
        func_args = getfullargspec(fn)[0]
        is_class = 'self' in func_args
        for name_arg in name_args:

            # going through non named args
            start_index = 0
            if is_class:
                start_index = 1
            found = False
            for idx, func_arg in enumerate(func_args[start_index:], start=start_index):
                if name_arg == func_arg:
                    if idx >= len(args):
                        format_params[name_arg] = kwargs.get(func_arg)
                    else:
                        format_params[name_arg] = args[idx]
                    found = True
                    break
            if found:
                continue

            if format_params.get(name_arg):
                continue

            # kwargs
            if name_arg in kwargs.keys():
                if '.' in name_arg:
                    temp_value = kwargs
                    for name_part in name_arg.split('.'):
                        temp_value = temp_value.get(name_part)
                    format_params[name_arg.split('.')[0]] = temp_value
                else:
                    format_params[name_arg] = kwargs[name_arg]
                continue

            if is_class:
                # class params
                value_from_func = getattr(args[0], name_arg.split('.')[0] if '.' in name_arg else name_arg, None)
                if value_from_func is not None:
                    if '.' in name_arg:
                        temp_value = value_from_func
                        for name_part in name_arg.split('.'):
                            temp_value = temp_value.get(name_part)
                        format_params[name_arg.split('.')[0]] = temp_value
                    else:
                        format_params[name_arg] = value_from_func
                    continue

            if name_arg == '*args':
                format_params[name_arg] = ' '.join(args[start_index:])
                continue

            raise RuntimeError("Can't find {} for @step on {} function".format(name_arg, fn.__name__))

        return base.format(**format_params)
    else:
        return base

