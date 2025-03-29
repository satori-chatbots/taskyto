from typing import List

import langchain.globals
from langchain.schema import BaseMessage

DEBUG = True


def debug(msg):
    if DEBUG:
        print(msg)


def debug_prompt(formatted_prompt: List[BaseMessage]):
    if langchain.globals.get_verbose():
        debug("Prompt:\n" + "\n".join([str(x.content) for x in formatted_prompt]))
