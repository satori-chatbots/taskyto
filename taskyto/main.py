import os.path
from argparse import ArgumentParser
from typing import Optional, List

from taskyto import spec
from taskyto import utils
from taskyto.engine.common import Configuration, Engine
from taskyto.engine.common.configuration import ConfigurationModel, read_configuration
from taskyto.engine.common.evaluator import Evaluator
from taskyto.engine.custom.engine import CustomPromptEngine
from taskyto.engine.custom.runtime import CustomRephraser
from taskyto.recording import dump_test_recording
from taskyto.testing.reader import load_test_model
from taskyto.testing.test_engine import TestEngineConfiguration, run_test


class CustomConfiguration(Configuration):

    def __init__(self, root_folder, model: ConfigurationModel):
        assert model is not None

        self.chatbot_model = spec.load_chatbot_model(root_folder)
        self.root_folder = root_folder
        self.model = model

    @property
    def initial_greeting(self):
        if self.model.begin is not None:
            return self.model.begin.greeting
        return "Hello"

    @property
    def is_user_beginning(self):
        return (self.model.begin is not None and
                self.model.begin.with_ == 'user')

    def new_channel(self):
        from taskyto.engine.custom.runtime import ConsoleChannel
        return ConsoleChannel()

    def new_engine(self) -> Engine:
        return CustomPromptEngine(self.chatbot_model, configuration=self)

    def new_evaluator(self):
        return Evaluator(load_path=[self.root_folder])

    def new_llm(self, module_name: Optional[str] = None):
        return self.model.get_llm_for_module_or_default(module_name)

    def new_rephraser(self):
        return CustomRephraser(self)


def load_configuration_model(chatbot_folder, configuration_file: Optional[str] = None, module_path: List[str] = []) -> ConfigurationModel:
    if configuration_file is None:
        configuration_file = os.path.join(chatbot_folder, "configuration", "default.yaml")
        if not os.path.isfile(configuration_file):
            print("Using default configuration")
            return ConfigurationModel(default_llm="gpt-4o-mini")
        else:
            print("Using configuration", configuration_file)

    # See OpenAI model table: https://platform.openai.com/docs/models
    return read_configuration(configuration_file, module_path)


def initialize_engine(chatbot_folder, configuration):
    if not os.path.exists(chatbot_folder):
        print("Chatbot folder does not exist: " + chatbot_folder)
        exit(1)
    engine = configuration.new_engine()
    return engine


def execute_chatbot(chatbot_folder: str, configuration, recording_file_dump: str = None, module_path=None):
    engine = initialize_engine(chatbot_folder, configuration)

    channel = configuration.new_channel()
    engine.run_all(channel)

    dump_test_recording(engine.recorded_interaction, file=recording_file_dump, trace=True)

    print()
    print("Bye!")
    print(f"Average response time: {engine.recorded_interaction.average_response_time()}")


def is_test_file(file):
    return file.endswith(".yaml") and not is_test_configuration(file)

def is_test_configuration(file):
    return file.endswith("configuration.yaml")


def test(chatbot, test_file, configuration, dry_run, replay=None, recording_file_dump: str = None, module_path=None):
    # Check if test_file is a folder, in which case return all tests in the `test` folder (find recursively)
    if os.path.isdir(test_file):
        tests = []
        for root, dirs, files in os.walk(test_file):
            for file in files:
                parent_folder_name = os.path.basename(root)
                if parent_folder_name in ["tests", "test"] and is_test_file(file):
                    tests.append(os.path.join(root, file))

        # iterate tests with indices
        for index, individual_test_file in enumerate(tests):
            print(f"{index + 1}. " + individual_test_file)
            test(chatbot, individual_test_file, configuration, dry_run, replay, None, module_path)
            print("\n")
    else:
        engine = initialize_engine(chatbot, configuration)
        test_model = load_test_model(test_file)
        config = TestEngineConfiguration(dry_run=dry_run)
        if replay:
            config.replay = replay
        completed_steps = run_test(test_model, engine, config)
        if not completed_steps:
            from taskyto.engine.custom.runtime import ConsoleChannel
            channel = ConsoleChannel()
            engine.run_all(channel)

        if recording_file_dump is not None:
            dump_test_recording(engine.recorded_interaction, file=recording_file_dump)


def setup_debugging_capabilities(args):
    if args.verbose:
        import langchain.globals

        langchain.globals.set_verbose(True)
    if args.debug:
        import langchain.globals

        langchain.globals.set_debug(True)


def setup_configuration(args):
    module_path = args.module_path.split(":")
    if args.engine is None or args.engine == 'standard':
        chatbot_folder = args.chatbot
        if os.path.isfile(chatbot_folder):
            chatbot_folder = os.path.dirname(chatbot_folder)

        config_model = load_configuration_model(chatbot_folder, args.config, module_path=module_path)
        conf = CustomConfiguration(chatbot_folder, config_model)
    else:
        raise ValueError(f"Unknown engine: {args.engine}")

    return conf

def main():
    parser = ArgumentParser(description='Runner for a chatbot')
    parser.add_argument('--chatbot', required=True,
                        help='Path to the chatbot specification')
    parser.add_argument('--module-path', default='',
                        help='List of paths to chatbot modules, separated by :')
    parser.add_argument('--engine', required=False, default="standard",
                        help='Engine to use')
    parser.add_argument('--verbose', default=False, action='store_true',
                        help='Show the intermediate prompts')
    parser.add_argument('--debug', default=False, action='store_true',
                        help='Show all intermediate processing information')
    parser.add_argument('--test', required=False,
                        help='Test file to run')
    parser.add_argument('--dry-run', default=False, action='store_true',
                        help='In test mode, do not check the chatbot answers')
    parser.add_argument('--replay', default=False, type=int,
                        help='Replay a test case up to n user steps')
    parser.add_argument('--dump', default=None, type=str,
                        help='A file to dump the interaction in a test case format')
    parser.add_argument('--config', default=None, type=str,
                        help='The configuration file to use for the chatbot')

    args = parser.parse_args()

    setup_debugging_capabilities(args)
    configuration = setup_configuration(args)

    utils.check_keys(["OPENAI_API_KEY"])  # "SERPAPI_API_KEY"
    if args.test:
        test(args.chatbot, args.test, configuration, args.dry_run, args.replay, args.dump, args.module_path)
    else:
        execute_chatbot(args.chatbot, configuration, args.dump, args.module_path)


if __name__ == '__main__':
    main()