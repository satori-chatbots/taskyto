import abc
from abc import ABC, abstractmethod, ABCMeta
from typing import Optional

import networkx as nx

import spec
from engine.common.evaluator import Evaluator

class DebugInfo:
    def __init__(self, current_module: str):
        self.current_module = current_module
        self.executed_tool = None


class ChatbotResult:
    def __init__(self, chatbot_msg: str, debug_info: DebugInfo):
        self.chatbot_msg = chatbot_msg
        self.debug_info = debug_info


class Configuration(abc.ABC):
    """Provides methods to create the components of the chatbot engine."""

    @abstractmethod
    def new_channel(self):
        raise NotImplementedError()

    @abstractmethod
    def new_engine(self):
        raise NotImplementedError()

    @abstractmethod
    def new_evaluator(self):
        raise NotImplementedError()

    @abstractmethod
    def new_llm(self, module_name: Optional[str] = None):
        """For now, the LLM follows Langchain BaseChatModel basic interface: __call__. This will probably change."""
        raise NotImplementedError()

    @abstractmethod
    def new_rephraser(self):
        raise NotImplementedError()


class BasicConfiguration(Configuration, metaclass=ABCMeta):
    "A basic configuration for the most commonly used components"

    def __init__(self, root_folder):
        self.chatbot_model = spec.load_chatbot_model(root_folder)
        self.root_folder = root_folder

    def new_evaluator(self):
        return Evaluator(load_path=[self.root_folder])


class Rephraser(abc.ABC):
    def __init__(self, configuration: Configuration):
        self.configuration = configuration

    def __call__(self, *args, **kwargs):
        return self.rephrase(*args, **kwargs)

    @abstractmethod
    def rephrase(self, message: str, context: Optional[str] = None):
        raise NotImplementedError()


# TODO: Find out which the right interface for an engine
#       For the moment, we assume that everything follows CustomPromptEngine
class Engine(ABC):
    pass


def get_property_value(p: spec.DataProperty, data):
    value = data.get(p.name)
    if value is None:
        return None

    # If type is string but the value is not str, we should somehow tell the chatbot that there is an issue
    # or perhaps we may need to convert the value to str
    if p.type == 'string':
        if isinstance(value, str):
            value = value.strip()
        elif isinstance(value, int) or isinstance(value, float) or isinstance(value, bool):
            value = str(value)
        else:
            return None

        if value == "":
            return None
    elif p.type == 'int' or p.type == 'integer':
        if isinstance(value, int):
            return value
        elif isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return None
        else:
            return None
    elif p.type == 'number' or p.type == 'float' or p.type == 'double':
        if isinstance(value, float):
            return value
        elif isinstance(value, str) or isinstance(value, int):
            try:
                return float(value)
            except ValueError:
                return None
        else:
            return None
    else:
        # TODO: Handle more types explicitly like date, enum, etc.
        # For the moment, just convert them to strings and check that at least they are not empty
        str_value = str(value)
        if len(str_value.strip()) == 0:
            return None

    return value


def replace_values(response, data):
    for k, v in data.items():
        # Handle both {{ }} and { }
        response = response.replace("{{" + k + "}}", str(v))
        response = response.replace("{" + k + "}", str(v))
    return response


def compute_init_module(chatbot_model: spec.ChatbotModel) -> spec.Item:
    g = nx.DiGraph()
    chatbot_model.to_graph(g)
    sorted_modules = list(nx.topological_sort(g))
    init = sorted_modules[0]
    return init
