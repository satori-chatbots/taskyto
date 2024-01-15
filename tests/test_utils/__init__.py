import re
from typing import Optional, List, Any

from langchain.callbacks.base import Callbacks
from langchain.schema import BaseMessage

import spec
from engine.common import Configuration, Engine, BasicConfiguration
from engine.common.configuration import ConfigurationModel
from engine.custom.engine import CustomPromptEngine


class AIAnswer:

    def __init__(self, message):
        self.message = message

    def to_message(self):
        response = f"Thought: Do I need to use a tool? No\nAI: {self.message}"
        return BaseMessage(content=response, type="mocked_test_response")


class ModuleActivation:

    def __init__(self, module, query):
        self.module = module
        self.query = query

    def to_message(self):
        response = f"""Thought: Do I need to use a tool? Yes
Action: {self.module}
Action Input: {self.query}"""
        return BaseMessage(content=response, type="mocked_test_response")


class MockedLLM:

    def __init__(self):
        self.prefixes = set()
        self.input_output = {}

    def __call__(
            self,
            messages: List[BaseMessage],
            stop: Optional[List[str]] = None,
            callbacks: Callbacks = None,
            **kwargs: Any,
    ) -> BaseMessage:
        full_message = "".join([m.content for m in messages])

        found_prefix = None
        found_text = None
        for line in full_message.split("\n"):
            for prefix in self.prefixes:
                if line.startswith(prefix):
                    found_prefix = prefix
                    found_text = line[len(prefix):].strip()

        if not found_prefix:
            raise Exception(f"Could not find configured prefixes in: `{full_message}`. Prefixes are:\n" + "\n".join(self.prefixes))

        if found_text not in self.input_output:
            raise Exception(f"Input `{found_text}` not found in the answers of the test mock")

        output = self.input_output[found_text]
        return output.to_message()

    def ai_answer(self, input, output, prefix):
        self.prefixes.add(prefix)
        self.input_output[input] = AIAnswer(message=output)

    def module_activation(self, input, module, query):
        self.input_output[input] = ModuleActivation(module=module, query=query)


class TestConfiguration(BasicConfiguration):
    def __init__(self, root_folder, mocked_llm: MockedLLM):
        super().__init__(root_folder)
        self.llm = mocked_llm
        self.model = ConfigurationModel(default_llm="mocked", languages="en")

    def new_channel(self):
        raise NotImplementedError("This is created separately by the test case")

    def new_rephraser(self):
        raise NotImplementedError()

    def new_engine(self) -> Engine:
        return CustomPromptEngine(self.chatbot_model, configuration=self)

    def new_llm(self, module_name: Optional[str] = None):
        return self.llm
