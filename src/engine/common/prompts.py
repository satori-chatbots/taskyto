from typing import Callable

from langchain.schema import OutputParserException

import spec


class Prompt:
    def __init__(self, sections=[]):
        self.sections = []
        self.sections.extend(sections)

    def __add__(self, other):
        return Prompt(self.sections + other.sections)

    def variables(self):
        variables = []
        for section_ in self.sections:
            variables.extend(section_.variables())
        return variables

    def to_text(self, prompts_disabled=[]) -> str:
        return "\n".join([s.content for s in self.sections if s.name not in prompts_disabled])

class PromptSection:
    def __init__(self, name, content):
        self.name = name
        self.content = content

    @property
    def sections(self):
        return [self]

    def to_prompt(self):
        return Prompt([self])

    def __add__(self, other):
        return Prompt([self, other])

    def variables(self):
        import re
        return re.findall(r'\{([^\}]+)\}', self.content)


def section(name: str, content: str) -> PromptSection:
    return PromptSection(name, content)


def menu_prompt(module: spec.MenuModule, item_handling: Callable[[spec.MenuModule], str], languages: str) -> str:
    # Describe the menu
    options = '\nYou are able to assist only in these tasks:\n'
    options = options + '\n'.join([f'{i}: {item.title}' for i, item in enumerate(module.items)])

    # Describe how to handle each option
    handling = item_handling(module)

    # Specify the fallback
    if module.fallback is None:
        fallback = ''
    else:
        fallback = '\nFallback:\n'+'For any question not related to these aspects you have to answer:'+module.fallback

    languages_prompt = '\nYou are only able to answer  the user in the following languages: '+languages+'\n'
    languages_prompt += f'\nIf the user uses a language different from {languages}, ask politely to switch to {languages}'

    prompt = f'{module.presentation}\n{languages_prompt}\n{options}\n{handling}\n{fallback}'

    return prompt


def question_answering_prompt(module: spec.QuestionAnsweringModule) -> str:
    prompt = [f"The following is the list of question/answer pairs that you are allowed to answer:\n"]
    prompt = prompt + [f"- Question: {q.question}\n  Answer: {q.answer}\n" for q in module.questions]
    prompt = prompt + [f"\nOnly provide an answer if the question is in the list.\n"]
    prompt = "\n".join(prompt) + "\n"
    return prompt

# When you have a response to say to the Human, or if you do not need to use a tool, you MUST use the format:
# If you do not need to use a tool to provide the answer to the Human, you MUST use the format:
FORMAT_INSTRUCTIONS = """You have tools to help you achieve some of your tasks. To use a tool, please use the following format:
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

NO_TOOL_INSTRUCTIONS = """To respond to the Human you MUST use the format:

```
Thought: Do I need to use a tool? No
{ai_prefix}: [your response here]
```"""