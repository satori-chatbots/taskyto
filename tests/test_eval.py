import base_test
from eval import eval_python, Stay


def test_simple_return_value():
    code = """
print('Hi, I am a test!')
return True"""
    r = eval_python(code, {})
    assert r is True


def test_use_args_and_return_value():
    code = """
return number + 10"""
    r = eval_python(code, {"number": 1})
    assert r is 11


def test_use_api_to_return_values():
    code = """
return Stay('Because this is a test')"""
    r = eval_python(code, {})
    assert isinstance(r, Stay)
    assert r.reason == 'Because this is a test'
