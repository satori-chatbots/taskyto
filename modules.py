from abc import ABC, abstractmethod

from langchain import OpenAI
from langchain.agents import ConversationalAgent, AgentExecutor
from langchain.memory import ConversationBufferMemory


class State:

    def __init__(self, llm):
        self.logged_user = None
        self.current_chain = None
        self.active_modules = []

        self.memory = ConversationBufferMemory(memory_key="chat_history")
        self.llm = llm

    def push_module(self, a_module):
        self.current_chain = a_module.get_chain()
        self.active_modules.append(a_module)

    def pop_module(self):
        self.active_modules.pop()

    def current_module(self):
        return self.active_modules[-1]

    def is_module_active(self, cls_or_obj):
        import inspect
        if inspect.isclass(cls_or_obj):
            return isinstance(self.active_modules[-1], cls_or_obj)
        return self.active_modules[-1] == cls_or_obj

    def log_user(self, name: str):
        self.logged_user = name

    def get_chain(self):
        return self.current_chain


class ChatbotModule(ABC):
    def __init__(self, state: State):
        self.state = state

    @abstractmethod
    def get_prompt(self):
        pass

    @abstractmethod
    def get_tools(self):
        pass

    def get_chain(self):
        prefix = self.get_prompt()
        tools = self.get_tools()
        llm = self.state.llm
        memory = self.state.memory

        memory = ConversationBufferMemory(memory_key="chat_history")

        agent = ConversationalAgent.from_llm_and_tools(llm=llm, tools=tools, memory=memory, prefix=prefix,
                                                       verbose=True)
        chain = AgentExecutor.from_agent_and_tools(
            agent=agent,
            tools=tools,
            memory=memory,
            verbose=True
        )

        return chain
