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
