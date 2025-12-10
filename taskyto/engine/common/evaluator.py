import os
from typing import List

from taskyto.spec import ExecuteElement


def find_file(filename, load_path):
    # Find the list of folders given by load_path a file with the given filename
    # If the file is not found, return None
    for folder in load_path:
        full_path = os.path.join(folder, filename)
        if os.path.exists(full_path):
            return full_path
    raise ValueError(f"File {filename} not found in load path")



def eval_python_file(filename: str, data: dict):
    with open(filename) as f:
        code_to_execute = f.read()

        ####################
        # code_to_execute += f'\nimport sys\nsys.path.append("<path_to_your_modules>")\n'
        # code_to_execute += f'\nprint(f"__file__: {__file__}")\n'
        # code_to_execute += f'\nprint(f"globals: {str(globals().keys())}")\n'

        # pillar valor de "load_path"

        code_to_execute += f'\nimport sys\nsys.path.append(f"{os.path.dirname(os.path.dirname(globals().get("load_path")[0]))}")\n'
        code_to_execute += f'\nprint(f"{os.path.dirname(os.path.dirname(globals().get("load_path")[0]))}")\n'
        # code_to_execute += f'\nprint(f"globals: {str(globals().get("load_path"))}")\n'
        ####################
        code_to_execute += f'\nglobals()["chatbot_llm_action_result_"] = main({", ".join(data.keys())})\n'

        compiled = compile(code_to_execute, filename, "exec")
        global_vars = globals().copy()
        exec(compiled, global_vars, data.copy())
        result = global_vars["chatbot_llm_action_result_"]
        return result


def eval_python_inline(code: str, data: dict):
    # insert a "\t" at the beginning of all lines of code
    code = "\t" + code.replace("\n", "\n\t")
    params = ", ".join(data.keys())
    code = f"""
import sys
# Now auxiliar python files can also be imported from the taskyto script. We assume they belong to the same project
sys.path.append(f"{os.path.dirname(os.path.dirname(globals().get("load_path")[0]))}")
print(f"{os.path.dirname(os.path.dirname(globals().get("load_path")[0]))}")

def _eval({params}):
{code}

globals()['chatbot_llm_action_result_'] = _eval({params})
    """

    compiled = compile(code, "<string>", "exec")
    global_vars = globals().copy()
    eval(compiled, global_vars, data.copy())
    result = global_vars["chatbot_llm_action_result_"]
    return result


class Evaluator:
    def __init__(self, load_path: List[str] = []):
        self.load_path = load_path
        globals()["load_path"] = load_path

    def eval_code(self, execution: ExecuteElement, data: dict):
        lang = execution.language.lower()
        if lang == "python":

            if execution.code.endswith(".py"):
                ic(self.load_path)
                filename = find_file(execution.code, self.load_path)
                return eval_python_file(filename, data)
            else:
                code_to_execute = execution.code
                return eval_python_inline(code_to_execute, data)
        else:
            raise ValueError(f"Unknown language: {lang}")
