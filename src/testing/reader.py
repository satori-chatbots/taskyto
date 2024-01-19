import glob
import os
from typing import Any

import pydantic
# from plistlib import Data

import yaml

from testing.test_config_model import TestConfigurationModel, default_test_configuration
from testing.test_model import Interaction, UserSays, ChatbotAnswer, ModuleAssert, DataAssert


def to_model(filename, data, configuration: TestConfigurationModel) -> Interaction:
    name = os.path.basename(filename).replace('.yaml', '')
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
            assert_data = element['assert_data']
            elements.append(DataAssert(scope=assert_data['scope'], data_asserts=assert_data['values']))
        else:
            raise ValueError('Unknown element type', element)

    test_configuration = configuration.configuration_for_test(name)
    return Interaction(name=name, interactions=elements, config=test_configuration)


def load_test_model(filename, configuration_file: str = None) -> Interaction:
    data = read(filename)

    # Try to find a default configuration file
    if configuration_file is None:
        configuration_file = os.path.join(os.path.dirname(filename), 'configuration.yaml')
        if not os.path.exists(configuration_file):
            configuration_file = None

    if configuration_file is not None:
        configuration = read_test_configuration(configuration_file)
    else:
        configuration = default_test_configuration()

    interaction = to_model(filename, data, configuration)
    return interaction

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


def read_test_configuration(configuration_file: str) -> TestConfigurationModel:
    import yaml

    def parse_obj_as_(type_: type, obj: Any):
        return pydantic.type_adapter.TypeAdapter(type_).validate_python(obj)

    with open(configuration_file) as yaml_file:
        data = yaml.safe_load(yaml_file.read())
        return parse_obj_as_(TestConfigurationModel, data)
