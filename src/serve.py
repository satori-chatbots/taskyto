from argparse import ArgumentParser

import main, utils

if __name__ == '__main__':
    parser = ArgumentParser(description='Runner for a chatbot')
    parser.add_argument('--chatbot', required=True,
                        help='Path to the chatbot specification')
    parser.add_argument('--engine', required=False, default="custom",
                        help='Engine to use')
    parser.add_argument('--verbose', default=False, action='store_true',
                        help='Show the intermediate prompts')
    parser.add_argument('--debug', default=False, action='store_true',
                        help='Show all intermediate processing information')

    args = parser.parse_args()

    main.setup_debugging_capabilities(args)

    utils.check_keys(["OPENAI_API_KEY"])

    configuration = main.setup_configuration(args)

    from server import FlaskChatbotApp
    chatbot_app = FlaskChatbotApp(configuration)
    chatbot_app.run()
