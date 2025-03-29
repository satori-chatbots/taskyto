import os
from typing import List


class Extension:
    def __init__(self, extension_module, name, type, extension_args: dict):
        self.extension_module = extension_module
        self.name = name
        self.type = type
        self.arguments = extension_args

    def __call__(self, **kwargs):
        all_arguments = {**self.arguments, **kwargs}
        return self.extension_module.invoke(**all_arguments)

class OllamaExtension(Extension):

    def __init__(self, name, type, extension_args: dict):
        import extensions.ollama_extension as ollama_extension
        super().__init__(ollama_extension, name, type, extension_args)
        self.host = extension_args['host']
        self.model = extension_args['model']
        if self.host is None or self.model is None:
            raise Exception("Ollama extension requires a host and a model")

    def __call__(self, **kwargs):
        input_ = kwargs['input']
        stop = kwargs.get('stop', [])
        return self.extension_module.invoke_ollama(input_, self.host, self.model, stop=stop)

class ExtensionLoader:

    def __init__(self, module_path: List[str]):
        self.module_path = module_path
        self.extensions = []

    def load(self, file, extension_args : dict, type) -> Extension:
        # Check "hardcoded" extensions first
        if file == 'ollama':
            return OllamaExtension(file, type, extension_args)

        for folder in self.module_path:
            filepath = os.path.join(folder, file)
            if os.path.isfile(filepath):
                return self._do_load(filepath, extension_args, type)
        return None

    def _do_load(self, filepath, extension_args: dict, type):
        import importlib
        import sys
        sys.path.append(os.path.dirname(filepath))
        extension_module = importlib.import_module('llm')
        return Extension(extension_module, filepath, type, extension_args)
