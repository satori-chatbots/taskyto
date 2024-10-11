import os.path
from spec import (ResponseElement, ExecuteElement, Action, ActionModule, DataGatheringModule, QuestionAnswer,
                  QuestionAnsweringModule, SequenceItem, ToolItem, AnswerItem, MenuModule, Module)
from spec import parse_yaml
import yaml
import glob
import shutil
from argparse import ArgumentParser
from typing import Dict


# --------------------------------------------------------------------------------------------
# TODO: mutatest for python (https://mutatest.readthedocs.io/en/latest/commandline.html)

# --------------------------------------------------------------------------------------------
# "to_dict" methods for the chatbot components, to facilitate their persistence using pydantic

def to_dict_response_element(self) -> dict:
    ret = dict()
    ret['text'] = self.text
    if self.rephrase is not None:
        ret['rephrase'] = self.rephrase
    return ret


def to_dict_execute_element(self) -> dict:
    ret = dict()
    ret['language'] = self.language
    ret['code'] = self.code
    return ret


def to_dict_action(self) -> dict:
    ret = dict()
    if self.execute is not None:
        ret['execute'] = self.execute.to_dict()
    if self.response is not None:
        ret['response'] = self.response.to_dict()
    return ret


def to_dict_action_module(self) -> dict:
    ret = dict()
    ret['name'] = self.name
    ret['kind'] = self.kind
    ret['data'] = self.data
    ret['on-success'] = self.on_success.to_dict()
    return ret


def to_dict_data_gathering_module(self) -> dict:
    ret = dict()
    ret['name'] = self.name
    ret['kind'] = self.kind
    ret['description'] = self.description
    ret['data'] = self.data
    ret['on-success'] = self.on_success.to_dict()
    return ret


def to_dict_question_answer(self) -> dict:
    ret = dict()
    ret['question'] = self.question
    ret['answer'] = self.answer
    return ret


def to_dict_question_answering_module(self) -> dict:
    ret = dict()
    ret['name'] = self.name
    ret['kind'] = self.kind
    ret['description'] = self.description
    ret['questions'] = [question.to_dict() for question in self.questions]
    return ret


def to_dict_sequence_item(self) -> dict:
    ret = dict()
    ret['title'] = self.title
    ret['memory'] = self.memory.value
    ret['kind'] = self.kind
    ret['references'] = self.references
    return ret


def to_dict_tool_item(self) -> dict:
    ret = dict()
    ret['title'] = self.title
    ret['kind'] = self.kind
    ret['reference'] = self.reference
    return ret


def to_dict_answer_item(self) -> dict:
    ret = dict()
    ret['title'] = self.title
    ret['kind'] = self.kind
    ret['answer'] = self.answer
    return ret


def to_dict_menu_module(self) -> dict:
    ret = dict()
    ret['name'] = self.name
    ret['kind'] = self.kind
    ret['presentation'] = self.presentation
    if self.fallback is not None:
        ret['fallback'] = self.fallback
    ret['items'] = [item.to_dict() for item in self.items]
    return {'modules': [ret]}


setattr(ResponseElement, "to_dict", to_dict_response_element)
setattr(ExecuteElement, "to_dict", to_dict_execute_element)
setattr(Action, "to_dict", to_dict_action)
setattr(ActionModule, "to_dict", to_dict_action_module)
setattr(DataGatheringModule, "to_dict", to_dict_data_gathering_module)
setattr(QuestionAnswer, "to_dict", to_dict_question_answer)
setattr(QuestionAnsweringModule, "to_dict", to_dict_question_answering_module)
setattr(SequenceItem, "to_dict", to_dict_sequence_item)
setattr(ToolItem, "to_dict", to_dict_tool_item)
setattr(AnswerItem, "to_dict", to_dict_answer_item)
setattr(MenuModule, "to_dict", to_dict_menu_module)


# --------------------------------------------------------------------------------------------
# mutation operators

class BaseMutationOperator:
    def __init__(self, chatbot_folder: str, mutants_folder: str):
        self.counter = 1
        self.name = self.__class__.__name__
        self.chatbot_folder = chatbot_folder
        self.mutants_folder = mutants_folder

    def persist(self, modules: Dict[str, Module], description: str = None):
        # copy original chatbot in output folder
        output_folder = f"{self.mutants_folder}/{self.name}_{self.counter}"
        shutil.copytree(self.chatbot_folder, output_folder)
        # overwrite received modules in output folder
        for yaml_path in modules:
            file_path = os.path.basename(yaml_path)
            with open(output_folder + '/' + file_path, 'w', encoding='utf-8') as outfile:
                yaml.dump(modules.get(yaml_path).to_dict(), outfile, default_flow_style=False, sort_keys=False)
        self.counter += 1
        # create file with description of mutation
        if description:
            with open(output_folder + '/__mutation__.txt', "w") as file:
                file.write(description)


class DeleteFallback(BaseMutationOperator):
    def generate_mutants(self, modules: Dict[str, Module]) -> None:
        for module_file, module in modules.items():
            if isinstance(module, MenuModule) and module.fallback is not None:
                fallback = module.fallback
                module.fallback = None
                self.persist(
                    {module_file: module},  # for efficiency, we only persist the mutated module
                    f"Mutated file: {module_file}\nMutation description: The fallback has been deleted"
                )
                module.fallback = fallback


class DeleteEnumDataValue(BaseMutationOperator):
    def generate_mutants(self, modules: Dict[str, Module]) -> None:
        for module_file, module in modules.items():
            if isinstance(module, (ActionModule, DataGatheringModule)):
                for data in module.data:
                    for data_name, data_value in data.items():
                        if data_value.get('type') == 'enum':
                            values = data_value.get('values')
                            for i in range(len(values)):
                                data_value['values'] = values[:i] + values[i+1:]
                                self.persist(
                                    {module_file: module},  # for efficiency, we only persist the mutated module
                                    f"Mutated file: {module_file}\nMutation description: The value '{values[i]}' has been deleted from the data enum '{data_name}'"
                                )
                            data_value['values'] = values


# --------------------------------------------------------------------------------------------


def generate_mutants(chatbot_folder: str, mutants_folder: str):
    if os.path.exists(mutants_folder):
        shutil.rmtree(mutants_folder)

    # parse yaml files in chatbot_folder
    modules = dict()
    for yaml_path in glob.glob(os.path.join(chatbot_folder, '*.yaml')):
        with open(yaml_path) as yaml_file:
            parsed_modules = parse_yaml(yaml_file.read())
            for parsed_module in parsed_modules:
                modules[yaml_path] = parsed_module

    # generate mutants
    mutation_operators = [
        DeleteFallback(chatbot_folder, mutants_folder),
        DeleteEnumDataValue(chatbot_folder, mutants_folder),
    ]
    for operator in mutation_operators:
        operator.generate_mutants(modules)


if __name__ == '__main__':
    parser = ArgumentParser(description='Runner for a chatbot')
    parser.add_argument('--chatbot', required=True, help='Path to the chatbot specification')
    parser.add_argument('--output', required=True, help='Path to store the generated chatbot mutants')
    args = parser.parse_args()
    generate_mutants(args.chatbot, args.output)
