import pytest

from tiden.utilities import BaseUtility
from tiden.tidenexception import TidenException


@pytest.fixture()
def base_util():
    class MockIgnite:
        name = "ignite"
    yield BaseUtility(MockIgnite())


def test_simple_positive(base_util):
    buff = "hola!\nhello!\nhi!"
    lines_to_search = ["hello"]
    assert base_util.check_content_all_required(buff, lines_to_search)


def test_simple_negative(base_util):
    with pytest.raises(TidenException):
        buff = "hola!\nhello!\nhi!"
        lines_to_search = ["ni hao!"]
        base_util.check_content_all_required(buff, lines_to_search)


def test_multiple_lines(base_util):
    buff = "hola!\nhello!\nhi!"
    lines_to_search = ["hi!", "hola!"]
    assert base_util.check_content_all_required(buff, lines_to_search)


def test_repeated_line_positive(base_util):
    buff = "hola!\nhi!hello!\nhi!"
    lines_to_search = ["hi!", "hi!"]
    base_util.check_content_all_required(buff, lines_to_search)


def test_repeated_line_negative(base_util):
    with pytest.raises(TidenException):
        buff = "hola!\nhello!\nhi!"
        lines_to_search = ["hi!", "hi!"]
        base_util.check_content_all_required(buff, lines_to_search)


def test_multiple_lines_negative(base_util):
    with pytest.raises(TidenException):
        buff = "hola!\nhello!\nhi!"
        lines_to_search = ["hola!", "ni hao!"]
        base_util.check_content_all_required(buff, lines_to_search)


def test_spaces_negative(base_util):
    with pytest.raises(TidenException):
        buff = "hola!\nhello!\nhi!"
        lines_to_search = [" hi!\n"]
        base_util.check_content_all_required(buff, lines_to_search)


def test_several_matches_not_allowed(base_util):
    with pytest.raises(TidenException):
        buff = "hello\nhello\nhi"
        lines_to_search = ["hello"]
        base_util.check_content_all_required(buff, lines_to_search)


def test_several_matches_allowed(base_util):
    buff = "Control utility\nConflict partition: 123\nConflict partition: 234\nExecution time: XXX"
    lines_to_search = ["Conflict partition"]
    assert base_util.check_content_all_required(buff, lines_to_search, match_once_or_more=True)


def test_maintain_order(base_util):
    buff = "hi\nhello\nni hao"
    lines_to_search = ["hi", "ni hao"]
    assert base_util.check_content_all_required(buff, lines_to_search, maintain_order=True)


def test_maintain_order_neg(base_util):
    with pytest.raises(TidenException):
        buff = "hi\nhello\nni hao"
        lines_to_search = ["ni hao", "hi"]
        assert base_util.check_content_all_required(buff, lines_to_search, maintain_order=True)


def test_escape(base_util):
    buff = "hi\nhi and hello\nni hao"
    lines_to_search = ["hi"]
    filter_lines = ["hello"]
    assert base_util.check_content_all_required(buff, lines_to_search, escape=filter_lines)


def test_escape_neg(base_util):
    with pytest.raises(TidenException):
        buff = "hi\nhi and hello\nni hao"
        lines_to_search = ["hello"]
        filter_lines = ["hi"]
        base_util.check_content_all_required(buff, lines_to_search, escape=filter_lines)
