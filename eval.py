from spec import ExecuteElement


class Move:
    def __init__(self, **kwargs):
        self.args = args


class Stay:
    def __init__(self, reason: str):
        self.reason = reason


def eval_code(execution: ExecuteElement, data: dict):
    lang = execution.language.lower()
    if lang == "python":
        return eval_python(execution.code, data)
    else:
        raise ValueError(f"Unknown language: {lang}")


def eval_python(code: str, data: dict):
    # insert a "\t" at the beginning of all lines of code
    code = "\t" + code.replace("\n", "\n\t")
    params = ", ".join(data.keys())
    code = f"""
def _eval({params}):
{code}

globals()['chatbot_llm_action_result_'] = _eval({params})
    """

    compiled = compile(code, "<string>", "exec")
    global_vars = globals().copy()
    eval(compiled, global_vars, data.copy())
    result = global_vars["chatbot_llm_action_result_"]
    return result
