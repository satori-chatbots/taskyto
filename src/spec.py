import abc
import glob
import os
from abc import abstractmethod
from enum import Enum

import pydantic
from pydantic import BaseModel, Field
from typing import List, Any, Optional
from typing import Literal, Union, Annotated
import networkx as nx


class Visitor(abc.ABC):
    pass


class Visitable:
    @abstractmethod
    def accept(self, visitor: Visitor) -> object:
        pass


class BaseItem(BaseModel):
    title: str

    def __hash__(self):
        return hash(self.title)

    def __eq__(self, other):
        return self.title == other.title

    def __cmp__(self, other):
        return self.title == other.title


class AnswerItem(BaseItem):
    kind: Literal["answer"] = "answer"
    answer: str

    def accept(self, visitor: Visitor) -> object:
        return visitor.visit_answer_item(self)


class ToolItem(BaseItem):
    kind: Literal["module"] = "module"
    reference: str

    def accept(self, visitor: Visitor) -> object:
        return visitor.visit_tool_item(self)


class MemoryScope(str, Enum):
    full = 'full'
    individual = 'individual'


class SequenceItem(BaseItem):
    kind: Literal["sequence"] = "sequence"
    memory: MemoryScope = MemoryScope.individual
    goback: bool = True
    references: List[str]

    impl_module: "SequenceModule" = None

    def get_sequence_module(self):
        if self.impl_module is None:
            module_name = f"sequence-{'-'.join(self.references)}"
            self.impl_module = SequenceModule(name=module_name, description=self.title, references=self.references, memory=self.memory)
        return self.impl_module

    def accept(self, visitor: Visitor) -> object:
        return visitor.visit_sequence_item(self)


Item = Annotated[Union[ToolItem, AnswerItem, SequenceItem], Field(discriminator='kind')]


# https://typethepipe.com/post/pydantic-discriminated-union/
# Alternative: https://docs.pydantic.dev/dev-v1/usage/types/#discriminated-unions-aka-tagged-unions
class BaseModule(BaseModel):
    name: str

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        return self.name == other.name

    def __cmp__(self, other):
        return self.name == other.name

    @abstractmethod
    def to_graph(self, g: nx.Graph):
        pass


class MenuModule(BaseModule):
    kind: Literal["menu"] = "menu"

    presentation: str
    fallback: Optional[str] = None
    items: List[Item]

    def to_graph(self, g: nx.Graph, chatbot_model: "ChatbotModel"):
        g.add_node(self)
        for item_ in self.items:
            if isinstance(item_, ToolItem):
                resolved_module = chatbot_model.resolve_module(item_.reference)
                g.add_edge(self, resolved_module)
            elif isinstance(item_, SequenceItem):
                seq = item_.get_sequence_module()
                seq.to_graph(g, chatbot_model)
                g.add_edge(self, seq)

    def accept(self, visitor: Visitor) -> object:
        return visitor.visit_menu_module(self)

class SequenceModule(BaseModule):
    kind: Literal["sequence"] = "sequence"
    references: List[str]
    memory: MemoryScope = MemoryScope.individual
    goback: bool = True
    description: str = None  # should this be merged with presentation?

    def to_graph(self, g: nx.Graph, chatbot_model: "ChatbotModel"):
        g.add_node(self)
        for reference in self.references:
            resolved_module = chatbot_model.resolve_module(reference)
            g.add_edge(self, resolved_module)
        # This is not exactly correct, because we should generate a sequence of edges...

    def accept(self, visitor: Visitor) -> object:
        return visitor.visit_sequence_module(self)

class EnumValue(BaseModel):
    name: str
    examples: List[str] = []

class DataProperty(BaseModel):
    name: str
    type: str
    values: Optional[List[EnumValue]] = None
    required: Optional[bool] = True
    examples: Optional[List[str]] = []

    def is_simple_type(self):
        return self.type != "enum"

    @property
    def is_optional(self):
        return not self.required

class DataSpecification(BaseModel):
    properties: List[DataProperty]


class ExecuteElement(BaseModel):
    language: str
    code: str


class ResponseElement(BaseModel):
    text: str
    rephrase: Optional[str] = None

    def is_direct_response(self):
        return self.rephrase is None or self.rephrase == "direct"

    def is_simple_rephrase(self):
        return self.rephrase == "simple"

    def is_in_caller_rephrase(self):
        return self.rephrase == "in-caller" or self.rephrase == "in_caller"


class Action(BaseModel):
    execute: Optional[ExecuteElement] = None
    response: Union[str, ResponseElement]

    def get_response_element(self) -> ResponseElement:
        if isinstance(self.response, str):
            return ResponseElement(text=self.response, rephrase=None)
        else:
            return self.response


