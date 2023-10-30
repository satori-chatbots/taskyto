from abc import abstractmethod
from typing import Optional, List, Callable

import langchain
import networkx as nx
from langchain.callbacks.manager import CallbackManagerForToolRun
from langchain.tools import BaseTool

import modules
import spec
from eval import eval_code
from recording import RecordedInteraction
from spec import ChatbotModel, Visitor


class Configuration:
    @abstractmethod
    def new_state(self):
        pass


class DebugInfo:
    def __init__(self, current_module: str):
        self.current_module = current_module


class ChatbotResult:
    def __init__(self, chatbot_msg: str, debug_info: DebugInfo):
        self.chatbot_msg = chatbot_msg
        self.debug_info = debug_info


class RuntimeChatbotModule(modules.ChatbotModule):

    def __init__(self, module: spec.Module, state, prompt: str, tools):
        super().__init__(state)
        self.prompt = prompt
        self.tools = tools
        self.spec_module = module

    @property
    def name(self):
        return self.spec_module.name

    def get_prompt(self):
        return self.prompt

    def get_tools(self):
        return self.tools


def get_property_value(p: spec.DataProperty, data):
    value = data.get(p.name)
    if value is None:
        return None

    # If type is string but the value is not str, we should somehow tell the chatbot that there is an issue
    # or perhaps we may need to convert the value to str
    if p.type == 'string':
        if isinstance(value, str):
            value = value.strip()
        elif isinstance(value, int) or isinstance(value, float) or isinstance(value, bool):
            value = str(value)
        else:
            return None

        if value == "":
            return None
    elif p.type == 'int' or p.type == 'integer':
        if isinstance(value, int):
            return value
        elif isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return None
        else:
            return None
    else:
        # TODO: Handle more types explicitly like date, enum, etc.
        # For the moment, just convert them to strings and check that at least they are not empty
        value = str(value)
        if len(value.strip()) == 0:
            return None

    return value


def replace_values(response, data):
    for k, v in data.items():
        # Handle both {{ }} and { }
        response = response.replace("{{" + k + "}}", str(v))
        response = response.replace("{" + k + "}", str(v))
    return response


