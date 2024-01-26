import os
from typing import List


class Extension:
    def __init__(self, extension_module, name, type):
        self.extension_module = extension_module
        self.name = name
        self.type = type
        # This are specific arguments depending on the type of the extension
        self.arguments = {}

    def __call__(self, **kwargs):
        all_arguments = {**self.arguments, **kwargs}
        return self.extension_module.invoke(**all_arguments)


class ExtensionLoader:

    def __init__(self, module_path: List[str]):
        self.module_path = module_path
        self.extensions = []

    def load(self, file, type) -> Extension:
        for folder in self.module_path:
            filepath = os.path.join(folder, file)
            if os.path.isfile(filepath):
                return self._do_load(filepath, type)
        return None

    def _do_load(self, filepath, type):
        import importlib
        import sys
        sys.path.append(os.path.dirname(filepath))
        extension_module = importlib.import_module('llm')
        return Extension(extension_module, filepath, type)
