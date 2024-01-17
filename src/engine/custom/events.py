import abc

import spec
from engine.custom.statemachine import TriggerEventMatchByClass, TriggerEvent


class Event(abc.ABC):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def has_property_value(self, name):
        return name in self.__dict__

    def get_property_value(self, name):
        value = self.__dict__[name]
        assert value is not None
        return value

class ActivateModuleEventType(TriggerEvent):
    def __init__(self, module: spec.Module):
        self.module = module

    def is_compatible(self, event):
        return isinstance(event, ActivateModuleEvent) and event.module.module == self.module

    def __str__(self):
        return f"ActivateModule({self.module.name})"

class ActivateModuleEvent(Event):

    def __init__(self, module: spec.Module, input: str, previous_answer: "MemoryPiece"):
        self.module = module
        self.input = input
        self.previous_answer = previous_answer

    def __str__(self):
        return f"ActivateModule({self.module.name()}, {self.input})" #, {self.previous_answer})"

class AIResponseEvent(Event):

    def __init__(self, message: str):
        self.message = message


AIResponseEventType = TriggerEventMatchByClass(AIResponseEvent)


class UserInput(Event):

    def __init__(self, message):
        self.message = message


UserInputEventType = TriggerEventMatchByClass(UserInput)


class TaskInProgressEvent(Event):

    def __init__(self, memory: dict):
        self.memory = memory


TaskInProgressEventType = TriggerEventMatchByClass(TaskInProgressEvent)


class TaskFinishEvent(Event):

    def __init__(self, message, memory: dict = {}, **kwargs):
        super().__init__(**kwargs)
        self.message = message
        self.memory = memory


TaskFinishEventEventType = TriggerEventMatchByClass(TaskFinishEvent)
