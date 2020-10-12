import pytest

from tiden.utilities import BaseUtility
from tiden.tidenexception import TidenException


class MockIgnite:
    name = "ignite"


def test_simple_positive():
    util = BaseUtility(MockIgnite())
    buff = "hola!\nhello!\nhi!"
    lines_to_search = ["hello"]
    assert util.check_content_all_required(buff, lines_to_search)


def test_simple_negative():
    with pytest.raises(TidenException):
        util = BaseUtility(MockIgnite())
        buff = "hola!\nhello!\nhi!"
        lines_to_search = ["ni hao!"]
        util.check_content_all_required(buff, lines_to_search)


def test_partial_match():
    util = BaseUtility(MockIgnite())
    buff = "hola!\nhello!\nhi!"
    lines_to_search = ["hell"]
    assert util.check_content_all_required(buff, lines_to_search)


def test_multiple_lines():
    util = BaseUtility(MockIgnite())
    buff = "hola!\nhello!\nhi!"
    lines_to_search = ["hi!", "hola!"]
    assert util.check_content_all_required(buff, lines_to_search)


def test_repeated_line():
    util = BaseUtility(MockIgnite())
    buff = "hola!\nhello!\nhi!"
    lines_to_search = ["hi!", "hi!"]
    assert util.check_content_all_required(buff, lines_to_search)


def test_multiple_lines_negative():
    with pytest.raises(TidenException):
        util = BaseUtility(MockIgnite())
        buff = "hola!\nhello!\nhi!"
        lines_to_search = ["hola!", "ni hao!"]
        util.check_content_all_required(buff, lines_to_search)


def test_spaces_negative():
    with pytest.raises(TidenException):
        util = BaseUtility(MockIgnite())
        buff = "hola!\nhello!\nhi!"
        lines_to_search = [" hi!\n"]
        util.check_content_all_required(buff, lines_to_search)
