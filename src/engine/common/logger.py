from typing import List

from langchain.schema import BaseMessage

DEBUG=True

def debug(msg):
    if DEBUG:
        print(msg)


def debug_prompt(formatted_prompt: List[BaseMessage]):
    debug("Prompt:\n" + "\n".join([str(x.content) for x in formatted_prompt]))
