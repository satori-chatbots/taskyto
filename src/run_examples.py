from argparse import ArgumentParser

import main
import utils

if __name__ == '__main__':
    parser = ArgumentParser(description='Runner for a chatbot')
    parser.add_argument('--engine', required=False, default="standard",
                        help='Engine to use')
    parser.add_argument('--verbose', default=False, action='store_true',
                        help='Show the intermediate prompts')
    parser.add_argument('--debug', default=False, action='store_true',
                        help='Show all intermediate processing information')

    args = parser.parse_args()

    main.setup_debugging_capabilities(args)

    utils.check_keys(["OPENAI_API_KEY"])

    chatbots = [
        "examples/yaml/pizza-shop",
        "examples/yaml/bike-shop",
        "examples/yaml/smart_calculator"
    ]

    for chatbot in chatbots:
        print("Running tests for chatbot: ", chatbot, "\n")
        args.chatbot = chatbot
        configuration = main.setup_configuration(args)
        main.test(chatbot, chatbot, configuration, False, False, None, [])
        