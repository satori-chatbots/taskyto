from argparse import ArgumentParser

import main, utils

import os

HOST = "0.0.0.0"
PORT = 5001


HOST = os.getenv("HOST", HOST)
PORT = os.getenv("PORT", PORT)

def execute_server():
    parser = ArgumentParser(description='Runner for a chatbot')
    parser.add_argument('--chatbot', required=True,
                        help='Path to the chatbot specification')
    
    # parser.add_argument('--engine', required=False, default="custom",
                        # help='Engine to use')
    # parser.add_argument('--engine', required=False, default="common",
                        # help='Engine to use')

    parser.add_argument('--engine', required=False, default="standard",
                        help='Engine to use')
    
    parser.add_argument('--module-path', default='',
                        help='List of paths to chatbot modules, separated by :')
    
    parser.add_argument('--verbose', default=False, action='store_true',
                        help='Show the intermediate prompts')
    parser.add_argument('--debug', default=False, action='store_true',
                        help='Show all intermediate processing information')
    parser.add_argument('--config', default=None, type=str,
                        help='The configuration file to use for the chatbot')
    
    parser.add_argument('--host', default=HOST, type=str,
                        help='Application host or domain')
    
    parser.add_argument('--port', default=PORT, type=str,
                        help='Port to be used')

    args = parser.parse_args()

    main.setup_debugging_capabilities(args)

    utils.check_keys(["OPENAI_API_KEY"])

    configuration = main.setup_configuration(args)

    from taskyto.server import FlaskChatbotApp
    chatbot_app = FlaskChatbotApp(configuration)
    chatbot_app.run(args.host, args.port)

    print(f"HOST: {args.host}")
    print(f"PORT: {args.port}")

if __name__ == '__main__':
    execute_server()