class WithDataModel(abc.ABC):

    def parse_data_model(self):
        properties = []
        # print(self.data)
        for d in self.data:
            for name, type in d.items():
                if isinstance(type, dict):
                    property = self.parse_type_specification(name, type)
                    properties.append(property)
                else:
                    properties.append(DataProperty(name=name, type=type))

        return DataSpecification(properties=properties)

    def parse_type_specification(self, name, type_dict: dict):
        if "type" not in type_dict:
            raise ValueError(f"Type specification should contain a type: {type_dict}")

        type_ = type_dict["type"]
        required = type_dict.get("required", True)
        examples = type_dict.get("examples", [])

        if type_ == "enum":
            values = type_dict["values"]
            # Traverse values and convert them to EnumValue
            values = [EnumValue(name=v, examples=[])
                      if isinstance(v, str)
                      else EnumValue(name=next(iter(v.keys())), examples=next(iter(v.values())))
                      for v in values]
            return DataProperty(name=name, type="enum", values=values, required=required)

        return DataProperty(name=name, type=type_, required=required, examples=examples)


class DataGatheringModule(BaseModule, WithDataModel):
    kind: Literal["data_gathering"] = "data_gathering"
    data: list
    data_model: DataSpecification = None

    description: str = None  # should this be merged with presentation?

    on_success: Action = Field(alias="on-success", default=None)

    def __init__(self, **data: Any):
        super().__init__(**data)
        self.data_model = self.parse_data_model()

    def to_graph(self, g: nx.Graph, chatbot_model: "ChatbotModel"):
        g.add_node(self)

    def accept(self, visitor: Visitor) -> object:
        return visitor.visit_data_gathering_module(self)


class ActionModule(BaseModule, WithDataModel):
    kind: Literal["action"] = "action"
    data: list
    data_model: DataSpecification = None

    on_success: Action = Field(alias="on-success", default=None)

    def __init__(self, **data: Any):
        super().__init__(**data)
        self.data_model = self.parse_data_model()

    def to_graph(self, g: nx.Graph, chatbot_model: "ChatbotModel"):
        pass

    def accept(self, visitor: Visitor) -> object:
        return visitor.visit_action_module(self)


class QuestionAnswer(BaseModel):
    question: str
    answer: str


class QuestionAnsweringModule(BaseModule):
    kind: Literal["question_answering"] = "question_answering"
    questions: List[QuestionAnswer]
    description: str

    on_success: Action = Field(alias="on-success", default=None)

    def to_graph(self, g: nx.Graph, chatbot_model: "ChatbotModel"):
        pass

    def accept(self, visitor: Visitor) -> object:
        return visitor.visit_question_answering_module(self)


Module = Annotated[
    Union[MenuModule, DataGatheringModule, QuestionAnsweringModule, SequenceModule, ActionModule], Field(
        discriminator='kind')]


class ChatbotModel(BaseModel):
    modules: List[Module]
    _modules_by_name: object = None

    def modules_by_name(self):
        if self._modules_by_name is None:
            self._modules_by_name = {m.name: m for m in self.modules}
        return self._modules_by_name

    def to_graph(self, g: nx.Graph):
        for m in self.modules:
            m.to_graph(g, self)

    def accept(self, visitor: Visitor) -> object:
        return visitor.visit_chatbot_model(self)

    def resolve_module(self, reference) -> Module:
        resolved_module = self.modules_by_name()[reference]
        if resolved_module is None:
            raise ValueError(f"Module {reference} not found")
        return resolved_module


# This is to imitate parse_obj_as but without warnings
def parse_obj_as_(type_: type, obj: Any):
    return pydantic.type_adapter.TypeAdapter(type_).validate_python(obj)


def parse_yaml(yaml_str) -> List[Module]:
    import yaml
    data = yaml.safe_load(yaml_str)
    if "modules" in data:
        return [parse_obj_as_(Module, m) for m in data["modules"]]
    else:
        return [parse_obj_as_(Module, data)]


def load_chatbot_model(chatbot_folder_or_file: str):
    modules = []
    if chatbot_folder_or_file.endswith(".yaml"):
        with open(chatbot_folder_or_file) as yaml_file:
            parsed_modules = parse_yaml(yaml_file.read())
            modules.extend(parsed_modules)
    else:
        # Read yaml files in chatbot_folder
        for yaml_path in glob.glob(os.path.join(chatbot_folder_or_file, '*.yaml')):
            with open(yaml_path) as yaml_file:
                parsed_modules = parse_yaml(yaml_file.read())
                modules.extend(parsed_modules)

    model = ChatbotModel(modules=modules)
    return model
