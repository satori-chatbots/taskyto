import abc
from abc import abstractmethod

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


Item = Annotated[Union[ToolItem, AnswerItem], Field(discriminator='kind')]


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

    def accept(self, visitor: Visitor) -> object:
        return visitor.visit_menu_module(self)



class DataProperty(BaseModel):
    name: str
    type: str
    values: List[str] = None

    def is_simple_type(self):
        return self.type != "enum"


class DataSpecification(BaseModel):
    properties: List[DataProperty]

class ExecuteElement(BaseModel):
    language: str
    code: str

class Action(BaseModel):
    execute: Optional[ExecuteElement] = None
    response: str


class DataGatheringModule(BaseModule):
    kind: Literal["data_gathering"] = "data_gathering"
    data: list
    data_model: DataSpecification = None

    description: str = None  # should this be merged with presentation?

    on_success: Action = Field(alias="on-success", default=None)

    def __init__(self, **data: Any):
        super().__init__(**data)
        self.data_model = self.parse_data_model()

    def parse_data_model(self):
        properties = []
        # print(self.data)
        for d in self.data:
            for name, type in d.items():
                if isinstance(type, dict):
                    if "type" in type and type["type"] == "enum":
                        properties.append(DataProperty(name=name, type="enum", values=type["values"]))
                    else:
                        raise ValueError(f"Unknown type: {type}")
                else:
                    properties.append(DataProperty(name=name, type=type))

        return DataSpecification(properties=properties)

    def to_graph(self, g: nx.Graph, chatbot_model: "ChatbotModel"):
        pass


    def accept(self, visitor: Visitor) -> object:
        return visitor.visit_data_gathering_module(self)


class QuestionAnswer(BaseModel):
    question: str
    answer: str

class QuestionAnsweringModule(BaseModule):
    kind: Literal["question_answering"] = "question_answering"
    questions: List[QuestionAnswer]
    description: str

    def to_graph(self, g: nx.Graph, chatbot_model: "ChatbotModel"):
        pass


    def accept(self, visitor: Visitor) -> object:
        return visitor.visit_question_answering_module(self)


Module = Annotated[Union[MenuModule, DataGatheringModule, QuestionAnsweringModule], Field(discriminator='kind')]


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
        visitor.visit_chatbot_model(self)

    def resolve_module(self, reference) -> Module:
        resolved_module = self.modules_by_name()[reference]
        if resolved_module is None:
            raise ValueError(f"Module {reference} not found")
        return resolved_module


def parse_yaml(yaml_str) -> List[Module]:
    import yaml
    data = yaml.safe_load(yaml_str)
    if "modules" in data:
        return [pydantic.parse_obj_as(Module, m) for m in data["modules"]]
    else:
        return [pydantic.parse_obj_as(Module, data)]


# Example YAML data
yaml_data = """
module:
    name: top-level
    kind: menu
    presentation: |
        You are a chatbot which helps users of a bike shop.
    fallback: |
        For any question not related to these aspects you have to answer:
        "I'm sorry it's a little loud in my shop, can you say that again?"
    items:
        - title: Hours
          answer: every weekday from 9am to 5:30pm
        - title: Make Appointment
          tool: make-appointment
        - title: Welcome
"""

if __name__ == '__main__':
    # Parse YAML data into Python objects
    module = parse_yaml(yaml_data)

    # Access the parsed data
    print(f"Module Name: {module.name}")
    print(f"Module Kind: {module.kind}")
    print(f"Module Presentation: {module.presentation}")
    print(f"Module Fallback: {module.fallback}")

    for item in module.items:
        print(f"Item Title: {item.title}")
        if item.answer:
            print(f"Item Answer: {item.answer}")
        if item.tool:
            print(f"Item Tool: {item.tool}")
