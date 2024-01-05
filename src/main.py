import os.path

from langchain.schema import OutputParserException
from typing import Optional

import utils
import glob

from argparse import ArgumentParser

from engine.common import Configuration, Engine, ChatbotResult, DebugInfo
from engine.common import Configuration, Engine
from engine.common.configuration import ConfigurationModel, read_configuration
from engine.common.evaluator import Evaluator
from engine.custom.engine import CustomPromptEngine
from engine.custom.runtime import CustomRephraser, ConsoleChannel
from recording import dump_test_recording
from spec import ChatbotModel
from spec import parse_yaml
from engine.langchain import LangchainEngine
from testing.reader import load_test_model
from testing.test_engine import TestEngineConfiguration, run_test
from utils import get_unparsed_output


class CustomConfiguration(Configuration):

    def __init__(self, root_folder, model: ConfigurationModel):
        self.root_folder = root_folder
        self.model = model

    def new_channel(self):
        from engine.custom.runtime import ConsoleChannel
        return ConsoleChannel()

    def new_engine(self, model: ChatbotModel) -> Engine:
        return CustomPromptEngine(model, configuration=self)

    def new_evaluator(self):
        return Evaluator(load_path=[self.root_folder])

    def llm(self, module_name: Optional[str] = None):
        from langchain.chat_models import ChatOpenAI
        model = self.model.get_llm_for_module_or_default(module_name)

        llm = ChatOpenAI(temperature=0, model_name=model.id, verbose=True)
        return llm

    def new_rephraser(self):
        return CustomRephraser(self)


class LangChainConfiguration(Configuration):

    def new_engine(self, model: ChatbotModel) -> Engine:
        return LangchainEngine(model, configuration=self)

    def new_state(self):
        from engine.langchain.modules import State
        from langchain.chat_models import ChatOpenAI

        llm = ChatOpenAI(temperature=0, model_name="gpt-3.5-turbo-0301", verbose=True)

        # Doesn't work
        # llm = ChatOpenAI(temperature=0., model_name="gpt-3.5-turbo", verbose=True)

        # Do work
        # llm = ChatOpenAI(temperature=0., model_name="gpt-4")

        state = State(llm=llm)
        return state


def load_chatbot_model(chatbot_folder_or_file: str):
    modules = []
    if chatbot_folder_or_file.endswith(".yaml"):
        with open(chatbot_folder_or_file) as yaml_file:
            parsed_modules = parse_yaml(yaml_file.read())
            modules.extend(parsed_modules)
    else:
        # Read yaml files in chatbot_folder
        for yaml_path in glob.glob(os.path.join(chatbot_folder_or_file, '*.yaml')):
            with open(yaml_path) as yaml_file:
                parsed_modules = parse_yaml(yaml_file.read())
                modules.extend(parsed_modules)

    model = ChatbotModel(modules=modules)
    return model


def load_configuration_model(chatbot_folder, configuration_file: Optional[str] = None) -> ConfigurationModel:
    if configuration_file is None:
        configuration_file = os.path.join(chatbot_folder, "configuration", "default.yaml")
        if not os.path.isfile(configuration_file):
            return ConfigurationModel(default_llm="gpt-3.5-turbo-0613")

    # See OpenAI model table: https://platform.openai.com/docs/models
    return read_configuration(configuration_file)


def initialize_engine(chatbot_folder, configuration):
    if not os.path.exists(chatbot_folder):
        print("Chatbot folder does not exist: " + chatbot_folder)
        exit(1)
    model = load_chatbot_model(chatbot_folder)
    engine = configuration.new_engine(model)
    return engine


def run_with_engine(engine: Engine):
    while True:
        user_prompt = utils.get_user_prompt()
        try:
            inp = input(user_prompt)
            if inp == 'exit':
                return
        except EOFError as e:
            return

        try:
            result = engine.run_step(inp)
        except OutputParserException as ope:
            #result = ChatbotResult("Could not parse LLM output", DebugInfo("top_level"))
            result = ChatbotResult(get_unparsed_output(str(ope)), DebugInfo("top_level"))

        utils.print_chatbot_answer(result)


def main(chatbot_folder: str, configuration, recording_file_dump: str = None, module_path=None):
    engine = initialize_engine(chatbot_folder, configuration)

    # check if engine has method first_action
    if not hasattr(engine, 'first_action'):
        channel = configuration.new_channel()
        engine.run_all(channel)

    else:
        # This is an engine which uses an externally input loop
        # Run the first action which is typically a greeting
        result = engine.first_action()
        utils.print_chatbot_answer(result)
        run_with_engine(engine)

    dump_test_recording(engine.recorded_interaction, file=recording_file_dump)


def test(chatbot, test_file, configuration, dry_run, replay=None, recording_file_dump: str = None, module_path=None):
    # Check if test_file is a folder, in which case return all tests in the `test` folder (find recursively)
    if os.path.isdir(test_file):
        tests = []
        for root, dirs, files in os.walk(test_file):
            for file in files:
                parent_folder_name = os.path.basename(root)
                if parent_folder_name in ["tests", "test"] and file.endswith(".yaml"):
                    tests.append(os.path.join(root, file))

        for individual_test_file in tests:
            print("Running test: " + individual_test_file)
            test(chatbot, individual_test_file, configuration, dry_run, replay, None, module_path)
    else:
        engine = initialize_engine(chatbot, configuration)
        test_model = load_test_model(test_file)
        config = TestEngineConfiguration(dry_run=dry_run)
        if replay:
            config.replay = replay
        completed_steps = run_test(test_model, engine, config)
        if not completed_steps:
            run_with_engine(engine)

        if recording_file_dump is not None:
            dump_test_recording(engine.recorded_interaction, file=recording_file_dump)


if __name__ == '__main__':
    parser = ArgumentParser(description='Runner for a chatbot')
    parser.add_argument('--chatbot', required=True,
                        help='Path to the chatbot specification')
    parser.add_argument('--module-path', default='.',
                        help='List of paths to chatbot modules, separated by :')
    parser.add_argument('--engine', required=False, default="custom",
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

    args = parser.parse_args()
    if args.verbose:
        import langchain.globals

        langchain.globals.set_verbose(True)

    if args.debug:
        import langchain.globals

        langchain.globals.set_debug(True)

    if args.engine == "langchain":
        configuration = LangChainConfiguration()
    else:
        chatbot_folder = args.chatbot
        if os.path.isfile(chatbot_folder):
            chatbot_folder = os.path.dirname(chatbot_folder)

        config_model = load_configuration_model(chatbot_folder)
        configuration = CustomConfiguration(chatbot_folder, config_model)

    utils.check_keys(["OPENAI_API_KEY"]) # "SERPAPI_API_KEY"
    if args.test:
        test(args.chatbot, args.test, configuration, args.dry_run, args.replay, args.dump, args.module_path)
    else:
        main(args.chatbot, configuration, args.dump, args.module_path)
