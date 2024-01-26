from typing import List, Any, Union, Optional

import pydantic
from pydantic import BaseModel, Field, ConfigDict

from engine.common.llm import LLM, OpenAILLM, ExtensionLLM
from extensions.extension import ExtensionLoader

from utils import parse_obj_as_


class LLMConfiguration(BaseModel):
    id: str
    temperature: float = 0.0


class ModuleConfiguration(BaseModel):
    name: str
    llm: Union[LLMConfiguration, str]

class ConversationStart(BaseModel):
    with_: Optional[str] = Field(alias="with")
    greeting: Optional[Union[str, List[str]]] = Field(alias="greeting", default="Hello")

class LLMService(BaseModel):
    name: str
    extension: str
    """The path to the folder containing the extension. This should be in the module_path."""
    args: dict


class ConfigurationModel(BaseModel):
    # To allow extension_loader
    model_config = ConfigDict(arbitrary_types_allowed=True)

    llm_services: List[LLMService] = []
    default_llm: Union[LLMConfiguration, str]
    languages: str = "any"
    modules: List[ModuleConfiguration] = []
    begin: Optional[ConversationStart] = None

    extension_loader: Optional[ExtensionLoader] = None

    def set_module_path(self, module_path: List[str]):
        if self.extension_loader is None:
            self.extension_loader = ExtensionLoader(module_path)
        else:
            self.extension_loader.module_path = module_path

    def get_llm_for_module_or_default(self, module_name: str) -> LLM:
        config = self._get_config_for_module_or_default(module_name)
        return self._create_llm(config)

    def _create_llm(self, config: LLMConfiguration) -> LLM:
        for service in self.llm_services:
            if service.name == config.id:
                return ExtensionLLM(self._create_llm_from_service(service))

        # Return this as a default, but we should possibly raise an exception if the model name is valid
        return OpenAILLM(model_name=config.id, temperature=config.temperature)

    def _get_config_for_module_or_default(self, module_name: str) -> LLMConfiguration:
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

    def _create_llm_from_service(self, service: LLMService) -> LLM:
        extension = self.extension_loader.load(service.extension, "llm")
        extension.arguments = service.args
        if extension is None:
            raise Exception("LLM extension not found: " + service.extension)
        return extension


# This is to imitate parse_obj_as but without warnings
def parse_obj_as_(type_: type, obj: Any):
    return pydantic.type_adapter.TypeAdapter(type_).validate_python(obj)


def read_configuration(configuration_file: str, module_path: List[str] = []) -> ConfigurationModel:
    import yaml
    with open(configuration_file) as yaml_file:
        data = yaml.safe_load(yaml_file.read())
        config = parse_obj_as_(ConfigurationModel, data)
        config.set_module_path(module_path)
        return config
