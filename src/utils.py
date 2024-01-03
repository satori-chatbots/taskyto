import os
import configparser

from engine.common import ChatbotResult


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


def get_unparsed_output(message : str) -> str:
    msg = message.split("Could not parse LLM output: ")
    if len(msg)>1:
        return msg[1].strip("`")
    return message