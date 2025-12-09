from proxy.tools import extract_tool_calls_from_text


TOOLS = [
    {"type": "function", "function": {"name": "read_file"}},
    {"type": "function", "function": {"name": "write_file"}},
    {"type": "function", "function": {"name": "search"}},
]


def test_parse_write_file_tag():
    text = "<write_file><path>/tmp/a.txt</path><content>Hello</content></write_file>"
    calls, remaining = extract_tool_calls_from_text(text, TOOLS)
    assert remaining == ""
    assert calls[0]["function"]["name"] == "write_file"
    args = calls[0]["function"]["arguments"]
    assert '"uri": "/tmp/a.txt"' in args
    assert '"contents": "Hello"' in args


def test_parse_search_tag():
    text = "<search><query>find me</query></search>"
    calls, remaining = extract_tool_calls_from_text(text, TOOLS)
    assert remaining == ""
    assert calls[0]["function"]["name"] == "search"
    args = calls[0]["function"]["arguments"]
    assert '"query": "find me"' in args


def test_parse_read_file_tag():
    text = "<read_file><path>/tmp/a.txt</path></read_file>"
    calls, remaining = extract_tool_calls_from_text(text, TOOLS)
    assert remaining == ""
    assert calls[0]["function"]["name"] == "read_file"
    args = calls[0]["function"]["arguments"]
    assert '"uri": "/tmp/a.txt"' in args
