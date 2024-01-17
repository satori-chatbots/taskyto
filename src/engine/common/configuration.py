from typing import List, Any, Union

import pydantic
from pydantic import BaseModel, Field


class LLMConfiguration(BaseModel):
    id: str
    temperature: float = 0.0

class ModuleConfiguration(BaseModel):
    name: str
    llm: Union[LLMConfiguration, str]


class ConfigurationModel(BaseModel):
    default_llm: Union[LLMConfiguration, str]
    languages: str = "any"
    modules: List[ModuleConfiguration] = []

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


# This is to imitate parse_obj_as but without warnings
def parse_obj_as_(type_: type, obj: Any):
    return pydantic.type_adapter.TypeAdapter(type_).validate_python(obj)


def read_configuration(configuration_file: str) -> ConfigurationModel:
    import yaml
    with open(configuration_file) as yaml_file:
        data = yaml.safe_load(yaml_file.read())
        return parse_obj_as_(ConfigurationModel, data)
