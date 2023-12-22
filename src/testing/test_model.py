import sys
from abc import ABC, abstractmethod
from typing import Literal, List, Dict, Any

import pydantic
from pydantic import BaseModel, Field
from pydantic.json_schema import DEFAULT_REF_TEMPLATE

import utils
#from engine.common import Engine, ChatbotResult
#from testing.test_engine import TestEngineConfiguration


class InteractionElement(BaseModel, ABC):
    def check(self, engine, config): # return response or None
        return False


class UserSays(InteractionElement):
    message: str

    def check(self, engine, config, response):
        """
        return True since it is a UserSays
        """
        utils.print_user_request(self.message)
        response = engine.run_step(self.message)
        utils.print_chatbot_answer(response)
        return response


class ChatbotAnswer(InteractionElement):
    answers: List[str] = []

    def check(self, engine, config, response):
        if not config.dry_run:
            message = response.chatbot_msg
            if message not in self.answers:
                print(f"Chatbot answer was '{message}'\n", file=sys.stderr)
                print(f"Expected one of:", file=sys.stderr)
                for a in self.answers:
                    print(f" - {a}", file=sys.stderr)
                print(file=sys.stderr)

                raise ValueError(f"Expected chatbot answer '{message}' not found in {self.answers}")
        return None


class ModuleAssert(InteractionElement):
    assert_module: str = None

    def check(self, engine, config, response) -> bool:
        if not config.dry_run:
            module_exec = response.debug_info.current_module
            if response.debug_info.executed_tool is not None:
                module_exec = response.debug_info.executed_tool

            if self.assert_module != module_exec:
                print(f"Expecting chatbot in module {self.assert_module}", file=sys.stderr)
                print(f"But chatbot was executing module {module_exec} ", file=sys.stderr)
                raise ValueError(f"Expected module {self.assert_module}, but was {module_exec}")
        return None


class DataAssert(InteractionElement):
    data_asserts: Dict[str, str] = {}

    def check(self, engine, config, response):
        if engine.state_manager.data is None:
            raise ValueError(f"Found no data, but asked to assert {self.data_asserts}")
        data = next(iter(engine.state_manager.data.values()))
        print(f"Need to check the following assertions {self.data_asserts} in {data}")
        for attr in self.data_asserts:
            if attr in data:
                if data[attr] != self.data_asserts[attr]:
                    print(f"Expecting value {self.data_asserts[attr]} for {attr}, but got {data[attr]}", file=sys.stderr)
                    raise ValueError(f"Expecting value {self.data_asserts[attr]} for {attr}, but got {data[attr]}")
            else:
                print(f"Did not find field {attr}", file=sys.stderr)
                raise ValueError(f"Did not find field {attr}")
        return None


class Interaction(BaseModel):
    interactions: List[InteractionElement]


