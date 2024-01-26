import abc
from typing import Union, List, Optional

from langchain.chat_models import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage


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


class OpenAILLM(LLM):
    def __init__(self, model_name: str, temperature: float = 0.0):
        self.llm_model = ChatOpenAI(temperature=temperature, model_name=model_name, verbose=True)

    def __call__(self, input_: LLMInput, stop: Optional[List[str]] = None) -> LLMResponse:
        return self.invoke(input_, stop)

    def invoke(self, input_: LLMInput, stop: Optional[List[str]] = None) -> LLMResponse:
        if isinstance(input_, str):
            langchain_input = input_
        else:
            langchain_input = []
            for message in input_:
                if message.type == "human":
                    langchain_input.append(HumanMessage(content=message.content))
                else:
                    langchain_input.append(SystemMessage(content=message.content))

        result = self.llm_model.invoke(langchain_input, stop=stop)
        return LLMResponse(result.content)


class ExtensionLLM(LLM):
    """An LLM dinamically loaded as an extension"""

    def __init__(self, extension):
        self.extension = extension

    def __call__(self, input_: LLMInput, stop: Optional[List[str]] = None) -> LLMResponse:
        return self.invoke(input_, stop)

    def invoke(self, input_: LLMInput, stop: Optional[List[str]] = None) -> LLMResponse:
        return LLMResponse(self.extension(input=input_, stop=stop))
