from engine.common.evaluator import Evaluator
from spec import ExecuteElement

evaluator = Evaluator()

def test_simple_return_value():
    code = """
print('Hi, I am a test!')
return True"""
    r = evaluator.eval_code(ExecuteElement(language="python", code=code), {})
    assert r is True


def test_use_args_and_return_value():
    code = """
return number + 10"""
    r = evaluator.eval_code(ExecuteElement(language="python", code=code), {"number": 1})
    assert r is 11


#def test_use_api_to_return_values():
#    code = """
#return Stay('Because this is a test')"""
#    r = evaluator.eval_code(ExecuteElement(language="python", code=code), {})
#    assert isinstance(r, Stay)
#    assert r.reason == 'Because this is a test'
