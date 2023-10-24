import sys

import utils
from engine import Engine
from testing.test_model import Interaction, UserSays, ChatbotAnswer


class TestEngineConfiguration:
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.replay = None


def assert_chatbot_answer(i: ChatbotAnswer, response):
    message = response.chatbot_msg
    if message not in i.answers:
        print(f"Chatbot answer was '{message}'\n", file=sys.stderr)
        print(f"Expected one of:", file=sys.stderr)
        for a in i.answers:
            print(f" - {a}", file=sys.stderr)
        print(file=sys.stderr)

        raise ValueError(f"Expected chatbot answer '{message}' not found in {i.answers}")


def run_test(interaction: Interaction, engine: Engine,
             config: TestEngineConfiguration = TestEngineConfiguration()):
    interactions = interaction.interactions[1:-1] \
        if isinstance(interaction.interactions[0], ChatbotAnswer) \
        else interaction.interactions

    response = engine.first_action()
    utils.print_chatbot_answer(response)

    user_interactions = 0
    for i in interactions:
        if config.replay is not None and user_interactions >= config.replay:
            return False

        if isinstance(i, UserSays):
            utils.print_user_request(i.message)

            response = engine.run_step(i.message)
            utils.print_chatbot_answer(response)

            user_interactions += 1
        elif isinstance(i, ChatbotAnswer):
            if not config.dry_run:
                assert_chatbot_answer(i, response)
        else:
            raise ValueError("Unknown interaction element", i)

    return True
