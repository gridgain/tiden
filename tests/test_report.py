from time import time

import pytest

from tiden.report.steps import _change_report_storage, InnerReportConfig, step, Step


def test_embedded_storage_change():
    class A:
        pass

    class B:
        pass

    class C:
        pass

    a = A()
    b = B()
    c = C()

    class Secret:

        def __init__(self):
            self.storage = {}

        def change(self, key, value):
            self.storage[key] = value

    s = Secret()
    setattr(a, '_secret_report_storage', s)
    setattr(b, '_parent_cls', a)
    setattr(c, '_parent_cls', b)

    _change_report_storage(c, lambda secret: secret.change('a', 1))

    assert c._parent_cls._parent_cls._secret_report_storage.storage.get('a') == 1, 'failed to get secret storage'


def test_default_step():
    class A:
        _secret_report_storage = InnerReportConfig()

        @step('Some method name')
        def some_method(self):
            pass

    a = A()
    a.some_method()
    a.some_method()
    added_steps = a._secret_report_storage.steps
    assert len(added_steps) == 2
    actual_step = added_steps[0]
    assert actual_step['name'] == 'Some method name'
    assert isinstance(actual_step['time']['start'], int)
    assert time() - 10 < actual_step['time']['start'] <= round(time() * 1000)
    assert isinstance(actual_step['time']['end'], int)
    assert actual_step['time']['end'] <= round(time() * 1000)
    assert actual_step['time']['diff'] == '0s'
    assert actual_step['stacktrace'] == ''
    assert actual_step['status'] == 'passed'


def test_failed_step():
    class A:
        _secret_report_storage = InnerReportConfig()

        @step('Method should fail')
        def some_failed_method(self):
            raise Exception('Bad bad bad')

    a = A()
    with pytest.raises(Exception):
        a.some_failed_method()
    failed_step = a._secret_report_storage.steps[0]
    assert 'Exception: Bad bad bad' in failed_step['stacktrace']
    assert failed_step['status'] == 'failed'


def test_expected_exceptions():
    class A:
        _secret_report_storage = InnerReportConfig()

        @step('Method should fail', expected_exceptions=[AssertionError])
        def some_method(self):
            assert False
    a = A()
    with pytest.raises(AssertionError):
        a.some_method()
    failed_step = a._secret_report_storage.steps[0]
    assert failed_step['status'] == 'passed'


def test_attached_parameters():
    class A:
        _secret_report_storage = InnerReportConfig()

        @step('Some method again', attach_parameters=True)
        def some_method(self, arg1, arg2, kwarg1='Some value'):
            pass
    a = A()
    a.some_method('arg1 value', 'arg2 value', kwarg1='Different kwarg value')
    failed_step = a._secret_report_storage.steps[0]
    assert failed_step.get('parameters')
    assert failed_step['parameters'] == [
        {'name': 'args.0', 'value': 'arg1 value'},
        {'name': 'args.1', 'value': 'arg2 value'},
        {'name': 'kwarg1', 'value': 'Different kwarg value'},
    ]


def test_with_step_default():
    class A:
        _secret_report_storage = InnerReportConfig()
    a = A()
    with Step(a, 'Some step'):
        pass

    added_steps = a._secret_report_storage.steps
    assert len(added_steps) == 1
    actual_step = added_steps[0]
    assert actual_step['name'] == 'Some step'
    assert isinstance(actual_step['time']['start'], int)
    assert time() - 10 < actual_step['time']['start'] <= round(time() * 1000)
    assert isinstance(actual_step['time']['end'], int)
    assert actual_step['time']['end'] <= round(time() * 1000)
    assert actual_step['time']['diff'] == '0s'
    assert actual_step['stacktrace'] == ''
    assert actual_step['status'] == 'passed'


def test_with_step_failed():
    class A:
        _secret_report_storage = InnerReportConfig()
    a = A()

    with pytest.raises(AssertionError):
        with Step(a, 'Some failed step'):
            raise AssertionError('Bad bad bad')

    added_steps = a._secret_report_storage.steps
    actual_step = added_steps[0]
    assert actual_step['status'] == 'failed'
    assert 'AssertionError: Bad bad bad' in actual_step['stacktrace']


def test_with_step_params():
    class A:
        _secret_report_storage = InnerReportConfig()
    a = A()

    with Step(a, 'Some step', parameters=[{'name': 'arg', 'value': 'val'}]):
        pass

    added_steps = a._secret_report_storage.steps
    actual_step = added_steps[0]
    assert actual_step['parameters'] == [{'name': 'arg', 'value': 'val'}]


def test_with_step_expected_exceptions():
    class A:
        _secret_report_storage = InnerReportConfig()
    a = A()

    with pytest.raises(AssertionError):
        with Step(a, 'Some step', expected_exceptions=[AssertionError]):
            assert False

    added_steps = a._secret_report_storage.steps
    actual_step = added_steps[0]
    assert actual_step['status'] == 'passed'
    assert actual_step['stacktrace'] == ''


def test_step_name():
    class A:
        _secret_report_storage = InnerReportConfig()

        @step('Some method name {arg} {arg2} {named_kwarg}')
        def some_method(self, arg, arg2, named_kwarg=None):
            pass

    a = A()
    a.some_method(1, 2, named_kwarg='val')
    added_step = a._secret_report_storage.steps[0]
    assert added_step['name'] == 'Some method name 1 2 val'
