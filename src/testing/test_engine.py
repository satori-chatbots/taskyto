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

def run_test(interaction: Interaction, engine: Engine,
             config: TestEngineConfiguration = TestEngineConfiguration()):

    interactions = interaction.interactions[1:] \
        if isinstance(interaction.interactions[0], ChatbotAnswer) \
        else interaction.interactions

    channel = config.new_channel()
    engine.start(channel)

    user_interactions = 0
    for i in interactions:
        if config.replay is not None and user_interactions >= config.replay:
            return False

        if isinstance(i, UserSays):
            utils.print_user_request(i.message)

            engine.execute_with_input(i.message)
            response = channel.last_response
            utils.print_chatbot_answer(response)
        else:
            i.check(interaction.config, engine, config, response)

    return True