class RuntimeDataGatheringTool(BaseTool):
    module: spec.DataGatheringModule
    runtime_module: RuntimeChatbotModule
    description: str
    state: object

    def __init__(self, module: spec.DataGatheringModule, runtime_module: RuntimeChatbotModule, description: str,
                 state: object):
        super().__init__(name=module.name, module=module, runtime_module=runtime_module, description=description,
                         state=state)

    def _run(self, query: str, run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        import json
        data = {}
        try:
            json_query = json.loads(query)
            for p in self.module.data_model.properties:
                value = get_property_value(p, json_query)
                if value is not None:
                    data[p.name] = value

            if len(data) == len(self.module.data_model.properties):
                if self.state.is_module_active(self.runtime_module):
                    self.state.pop_module()

                result = None
                if self.module.on_success is not None and self.module.on_success.execute is not None:
                    result = eval_code(self.module.on_success.execute, data)
                    print("Result: ", result)

                if self.module.on_success is not None and self.module.on_success.response is not None:
                    data['result'] = result
                    return replace_values(self.module.on_success.response, data)
                else:
                    collected_data = ",".join([f'{k} = {v}' for k, v in data.items()])
                    return "Stop using the tool. The following data has been collected: " + collected_data

        except json.JSONDecodeError:
            pass

        if not self.state.is_module_active(self.runtime_module):
            self.state.push_module(self.runtime_module)

        return "Do not use the " + self.name + " tool and ask the user the following:" \
                                               "Please provide " + ", ".join(
            [p.name for p in self.module.data_model.properties])


class RuntimeQuestionAnsweringTool(BaseTool):
    module: spec.QuestionAnsweringModule
    runtime_module: RuntimeChatbotModule
    description: str
    state: object

    def __init__(self, module: spec.QuestionAnsweringModule, runtime_module: RuntimeChatbotModule, description: str,
                 state: object):
        super().__init__(name=module.name, module=module, runtime_module=runtime_module, description=description,
                         state=state)

    def _run(self, query: str, run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        print("QA: ", query)
        if query.startswith("Question:"):
            question = query.replace("Question:", "").strip()
            agent_chain = self.runtime_module.get_chain()
            ans = agent_chain.run(input=question)
            return ans
            # return "Answer the question: " + question
        else:
            raise ValueError("The query should start with \"Question:\"")


class RuntimeSequenceTool(BaseTool):
    module: spec.SequenceModule
    runtime_module: RuntimeChatbotModule
    description: str
    state: object

    def __init__(self, module: spec.SequenceModule, runtime_module: RuntimeChatbotModule, description: str,
                 state: object):
        super().__init__(name=module.name, module=module, runtime_module=runtime_module, description=description,
                         state=state, return_direct=True)

    def _run(self, query: str, run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        seq_modules = [t.runtime_module for t in self.runtime_module.tools]

        if not self.state.is_module_active(self.runtime_module):
            self.state.push_module(self.runtime_module)
            self.runtime_module.current_seq = 0

        self.state.push_module(seq_modules[self.runtime_module.current_seq])

        try:
            res = self.state.get_chain().run(input=query)
        except:
            # This is likely because of the query got from the upper module is not well-formed
            res = self.state.get_chain().run(input="Do your task")

        self.runtime_module.current_seq = self.runtime_module.current_seq + 1

        if self.state.is_module_active(self.runtime_module) and self.runtime_module.current_seq == len(seq_modules):
            self.state.pop_module()

        return res


def compute_init_module(chatbot_model: ChatbotModel) -> spec.Item:
    g = nx.DiGraph()
    chatbot_model.to_graph(g)
    sorted_modules = list(nx.topological_sort(g))
    init = sorted_modules[0]
    return init


class Engine(Visitor):
    def __init__(self, chatbot_model: ChatbotModel, configuration: Configuration):
        self._chatbot_model = chatbot_model
        self._init_module = compute_init_module(chatbot_model)
        self.configuration = configuration
        self._current_state = None
        self.recorded_interaction = RecordedInteraction()

    def first_action(self) -> ChatbotResult:
        self._current_state = self.configuration.new_state()
        module: modules.ChatbotModule = self._init_module.accept(self)
        self._current_state.push_module(module)

        initial_msg = "Hello"
        self.recorded_interaction.append(type="chatbot", message=initial_msg)
        return ChatbotResult(initial_msg, DebugInfo(current_module=self._init_module.name))

    def run_step(self, query: str) -> ChatbotResult:
        self.recorded_interaction.append(type="user", message=query)

        agent_chain = self._current_state.get_chain()
        ans = agent_chain.run(input=query)
        self.recorded_interaction.append(type="chatbot", message=ans)

        module_name = self._current_state.current_module().name  # type(self._current_state.current_module()).__name__
        return ChatbotResult(ans, DebugInfo(current_module=module_name))

    def visit_menu_module(self, module: spec.Module) -> modules.ChatbotModule:
        # Describe the menu
        options = '\nYou are able to assist only in these tasks:\n'
        options = options + '\n'.join([f'{i}: {item.title}' for i, item in enumerate(module.items)])

        # Describe how to handle each option
        handling = '\nThe following items specify how to handle each task:\n'
        handling = handling + '\n'.join([f'{i}: {item.accept(self)}. ' for i, item in enumerate(module.items)])

        # Specify the fallback
        if module.fallback is None:
            fallback = ''
        else:
            fallback = '\nFallback:\n' + module.fallback

        prompt = f'{module.presentation}\n{options}\n{handling}\n{fallback}'

        generator = ToolGenerator(self._chatbot_model, self._current_state)
        tools = [i.accept(generator) for i in module.items if
                 isinstance(i, spec.ToolItem) or isinstance(i, spec.SequenceItem)]
        # tools=[] # TODO: remove
        return RuntimeChatbotModule(module, self._current_state, prompt, tools=tools)

    def visit_data_gathering_module(self, module: spec.DataGatheringModule) -> modules.ChatbotModule:
        generator = ToolGenerator(self._chatbot_model, self._current_state)
        tool = module.accept(generator)
        return tool.runtime_module

    def visit_answer_item(self, item: spec.Item) -> str:
        return f'You have to answer "{item.answer}"'

    def visit_tool_item(self, item: spec.Item) -> str:
        return f'You have to use the tool "{item.reference}"'

    def visit_sequence_item(self, item: spec.SequenceItem) -> str:
        seq = item.get_sequence_module()
        return f'You have to use the tool "{seq.name}"'


class ToolGenerator(Visitor):
    def __init__(self, chatbot_model: ChatbotModel, state: "State"):
        self.chatbot_model = chatbot_model
        self.state = state

    def visit_tool_item(self, item: spec.ToolItem):
        return self.chatbot_model.resolve_module(item.reference).accept(self)

    def visit_sequence_item(self, item: spec.SequenceItem):
        seq = item.get_sequence_module()
        return seq.accept(self)

    def visit_data_gathering_module(self, module: spec.DataGatheringModule):
        prompt = module.description
        prompt = prompt + "\nThe tool needs the following data:\n"
        for p in module.data_model.properties:
            if p.is_simple_type():
                prompt = prompt + f'- {p.name} which is of type {p.type}\n'
            elif p.type == 'enum':
                prompt = prompt + f'- {p.name} which can be one of the following values: {",".join(p.values)}\n'
            else:
                raise ValueError(f'Unknown type {p.type}')

        property_names = ", ".join([p.name for p in module.data_model.properties])
        prompt = prompt + f'\nProvide the values as JSON with the following fields: {property_names}.\n'
        prompt = prompt + f"\nOnly provide the values for {property_names} if given by the user. If no value is given, provide the empty string.\n"

        module_prompt = (f"Your task is collecting the following data from the user: {property_names}. Pass this information to the corresponding tool.\n"
                         f"If there is missing data, ask for it politely.\n"
                         # f"Focus on the data to be collected and do not provide any other information or ask other stuff.\n"
                         f"\n")
        runtime_module = RuntimeChatbotModule(module, self.state, module_prompt, tools=[])
        tool = RuntimeDataGatheringTool(module=module, runtime_module=runtime_module, description=prompt,
                                        state=self.state)
        runtime_module.tools = [tool]
        return tool

    def visit_question_answering_module(self, module: spec.QuestionAnsweringModule):
        tool_description = (module.description +
                            # The list of questions is not needed in GPT-4
                            "\nThe tool is able to answer the following questions:\n" +
                            "\n".join([f"- Question: {q.question}" for q in module.questions]) +
                            "\n"
                            "\nProvide the question given by the user using the JSON format "
                            "\"'Question: <question>'\".\n")

        module_prompt = [f"Use the following to answer the questions:\n"]
        module_prompt = module_prompt + [f"- Question: {q.question}\n  Answer: {q.answer}\n" for q in module.questions]
        module_prompt = module_prompt + [f"\nOnly provide an answer if the question is in the list.\n"]
        module_prompt = "\n".join(module_prompt) + "\n"

        runtime_module = RuntimeChatbotModule(module, self.state, module_prompt, tools=[])
        tool = RuntimeQuestionAnsweringTool(module=module, runtime_module=runtime_module, description=tool_description,
                                            state=self.state)
        # The module doesn't have the tool because we don't want it to recurse
        # runtime_module.tools = [tool]
        return tool

    def visit_sequence_module(self, module: spec.SequenceModule):
        tool_description = module.description

        module_prompt = ''

        called_modules = [self.chatbot_model.resolve_module(ref) for ref in module.references]
        seq_tools = [t for m in called_modules if (t := m.accept(self)) is not None]

        runtime_module = RuntimeChatbotModule(module, self.state, module_prompt, tools=seq_tools)
        tool = RuntimeSequenceTool(module=module, runtime_module=runtime_module, description=tool_description,
                                   state=self.state)

        #current = runtime_module
        #for t in seq_tools[1:-1]:
        #   current.on_finish(lambda response: tool.module_finished(t.runtime_module))
        return tool

    def visit_action_module(self, module: spec.ActionModule):
        return None
