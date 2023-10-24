import os
import configparser

from engine import ChatbotResult


def check_keys(key_list: list):
    # Check if keys.properties exists
    if os.path.exists('keys.properties'):
        config = configparser.ConfigParser()
        config.read('keys.properties')

        # Loop over all keys and values
        for key in config['keys']:
            key = key.upper()
            os.environ[key] = config['keys'][key]

    for k in key_list:
        if not os.environ.get(k):
            raise Exception(f"{k} not found")


def print_chatbot_answer(response: ChatbotResult):
    module_name = response.debug_info.current_module
    print("Chatbot [" + module_name + "]: " + response.chatbot_msg)


def get_user_prompt():
    return "You: "


def print_user_request(message: str):

    print(get_user_prompt() + message)
