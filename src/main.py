import os.path
import engine
import utils
import glob

from argparse import ArgumentParser
from spec import ChatbotModel
from spec import parse_yaml
from engine import Engine


class LangChainConfiguration(engine.Configuration):

    def new_state(self):
        from modules import State
        from langchain.chat_models import ChatOpenAI

        utils.check_keys(["SERPAPI_API_KEY", "OPENAI_API_KEY"])
        llm = ChatOpenAI(temperature=0, model_name="gpt-3.5-turbo-0301", verbose=True)

        #Doesn't work
        #llm = ChatOpenAI(temperature=0., model_name="gpt-3.5-turbo", verbose=True)

        # Do work
        #llm = ChatOpenAI(temperature=0., model_name="gpt-4")

        state = State(llm=llm)
        return state


def load_chatbot_model(chatbot_folder):
    # Read yaml files in chatbot_folder
    modules = []
    for yaml_path in glob.glob(os.path.join(chatbot_folder, '*.yaml')):
        with open(yaml_path) as yaml_file:
            parsed_modules = parse_yaml(yaml_file.read())
            modules.extend(parsed_modules)
    model = ChatbotModel(modules=modules)
    return model


def main(chatbot_folder: str, module_path):
    if not os.path.exists(chatbot_folder):
        print("Chatbot folder does not exist: " + chatbot_folder)
        exit(1)

    model = load_chatbot_model(chatbot_folder)
    engine = Engine(model, configuration=LangChainConfiguration())
    result = engine.first_action()
    while True:
        module_name = result.debug_info.current_module
        print("Chatbot [" + module_name + "]: " + result.chatbot_msg)

        user_prompt = "You: "

        inp = input(user_prompt)

        result = engine.run_step(inp)


if __name__ == '__main__':
    parser = ArgumentParser(description='Runner for a chatbot')
    parser.add_argument('--chatbot', required=True,
                        help='Path to the chatbot specification')
    parser.add_argument('--module-path', default='.',
                        help='List of paths to chatbot modules, separated by :')
    parser.add_argument('--verbose', default=False, action='store_true',
                        help='Show the intermediate prompts')
    parser.add_argument('--debug', default=False, action='store_true',
                        help='Show all intermediate processing information')

    args = parser.parse_args()
    if args.verbose:
        import langchain.globals
        langchain.globals.set_verbose(True)

    if args.debug:
        import langchain.globals
        langchain.globals.set_debug(True)

    main(args.chatbot, args.module_path)
