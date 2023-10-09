import os.path
from argparse import ArgumentParser

import engine
import utils
from spec import ChatbotModel


class LangChainConfiguration(engine.Configuration):

    def new_state(self):
        from modules import State
        from langchain.chat_models import ChatOpenAI

        utils.check_keys(["SERPAPI_API_KEY", "OPENAI_API_KEY"])
        llm = ChatOpenAI(temperature=0., model_name="gpt-3.5-turbo-0301", verbose=True)

        #Doesn't work
        #llm = ChatOpenAI(temperature=0., model_name="gpt-3.5-turbo", verbose=True)

        # Do work
        #llm = ChatOpenAI(temperature=0., model_name="gpt-4")

        state = State(llm=llm)
        return state


def main(chatbot_folder: str, module_path):
    from engine import Engine
    from spec import parse_yaml
    import glob

    if not os.path.exists(chatbot_folder):
        print("Chatbot folder does not exist: " + chatbot_folder)
        exit(1)

    # Read yaml files in chatbot_folder
    modules = []
    for yaml_path in glob.glob(os.path.join(chatbot_folder, '*.yaml')):
        with open(yaml_path) as yaml_file:
            parsed_modules = parse_yaml(yaml_file.read())
            modules.extend(parsed_modules)

    model = ChatbotModel(modules=modules)
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

    args = parser.parse_args()

    main(args.chatbot, args.module_path)
