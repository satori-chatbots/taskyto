from langchain_community.document_loaders import PyPDFLoader

from taskyto.engine.common import Configuration


class InputLoader:
    def __init__(self, input_files, configuration: Configuration):
        self.input_files = input_files
        self.configuration = configuration

    def load_data(self):
        documents = []
        for f in self.input_files:
            loader = PyPDFLoader(f)
            docs = loader.load()
            documents.extend(docs)

        return documents

    # TODO:
    # Storing the index: https://docs.llamaindex.ai/en/stable/understanding/storing/storing/
