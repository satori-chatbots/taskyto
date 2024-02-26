import abc
from typing import List, Optional, Union

from pydantic import BaseModel, Field
import time


class Message(BaseModel, abc.ABC):
    timestamp: float = Field(default_factory=lambda: time.time())
    message: str

    @abc.abstractmethod
    def prefix(self) -> str:
        raise NotImplementedError()


class HumanMessage(Message):

    def prefix(self) -> str:
        return "Human: "

    @property
    def memory_type(self) -> str:
        return "human"


class DataMessage(Message):

    def prefix(self) -> str:
        return ""

    @property
    def memory_type(self) -> str:
        return "data"


class InstructionMessage(Message):

    def prefix(self) -> str:
        return "Instruction: "

    @property
    def memory_type(self) -> str:
        return "instruction"


class AIMessage(Message):
    pass


class AIReasoningMessage(AIMessage):

    def prefix(self) -> str:
        return ""

    @property
    def memory_type(self) -> str:
        return "ai_reasoning"


class AIResponse(AIMessage):

    def prefix(self) -> str:
        return "AI: "

    @property
    def memory_type(self) -> str:
        return "ai_response"


class ConversationMemory(BaseModel):
    """Conversation memory model."""

    messages: List[Message] = []

    def add_memory(self, memory_piece: "MemoryPiece"):
        # Append memory_piece.messages to self.messages but keep only the last one of InstructionMessage,
        # and append the rest of messages types
        for m in memory_piece.messages:
            if isinstance(m, InstructionMessage):
                self.messages = [i for i in self.messages if not isinstance(i, InstructionMessage)]
                self.messages.append(m)
            elif isinstance(m, DataMessage):
                self.messages = [i for i in self.messages if not isinstance(i, DataMessage)]
                self.messages.append(m)
            else:
                self.messages.append(m)

        self.__normalize_messages()

    def copy_memory_from(self, other_memory: "ConversationMemory", filter=None):
        to_be_copied = other_memory.messages
        if filter is not None:
            to_be_copied = [m for m in to_be_copied if m.__class__ in filter]

        self.messages = self.messages + to_be_copied
        self.__normalize_messages()

    # TODO: This should be done as we insert messages, but for the moment the number of messages is expected
    #  to be small so it's ok to do this at the end which is easier
    def __normalize_messages(self):
        self.messages = sorted(self.messages, key=lambda x: x.timestamp)
        self.messages = [self.messages[i] for i in range(len(self.messages)) if
                         i == 0 or self.messages[i].timestamp != self.messages[i - 1].timestamp]

    def add_data_message(self, message: str):
        self.messages.append(DataMessage(message=message))
        return self

    def add_instruction_message(self, message: str):
        self.messages.append(InstructionMessage(message=message))
        return self

    def add_human_message(self, message: str):
        self.messages.append(HumanMessage(message=message))
        return self

    def add_ai_reasoning_message(self, message: str):
        self.messages.append(AIReasoningMessage(message=message))
        return self

    def add_ai_response(self, message: str):
        self.messages.append(AIResponse(message=message))
        return self

    def to_text_messages(self, memory_types: Union[List[str], str] = 'default') -> str:
        text = ""
        last_type = None
        for m in self.messages:
            if isinstance(memory_types, list) and m.memory_type not in memory_types:
                continue

            if m.memory_type != last_type:
                last_type = m.memory_type

            text += m.prefix() + m.message + "\n"
        return text


class MemoryPiece(ConversationMemory):
    pass
