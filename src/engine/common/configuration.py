from typing import List, Any, Union, Optional

import pydantic
from pydantic import BaseModel, Field

from utils import parse_obj_as_


class LLMConfiguration(BaseModel):
    id: str
    temperature: float = 0.0

class ModuleConfiguration(BaseModel):
    name: str
    llm: Union[LLMConfiguration, str]

class ConversationStart(BaseModel):
    with_: str = Field(alias="with")
    greeting: Union[str, List[str]]

class ConfigurationModel(BaseModel):
    default_llm: Union[LLMConfiguration, str]
    languages: str = "any"
    modules: List[ModuleConfiguration] = []
    begin: Optional[ConversationStart] = None

    def get_llm_for_module_or_default(self, module_name: str) -> LLMConfiguration:
        for module in self.modules:
            if module.name == module_name:
                return ConfigurationModel.__to_llm_config(module.llm)
        return ConfigurationModel.__to_llm_config(self.default_llm)

    @staticmethod
    def __to_llm_config(llm_config: Union[LLMConfiguration, str]) -> LLMConfiguration:
        if isinstance(llm_config, str):
            return LLMConfiguration(id=llm_config, temperature=0.0)
        else:
            return llm_config


def read_configuration(configuration_file: str) -> ConfigurationModel:
    import yaml
    with open(configuration_file) as yaml_file:
        data = yaml.safe_load(yaml_file.read())
        return parse_obj_as_(ConfigurationModel, data)
