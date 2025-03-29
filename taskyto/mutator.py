import os.path
from taskyto.spec import (ResponseElement, ExecuteElement, Action, ActionModule, DataGatheringModule, QuestionAnswer,
                  QuestionAnsweringModule, SequenceItem, ToolItem, AnswerItem, MenuModule, Module, MemoryScope,
                  SequenceModule)
from taskyto.spec import parse_yaml
import yaml
import glob
import shutil
import re
from argparse import ArgumentParser
from typing import Dict, Union
from abc import ABC, abstractmethod

# --------------------------------------------------------------------------------------------
# TODO: mutatest for python (https://mutatest.readthedocs.io/en/latest/commandline.html)

# --------------------------------------------------------------------------------------------
# "to_dict" methods for the chatbot components, to facilitate their persistence using pydantic


def to_dict_response_element(self) -> dict:
    ret = dict()
    ret['text'] = self.text
    if self.rephrase:
        ret['rephrase'] = self.rephrase
    return ret


def to_dict_execute_element(self) -> dict:
    ret = dict()
    ret['language'] = self.language
    ret['code'] = self.code
    return ret


def to_dict_action(self) -> dict:
    ret = dict()
    if self.execute:
        ret['execute'] = self.execute.to_dict()
    if self.response:
        if isinstance(self.response, ResponseElement):
            ret['response'] = self.response.to_dict()
        else:
            ret['response'] = self.response
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
    if self.on_success:
        ret['on-success'] = self.on_success.to_dict()
    return ret


def to_dict_sequence_item(self) -> dict:
    ret = dict()
    ret['title'] = self.title
    if self.memory:
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
    if self.fallback:
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

class BaseMutationOperator(ABC):
    def __init__(self, chatbot_folder: str, mutants_folder: str, max = 10000):
        self.counter = 1
        self.name = self.__class__.__name__
        self.chatbot_folder = chatbot_folder
        self.mutants_folder = mutants_folder
        self.max = max
        self.num_mutants = 0

    @abstractmethod
    def generate_mutants(self, modules: Dict[str, Module]) -> None:
        pass

    def persist(self, modules: Dict[str, Module], description: str = None) -> None:
        # copy original chatbot in output folder
        self.num_mutants += 1
        if self.num_mutants>self.max:
            return
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


class DeleteEnumDataValue(BaseMutationOperator):
    def generate_mutants(self, modules: Dict[str, Module]) -> None:
        for module_file, module in modules.items():
            if isinstance(module, (ActionModule, DataGatheringModule)):
                for data in module.data:
                    for data_name, data_value in data.items():
                        if isinstance(data_value, dict) and data_value.get('type') == 'enum':
                            values = data_value.get('values')
                            for i in range(len(values)):
                                data_value['values'] = values[:i] + values[i+1:]
                                self.persist(
                                    {module_file: module},  # for efficiency, we only persist the mutated module
                                    f"Mutated file: {module_file}\nMutation description: The value '{values[i]}' has been deleted from the data enum '{data_name}'"
                                )
                            data_value['values'] = values


class ChangeRequiredData(BaseMutationOperator):
    def generate_mutants(self, modules: Dict[str, Module]) -> None:
        for module_file, module in modules.items():
            if isinstance(module, (ActionModule, DataGatheringModule)):
                for data in module.data:
                    for data_name, data_value in data.items():
                        if isinstance(data_value, dict) and 'required' in data_value:
                            data_value['required'] = not data_value['required']
                            self.persist(
                                {module_file: module},  # for efficiency, we only persist the mutated module
                                f"Mutated file: {module_file}\nMutation description: The data '{data_name}' has changed from required={not data_value['required']} to required={data_value['required']}"
                            )
                            data_value['required'] = not data_value['required']


class DeleteQuestionAnswer(BaseMutationOperator):
    def generate_mutants(self, modules: Dict[str, Module]) -> None:
        for module_file, module in modules.items():
            if isinstance(module, QuestionAnsweringModule):
                questions = module.questions
                for i in range(len(module.questions)):
                    module.questions = questions[:i] + questions[i+1:]
                    self.persist(
                        {module_file: module},  # for efficiency, we only persist the mutated module
                        f"Mutated file: {module_file}\nMutation description: The following question/answer has been deleted\n- question: {questions[i].question}\n  answer: {questions[i].answer}"
                    )
                module.questions = questions


