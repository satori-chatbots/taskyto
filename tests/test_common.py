from engine.common import replace_values


def test_replace_values():
    assert replace_values("{{test}}", {"test": "a test value"}) == "a test value"
    assert replace_values("{test}", {"test": "a test value"}) == "a test value"

    multiline = "This is a {{test}}\nAnd this is a {test}"
    assert replace_values(multiline, {"test": "test value"}) == "This is a test value\nAnd this is a test value"