from argparse import ArgumentParser

from taskyto import main, utils

def execute_server():
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
    parser.add_argument('--config', default=None, type=str,
                        help='The configuration file to use for the chatbot')

    args = parser.parse_args()

    main.setup_debugging_capabilities(args)

    utils.check_keys(["OPENAI_API_KEY"])

    configuration = main.setup_configuration(args)

    from taskyto.server import FlaskChatbotApp
    chatbot_app = FlaskChatbotApp(configuration)
    chatbot_app.run()

if __name__ == '__main__':
    execute_server()