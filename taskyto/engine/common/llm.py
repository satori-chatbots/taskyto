import abc
from typing import Union, List, Optional


class Message:
    def __init__(self, content: str, type: str):
        self.content = content
        self.type = type


LLMInput = Union[str, List[Message]]


class LLMResponse:

    def __init__(self, content: str):
        self.content = content


class LLM(abc.ABC):
    @abc.abstractmethod
    def __call__(self, input_: LLMInput) -> LLMResponse:
        raise NotImplementedError()

from openai import OpenAI

class OpenAILLM(LLM):
    def __init__(self, model_name: str, temperature: float = 0.0):
        self.model_name = model_name
        self.temperature = temperature
        self.client = OpenAI()

    def __call__(self, input_: LLMInput, stop: Optional[List[str]] = None) -> LLMResponse:
        return self.invoke(input_, stop)

    def invoke(self, input_: LLMInput, stop: Optional[List[str]] = None) -> LLMResponse:
        llm_input_messages = []
        if isinstance(input_, str):
            llm_input_messages.append({ "role": "user", "content":input_ })
        else:
            for message in input_:
                if message.type == "human":
                    llm_input_messages.append({ "role": "user", "content": message.content })
                else:
                    llm_input_messages.append({ "role": "developer", "content": message.content })
                # TODO: Identify assistant role

        completion = self.client.chat.completions.create(model=self.model_name,
                                                         temperature=self.temperature,
                                                         messages=llm_input_messages,
                                                         stop=stop)

        result = completion.choices[0].message
        return LLMResponse(result.content)


class ExtensionLLM(LLM):
    """A LLM dinamically loaded as an extension"""

    def __init__(self, extension):
        self.extension = extension

    def __call__(self, input_: LLMInput, stop: Optional[List[str]] = None) -> LLMResponse:
        return self.invoke(input_, stop)

    def invoke(self, input_: LLMInput, stop: Optional[List[str]] = None) -> LLMResponse:
        return LLMResponse(self.extension(input=input_, stop=stop))