class SwapQuestionAnswer(BaseMutationOperator):
    """ It swaps the answer of two questions in a question-answering module """
    def generate_mutants(self, modules: Dict[str, Module]) -> None:
        for module_file, module in modules.items():
            if isinstance(module, QuestionAnsweringModule):
                questions = module.questions
                for i in range(len(module.questions)-1):
                    for j in range(i+1, len(module.questions)):
                        answer_i = module.questions[i].answer
                        answer_j = module.questions[j].answer
                        module.questions[i].answer = answer_j
                        module.questions[j].answer = answer_i
                        self.persist(
                            {module_file: module},  # for efficiency, we only persist the mutated module
                            f"Mutated file: {module_file}\nMutation description: The answer of the following questions has been swapped\n- question: {questions[i].question}\n  answer: {answer_i}\n- question: {questions[j].question}\n  answer: {answer_j}"
                        )
                        module.questions[i].answer = answer_i
                        module.questions[j].answer = answer_j
                module.questions = questions


class DeleteFallback(BaseMutationOperator):
    def generate_mutants(self, modules: Dict[str, Module]) -> None:
        for module_file, module in modules.items():
            if isinstance(module, MenuModule) and module.fallback:
                fallback = module.fallback
                module.fallback = None
                self.persist(
                    {module_file: module},  # for efficiency, we only persist the mutated module
                    f"Mutated file: {module_file}\nMutation description: The fallback has been deleted"
                )
                module.fallback = fallback


class DeleteItemTopModule(BaseMutationOperator):
    def generate_mutants(self, modules: Dict[str, Module]) -> None:
        for module_file, module in modules.items():
            if isinstance(module, MenuModule):
                items = module.items
                for i in range(len(module.items)):
                    module.items = items[:i] + items[i+1:]
                    self.persist(
                        {module_file: module},  # for efficiency, we only persist the mutated module
                        f"Mutated file: {module_file}\nMutation description: The item with the following title has been deleted: '{items[i].title}'"
                    )
                module.items = items


class DeleteSequenceStep(BaseMutationOperator):
    def generate_mutants(self, modules: Dict[str, Module]) -> None:
        for module_file, module in modules.items():
            if isinstance(module, MenuModule):
                for item in module.items:
                    if isinstance(item, SequenceItem):
                        references = item.references
                        for i in range(len(item.references)):
                            item.references = references[:i] + references[i+1:]
                            self.persist(
                                {module_file: module},  # for efficiency, we only persist the mutated module
                                f"Mutated file: {module_file}\nMutation description: The step {references[i]} has been deleted"
                            )
                        item.references = references


class SwapSequenceStep(BaseMutationOperator):
    """ It swaps the order of two steps in a sequence """
    def generate_mutants(self, modules: Dict[str, Module]) -> None:
        for module_file, module in modules.items():
            if isinstance(module, MenuModule):
                for item in module.items:
                    if isinstance(item, SequenceItem):
                        references = item.references
                        for i in range(len(item.references)-1):
                            for j in range(i+1, len(item.references)):
                                reference_i = item.references[i]
                                reference_j = item.references[j]
                                item.references[i] = reference_j
                                item.references[j] = reference_i
                                self.persist(
                                    {module_file: module},  # for efficiency, we only persist the mutated module
                                    f"Mutated file: {module_file}\nMutation description: The steps {reference_i} and {reference_j} have been swapped"
                                )
                                item.references[i] = reference_i
                                item.references[j] = reference_j
                        item.references = references


class DeleteDataFromResponse(BaseMutationOperator):
    """ Each mutant removes an expression between curly braces from a response text """
    def generate_mutants(self, modules: Dict[str, Module]) -> None:
        for module_file, module in modules.items():
            if (isinstance(module, (DataGatheringModule, ActionModule, QuestionAnsweringModule)) and
                    module.on_success and
                    isinstance(module.on_success, Action)):
                text = self.get_text(module.on_success)
                fragments = re.split(r'(\{{1,2}.*?\}{1,2})', text) # deals with 1 or 2 curly braces
                for i in range(len(fragments)):
                    if fragments[i].startswith('{') and fragments[i].endswith('}'):
                        self.set_text(module.on_success, ''.join(fragments[:i] + fragments[i+1:]))
                        self.persist(
                            {module_file: module},  # for efficiency, we only persist the mutated module
                            f"Mutated file: {module_file}\nMutation description: The expression {fragments[i]} has been removed from the text response"
                        )
                self.set_text(module.on_success, text)

    def get_text(self, action: Action) -> str:
        if isinstance(action.response, ResponseElement):
            return action.response.text
        elif isinstance(action.response, str):
            return action.response
        return ''

    def set_text(self, action: Action, new_text: str) -> None:
        if isinstance(action.response, ResponseElement):
            action.response.text = new_text
        elif isinstance(action.response, str):
            action.response = new_text


