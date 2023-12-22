import glob
import os
#from plistlib import Data

import yaml
from testing.test_model import Interaction, UserSays, ChatbotAnswer, ModuleAssert, DataAssert


def to_model(data) -> Interaction:
    interaction = data['interaction']
    elements = []
    for element in interaction:
        if 'user' in element:
            elements.append(UserSays(message=element['user']))
        elif 'chatbot' in element:
            chatbot_answer = element['chatbot']
            if isinstance(chatbot_answer, str):
                elements.append(ChatbotAnswer(answers=[chatbot_answer]))
            elif isinstance(chatbot_answer, list):
                elements.append(ChatbotAnswer(answers=chatbot_answer))
            else:
                raise ValueError('Unknown chatbot answer', chatbot_answer)
        elif 'assert_module' in element:
            elements.append(ModuleAssert(assert_module=element['assert_module']))
        elif 'assert_data' in element:
            elements.append(DataAssert(data_asserts=element['assert_data']))
        else:
            raise ValueError('Unknown element type', element)

    return Interaction(interactions=elements)


def load_test_model(filename):
    data = read(filename)
    return to_model(data)


def load_test_set(path):
    # Read files in path
    files = glob.glob(os.path.join(path, '*.yaml'))
    for file in files:
        # TODO: Merge
        return load_test_model(file)


def read(filename):
    # Open the yaml file
    with open(filename, 'r') as stream:
        try:
            # Load the yaml file
            data = yaml.safe_load(stream)
            # Return the data
            return data
        except yaml.YAMLError as exc:
            print(exc)
