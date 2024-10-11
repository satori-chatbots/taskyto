import os

from langchain import hub
from langchain_chroma import Chroma
from langchain_community.document_loaders import WebBaseLoader
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

class Indexer:

    def __init__(self, documents):
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        splits = text_splitter.split_documents(documents)

        # shalomma/llama-7b-embeddings
        embedding = self._get_embedding()
        persist_dir = os.path.expanduser("~/.taskyto/chroma")
        vectorstore = Chroma.from_documents(documents=splits, embedding=embedding,
                                            persist_directory=persist_dir)

        # Retrieve and generate using the relevant snippets of the blog.
        retriever = vectorstore.as_retriever()
        prompt = hub.pull("rlm/rag-prompt")

        def format_docs(docs):
            return "\n\n".join(doc.page_content for doc in docs)

        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(model="gpt-4o-mini")

        self.rag_chain = (
                {"context": retriever | format_docs, "question": RunnablePassthrough()}
                | prompt
                | llm
                | StrOutputParser()
        )

    def _get_embedding(self):
        return OpenAIEmbeddings()
        # return _get_hf_embedding()

    def _get_hf_embedding(self):
        from langchain_huggingface import HuggingFaceEmbeddings

        #model_name = "sentence-transformers/all-mpnet-base-v2"
        model_name = "shalomma/llama-7b-embeddings"
        model_kwargs = {'device': 'cpu'}
        encode_kwargs = {'normalize_embeddings': False}
        hf = HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs=model_kwargs,
            encode_kwargs=encode_kwargs
        )

        return hf

    def query(self, text):
        return self.rag_chain.invoke(text)