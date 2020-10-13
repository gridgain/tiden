import pytest

from tiden.utilities import BaseUtility
from tiden.tidenexception import TidenException


@pytest.fixture()
def base_util():
    class MockIgnite:
        name = "ignite"
    yield BaseUtility(MockIgnite())


positive_input = [
    # ("", ""),
    ('\n'.join(["hola!", "hello!", "hi!"]), "hello"),
    ('\n'.join(["hola!", "hello!", "hi!"]), ["hello"]),
    ('\n'.join(["hola!", "hello!", "hi!"]), ["hello!"]),
    ('\n'.join(["hello!", "hola!", "hello!", "hi!"]), ["hello!", "hello!"]),
    ('\n'.join(["hola!", "hello!", "hi!"]), ["hello", "hola!"]),
    ('\n'.join(["Conflict partition: X", "Execution time"]), ["Conflict partition"]),
    ('\n'.join([
        "-----------",
        "Command [LIST] successfully finished",
        "Exit code: 0"]
    ),
        ["Command \[LIST\] successfully finished", "-----------", "Exit code: 0"]),
    ('\n'.join([
        "List of snapshots:",
        "ID=1234567890, ..., TYPE=FULL, CLUSTER SIZE=Y, ....",
        "Number of full snapshots: 3",
        "Command [LIST] successfully finished in 0 seconds."
    ]),
        ["List of snapshots:", "ID=\d+, .* TYPE=FULL", "Command \[LIST\] successfully finished in \d+ seconds."]),
]
negative_input = [
    ('\n'.join(["hola!", "hello!", "hi!"]), ["ni hao!"]),
    ('\n'.join(["hola!", "hello!", "hi!", "hello"]), ["hello"]),
    ('\n'.join(["hola!", "hello!", "hi!"]), ["hello!", "hello!"]),
    ('\n'.join(["Conflict partition: X", "Conflict partition: Y", "Execution time"]), ["Conflict partition"]),
]

# match_once_or_more = True
positive_input_match_once_or_more = [
    ('\n'.join(["Conflict partition: X", "Conflict partition: Y", "Execution time"]), ["Conflict partition"]),
]
negative_input_match_once_or_more = [
    ('\n'.join(["Conflict partition: X", "Conflict partition: Y", "Execution time"]), ["Conflict partition", "Status"]),
]

# maintain_order = True
positive_input_maintain_order = [
    ('\n'.join(["hola!", "hello!", "hi!"]), ["hola", "hello"]),
    ('\n'.join(["hola!", "hello!", "hi!"]), ["hola", "hi"]),
    ('\n'.join(["hola!", "hello!", "hi!"]), ["hello"]),
]
negative_input_maintain_order = [
    ('\n'.join(["hola!", "hello!", "hi!"]), ["hello", "hola"]),
    ('\n'.join(["hola!", "hello!", "hi!"]), ["hi", "hello"]),
    ('\n'.join(["hola!", "hello!", "hi!"]), ["hello", "ni hao"]),
]

# escape = True
positive_input_escape = [
    ('\n'.join(["Conflict partition: X", "Conflict partition: YYY", "Execution time"]), ["Conflict partition"], ["YYY"]),
]
negative_input_escape = [
    ('\n'.join(["Conflict partition: YYY", "Execution time"]), ["Conflict partition"], ["YYY"]),
]


@pytest.mark.parametrize("buff,lines_to_search", positive_input)
def test_defaults_positive(base_util, buff, lines_to_search):
    assert base_util.check_content_all_required(buff, lines_to_search)


@pytest.mark.parametrize("buff,lines_to_search", negative_input)
def test_defaults_negative(base_util, buff, lines_to_search):
    with pytest.raises(TidenException):
        base_util.check_content_all_required(buff, lines_to_search)


@pytest.mark.parametrize("buff,lines_to_search", positive_input_match_once_or_more)
def test_match_once_or_more_positive(base_util, buff, lines_to_search):
    assert base_util.check_content_all_required(buff, lines_to_search, match_once_or_more=True)


@pytest.mark.parametrize("buff,lines_to_search", negative_input_match_once_or_more)
def test_match_once_or_more_negative(base_util, buff, lines_to_search):
    with pytest.raises(TidenException):
        base_util.check_content_all_required(buff, lines_to_search, match_once_or_more=True)


@pytest.mark.parametrize("buff,lines_to_search", positive_input_maintain_order)
def test_maintain_order_positive(base_util, buff, lines_to_search):
    assert base_util.check_content_all_required(buff, lines_to_search, maintain_order=True)


@pytest.mark.parametrize("buff,lines_to_search", negative_input_maintain_order)
def test_maintain_order_negative(base_util, buff, lines_to_search):
    with pytest.raises(TidenException):
        base_util.check_content_all_required(buff, lines_to_search, maintain_order=True)


@pytest.mark.parametrize("buff,lines_to_search,escape", positive_input_escape)
def test_escape_positive(base_util, buff, lines_to_search, escape):
    assert base_util.check_content_all_required(buff, lines_to_search, escape=escape)


@pytest.mark.parametrize("buff,lines_to_search,escape", negative_input_escape)
def test_escape_negative(base_util, buff, lines_to_search, escape):
    with pytest.raises(TidenException):
        base_util.check_content_all_required(buff, lines_to_search, escape=escape)