class ChangeRephrase(BaseMutationOperator):
    def generate_mutants(self, modules: Dict[str, Module]) -> None:
        for module_file, module in modules.items():
            if (isinstance(module, (DataGatheringModule, ActionModule, QuestionAnsweringModule)) and
                    module.on_success and
                    isinstance(module.on_success, Action) and
                    isinstance(module.on_success.response, ResponseElement)):
                rephrase = module.on_success.response.rephrase
                if rephrase != "direct":
                    module.on_success.response.rephrase = "direct"
                    self.persist(
                        {module_file: module},  # for efficiency, we only persist the mutated module
                        f"Mutated file: {module_file}\nMutation description: The rephrase has changed from {rephrase} to direct"
                    )
                if rephrase != "simple":
                    module.on_success.response.rephrase = "simple"
                    self.persist(
                        {module_file: module},  # for efficiency, we only persist the mutated module
                        f"Mutated file: {module_file}\nMutation description: The rephrase has changed from {rephrase} to simple"
                    )
                if rephrase != "on-caller" and rephrase != "on_caller":
                    module.on_success.response.rephrase = "on-caller"
                    self.persist(
                        {module_file: module},  # for efficiency, we only persist the mutated module
                        f"Mutated file: {module_file}\nMutation description: The rephrase has changed from {rephrase} to on-caller"
                    )
                module.on_success.response.rephrase = rephrase


class ChangeMemoryScope(BaseMutationOperator):
    def mutate(self, element_with_memory: Union[SequenceItem, SequenceModule], module_file: str, module: Module) -> None:
        if element_with_memory.memory:
            memory = element_with_memory.memory
            if element_with_memory.memory == MemoryScope.individual:
                element_with_memory.memory = MemoryScope.full
            else:
                element_with_memory.memory = MemoryScope.individual
            self.persist(
                {module_file: module},  # for efficiency, we only persist the mutated module
                f"Mutated file: {module_file}\nMutation description: The memory has changed from {memory} to {element_with_memory.memory} for the sequence with title '{element_with_memory.title}'"
            )
            element_with_memory.memory = memory

    def generate_mutants(self, modules: Dict[str, Module]) -> None:
        for module_file, module in modules.items():
            if isinstance(module, MenuModule):
                for item in module.items:
                    if isinstance(item, SequenceItem):
                        self.mutate(item, module_file, module)
            elif isinstance(module, SequenceModule):
                self.mutate(module, module_file, module)

# --------------------------------------------------------------------------------------------


def generate_mutants(chatbot_folder: str, mutants_folder: str, max):
    if not os.path.exists(chatbot_folder):
        print(f"The folder {chatbot_folder} does not exist")
        exit(1)

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
        DeleteEnumDataValue(chatbot_folder, mutants_folder, max),
        ChangeRequiredData(chatbot_folder, mutants_folder, max),
        DeleteQuestionAnswer(chatbot_folder, mutants_folder, max),
        SwapQuestionAnswer(chatbot_folder, mutants_folder, max),
        DeleteFallback(chatbot_folder, mutants_folder, max),
        DeleteItemTopModule(chatbot_folder, mutants_folder, max),
        DeleteSequenceStep(chatbot_folder, mutants_folder, max),
        SwapSequenceStep(chatbot_folder, mutants_folder, max),
        DeleteDataFromResponse(chatbot_folder, mutants_folder, max),
        ChangeRephrase(chatbot_folder, mutants_folder, max),
        ChangeMemoryScope(chatbot_folder, mutants_folder, max),
    ]
    for operator in mutation_operators:
        operator.generate_mutants(modules)


if __name__ == '__main__':
    parser = ArgumentParser(description='Runner for a chatbot')
    parser.add_argument('--chatbot', required=True, help='Path to the chatbot specification')
    parser.add_argument('--output', required=True, help='Path to store the generated chatbot mutants')
    parser.add_argument('--max', required=False, type=int, default=10000, help='Max number of mutants per type')
    args = parser.parse_args()
    generate_mutants(args.chatbot, args.output, args.max)
