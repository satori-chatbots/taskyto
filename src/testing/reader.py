import glob
import os

import yaml
from testing.test_model import Interaction, UserSays, ChatbotAnswer


def to_model(data) -> Interaction:
    interaction = data['interaction']
    elements = []
    for element in interaction:
        if 'user' in element:
            elements.append(UserSays(message=element['user']))
        elif 'chatbot' in element:
            elements.append(ChatbotAnswer(message=element['chatbot']))
        else:
            raise ValueError('Unknown element type', element)

    return Interaction(interaction=elements)


def load_test_model(path):
    # Read files in path
    files = glob.glob(os.path.join(path, '*.yaml'))
    for file in files:
        data = read(file)
        # TODO: Merge
        return to_model(data)

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
    
