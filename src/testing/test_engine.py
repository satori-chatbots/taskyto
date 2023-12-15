import sys

import utils

from engine.common import Engine
from testing.test_model import Interaction, UserSays, ChatbotAnswer, ModuleAssert
from engine.common import Engine, DebugInfo
from engine.custom.runtime import Channel
from testing.test_model import Interaction, UserSays, ChatbotAnswer

class TestChannel(Channel):

    def __init__(self):
        self.last_response = None

    def input(self):
        raise NotImplementedError()

    def output(self, msg, who=None):
        self.last_response = ChatbotResult(msg, DebugInfo(who))

class ChatbotResult:
    def __init__(self, chatbot_msg: str, debug_info: DebugInfo):
        self.chatbot_msg = chatbot_msg
        self.debug_info = debug_info


class TestEngineConfiguration:
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.replay = None

    def new_channel(self):
        return TestChannel()

def assert_chatbot_answer(i: ChatbotAnswer, response):
    message = response.chatbot_msg
    if message not in i.answers:
        print(f"Chatbot answer was '{message}'\n", file=sys.stderr)
        print(f"Expected one of:", file=sys.stderr)
        for a in i.answers:
            print(f" - {a}", file=sys.stderr)
        print(file=sys.stderr)

        raise ValueError(f"Expected chatbot answer '{message}' not found in {i.answers}")

def assert_chatbot_module(i: ModuleAssert, response):
    module_exec = response.debug_info.current_module
    if response.debug_info.executed_tool is not None:
        module_exec = response.debug_info.executed_tool

    if i.assert_module != module_exec:
        print(f"Expecting chatbot in module {i.assert_module}", file=sys.stderr)
        print(f"But chatbot was executing module {module_exec} ", file=sys.stderr)
        raise ValueError(f"Expected module {i.assert_module}, but was {module_exec}")

def run_test(interaction: Interaction, engine: Engine,
             config: TestEngineConfiguration = TestEngineConfiguration()):

    #interactions = interaction.interactions
    interactions = interaction.interactions[1:] \
        if isinstance(interaction.interactions[0], ChatbotAnswer) \
        else interaction.interactions

    channel = config.new_channel()
    engine.start(channel)

    user_interactions = 0
    for i in interactions:
        if config.replay is not None and user_interactions >= config.replay:
            return False

        result = i.check(engine, config, response)
        if result is not None:
            response = result
            user_interactions +=1

        if isinstance(i, UserSays):
            utils.print_user_request(i.message)

            engine.execute_with_input(i.message)
            response = channel.last_response
            utils.print_chatbot_answer(response)


        # if isinstance(i, UserSays):
        #     utils.print_user_request(i.message)
        #
        #     response = engine.run_step(i.message)
        #     utils.print_chatbot_answer(response)
        #
        #     user_interactions += 1
        # elif isinstance(i, ChatbotAnswer):
        #     if not config.dry_run:
        #         assert_chatbot_answer(i, response)
        # elif isinstance(i, ModuleAssert):
        #     if not config.dry_run:
        #         assert_chatbot_module(i, response)
        #else:
        #    raise ValueError("Unknown interaction element", i)

    return True
