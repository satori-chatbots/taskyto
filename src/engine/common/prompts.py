from typing import Callable

from langchain.schema import OutputParserException

import spec


def menu_prompt(module: spec.MenuModule, item_handling: Callable[[spec.MenuModule], str]) -> str:
    # Describe the menu
    options = '\nYou are able to assist only in these tasks:\n'
    options = options + '\n'.join([f'{i}: {item.title}' for i, item in enumerate(module.items)])

    # Describe how to handle each option
    handling = item_handling(module)

    # Specify the fallback
    if module.fallback is None:
        fallback = ''
    else:
        fallback = '\nFallback:\n' + module.fallback

    prompt = f'{module.presentation}\n{options}\n{handling}\n{fallback}'

    return prompt

def question_answering_prompt(module: spec.QuestionAnsweringModule) -> str:
    prompt = [f"Use the following to answer the questions:\n"]
    prompt = prompt + [f"- Question: {q.question}\n  Answer: {q.answer}\n" for q in module.questions]
    prompt = prompt + [f"\nOnly provide an answer if the question is in the list.\n"]
    prompt = "\n".join(prompt) + "\n"
    return prompt

FORMAT_INSTRUCTIONS = """To use a tool, please use the following format:

```
Thought: Do I need to use a tool? Yes
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
```

When you have a response to say to the Human, or if you do not need to use a tool, you MUST use the format:

```
Thought: Do I need to use a tool? No
{ai_prefix}: [your response here]
```"""
