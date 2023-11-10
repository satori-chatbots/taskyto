from abc import ABC, abstractmethod

import networkx as nx

import spec


class DebugInfo:
    def __init__(self, current_module: str):
        self.current_module = current_module


class ChatbotResult:
    def __init__(self, chatbot_msg: str, debug_info: DebugInfo):
        self.chatbot_msg = chatbot_msg
        self.debug_info = debug_info


class Configuration:
    @abstractmethod
    def new_state(self):
        pass

    @abstractmethod
    def new_evaluator(self):
        raise NotImplementedError()

class Engine(ABC):
    @abstractmethod
    def first_action(self) -> ChatbotResult:
        pass

    @abstractmethod
    def run_step(self, message: str) -> ChatbotResult:
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
    else:
        # TODO: Handle more types explicitly like date, enum, etc.
        # For the moment, just convert them to strings and check that at least they are not empty
        value = str(value)
        if len(value.strip()) == 0:
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
