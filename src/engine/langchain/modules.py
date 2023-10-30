from abc import ABC, abstractmethod
from typing import Callable, Optional

from langchain.agents import ConversationalAgent, AgentExecutor
from langchain.memory import ConversationBufferMemory


class State:

    def __init__(self, llm):
        self.logged_user = None
        self.active_chains = []
        self.active_modules = []

        self.memory = ConversationBufferMemory(memory_key="chat_history")
        self.llm = llm

    def push_module(self, a_module):
        self.active_chains.append(a_module.get_chain())
        self.active_modules.append(a_module)

    def pop_module(self, response: Optional[str] = None) -> Optional[str]:
        self.active_chains.pop()
        mod = self.active_modules.pop()
        if response is not None:
            return mod.finished(response)
        return None

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
        return self.active_chains[-1]


class ChatbotModule(ABC):

    def __init__(self, state: State):
        self.state = state
        self.on_finish = []  # List[Callable[[str], str]] = []

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

    def on_finish(self, handler: Callable[[str], str]):
        self.on_finish.append(handler)

    def finished(self, result: str) -> str:
        for handler in self.on_finish:
            result = handler(result)
        return result
