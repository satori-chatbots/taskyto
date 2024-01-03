import re
import uuid
from abc import ABC
from typing import List, Optional, Union

from langchain.agents.conversational.output_parser import ConvoOutputParser
from langchain.memory import ConversationBufferMemory
from langchain.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, SystemMessagePromptTemplate
from langchain.prompts.chat import MessageLike
from langchain.schema import AgentAction, OutputParserException, HumanMessage, AIMessage, AgentFinish
from pydantic import BaseModel, ConfigDict

import spec
from engine.common import Configuration, logger, get_property_value, replace_values
from engine.common.prompts import FORMAT_INSTRUCTIONS
from engine.common.validator import Formatter


class State:
    def __init__(self, module):
        self.module = module
        self.data = {}
        self.memory = ConversationBufferMemory(memory_key="chat_history")
        self.executed_tool = None

        # This is a hack to tell the engine that the current state has be executed
        # by passing the last response (or data).
        self.linked_to_previous_response = False

    def add_memory(self, memory_piece: "MemoryPiece"):
        if memory_piece.input is not None:
            self.memory.chat_memory.add_user_message(memory_piece.input)
        if memory_piece.output is not None:
            self.memory.chat_memory.add_ai_message(memory_piece.output)

    def add_user_memory(self, message):
        self.memory.chat_memory.add_user_message(message)

    def add_ai_memory(self, message):
        self.memory.chat_memory.add_ai_message(message)


class Instruction(ABC):
    pass


class AskUser(Instruction):
    pass


class RunModule(Instruction, BaseModel):
    module: "RuntimeChatbotModule"


class StateManager:

    def __init__(self):
        self.stack = []
        self.data = {}
        self.active_states = []
        # self.memory = ConversationBufferMemory(memory_key="chat_history")

    def push_instruction(self, instruction: Instruction):
        self.stack.append(instruction)

    def pop_instruction(self):
        self.stack.pop()

    def current_instruction(self):
        return self.stack[-1]

    def push_module(self, a_module):
        self.push_state(State(a_module))

    def push_state(self, state):
        self.active_states.append(state)

    def pop_module(self):
        self.active_states.pop()

    def current_state(self):
        return self.active_states[-1]

    def is_module_active(self, cls_or_obj):
        import inspect
        if inspect.isclass(cls_or_obj):
            return isinstance(self.active_modules[-1].module, cls_or_obj)
        return self.active_states[-1].module == cls_or_obj


class ChatbotOutputParser(ConvoOutputParser):

    # Make sure that it uses the proper format_instructions
    def parse(self, text: str) -> Union[AgentAction, AgentFinish]:
        if f"{self.ai_prefix}:" in text:
            return super().parse(text)

        expected = "Thought: Do I need to use a tool? No"
        if expected in text:
            return AgentFinish(
                {"output": text.split(expected)[-1].strip()}, text
            )
        return super().parse(text)

    @staticmethod
    def parse_observation(text):
        regex = r"Observation: (.*?)[\n]"
        match = re.search(regex, text + "\n")
        if not match:
            raise OutputParserException(f"Could not parse Observation from LLM output: `{text}`")
        return match.group(1)


class ModuleResponse(ABC):
    def __init__(self, message):
        self.message = message


class TaskSuccessResponse(ModuleResponse):
    def __init__(self, message):
        super().__init__(message)


class TaskInProgressResponse(ModuleResponse):
    module: Optional["RuntimeChatbotModule"] = None

    def __init__(self, message, module=None):
        super().__init__(message)
        self.module = module


class MemoryPiece(BaseModel):
    input: Optional[str] = None
    output: Optional[str] = None


# HUMAN_MESSAGE_TEMPLATE = "{input}\n\n{agent_scratchpad}"
HUMAN_MESSAGE_TEMPLATE = "Begin!\n\nPrevious conversation history:\n{history}\n\n{input}\n\n{agent_scratchpad}\n"


class RuntimeChatbotModule(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    module: spec.Module
    prompt: str
    activation_prompt: str = None
    tools: List["RuntimeChatbotModule"]
    configuration: Configuration

    ai_prefix: str = "AI"
    parser: ChatbotOutputParser = ChatbotOutputParser()

    # Handling of data dependencies
    id: str = uuid.uuid4()
    previous_tool: Optional["RuntimeChatbotModule"] = None

    def name(self):
        return self.module.name

    def set_data(self, state: StateManager, data):
        """
        To be used by sub-classes
        """
        state.data[self.id] = data

    def get_tool_names(self):
        return ", ".join([tool.name() for tool in self.tools])

    def get_tools_prompt(self):
        activations = [f'> {tool.name()}: {tool.activation_prompt}' for tool in self.tools if
                       tool.activation_prompt is not None]
        if len(activations) == 0:
            return ""

        return "Tools:\n" + "\n\n".join(activations)

    def run_as_tool(self, state: StateManager, tool_input: str):
        raise NotImplementedError("This module cannot be run as a tool")

    def find_tool_by_name(self, tool_name: str):
        for tool in self.tools:
            if tool.name() == tool_name:
                return tool
        raise ValueError(f"Unknown tool {tool_name}")

    def execute_tool(self, state: StateManager, tool_name: str, tool_input: str, previous_answer: MemoryPiece):
        module = self.find_tool_by_name(tool_name)
        response = module.run_as_tool(state, tool_input)

        if isinstance(response, TaskSuccessResponse):
            # TODO: Here we need to decide if we want to add something to the memory like a summary of what the tool has performed
            state.current_state().executed_tool = tool_name    # trace executed tool
            return response
        elif isinstance(response, TaskInProgressResponse):
            previous_answer.output += "\nObservation: " + response.message
            state.current_state().add_memory(previous_answer)
            # new_input = "Observation: " + response.message

            if response.module is not None:
                module = response.module

            return module.run(state, None)
        else:
            raise ValueError(f"Unknown response type {response}")

    def run(self, state: StateManager, input: str) -> ModuleResponse:
        # From ConversationalAgent, but modified
        prefix = self.prompt
        format_instructions = FORMAT_INSTRUCTIONS.format(tool_names=self.get_tool_names(), ai_prefix=self.ai_prefix)
        formatted_tools = self.get_tools_prompt()
        suffix = ""

        template = "\n\n".join([prefix,
                                formatted_tools,
                                format_instructions,
                                suffix])

        input_variables = ["input", "history", "agent_scratchpad"]
        _memory_prompts = state.current_state().memory.buffer_as_messages
        messages = [
            SystemMessagePromptTemplate.from_template(template),
            # *_memory_prompts,
            HumanMessagePromptTemplate.from_template(HUMAN_MESSAGE_TEMPLATE),
        ]
        template = ChatPromptTemplate(input_variables=input_variables, messages=messages)

        llm = self.configuration.llm()

        if input is None or input.strip() == "":
            prompt_input = ""
        else:
            prompt_input = "New input: " + input

        formatted_prompt = template.format_messages(input=prompt_input,
                                                    history=RuntimeChatbotModule.to_messages(_memory_prompts),
                                                    agent_scratchpad="")
        # agent_scratchpad="Thought: ")
        logger.debug_prompt(formatted_prompt)

        result = llm(formatted_prompt, stop=["\nObservation:"])

        # TODO: Handle langchain.schema.output_parser.OutputParserException smoothly
        parsed_result = self.parser.parse(result.content)

        if isinstance(parsed_result, AgentAction):
            previous_answer = MemoryPiece(input=input, output=parsed_result.log)
            return self.execute_tool(state, parsed_result.tool, parsed_result.tool_input, previous_answer)
        else:
            output = parsed_result.return_values['output']

            state.current_state().add_memory(MemoryPiece(input=input, output=output))

            return TaskSuccessResponse(output)

    @staticmethod
    def to_messages(messages: [MessageLike]):
        prefixed = []
        for message in messages:
            if isinstance(message, HumanMessage):
                # prefixed.append(message.content)
                prefixed.append("Human: " + message.content)
            elif isinstance(message, AIMessage):
                # prefixed.append("AI: " + message.content)
                prefixed.append(message.content)
            else:
                raise ValueError(f"Unknown message type {message}")
        return "\n".join(prefixed)

class DataGatheringChatbotModule(RuntimeChatbotModule):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tools.append(self)

    def run_as_tool(self, state: StateManager, tool_input: str):
        import json
        data = {}
        validators = Formatter.get_validators()

        try:
            json_query = json.loads(tool_input)

            for p in self.module.data_model.properties:
                value = get_property_value(p, json_query)
                if value is not None and p.type in validators:
                    formatted_value = validators[p.type].do_format(value, p)
                    if formatted_value is not None:
                        data[p.name] = formatted_value
                else:
                    data[p.name] = value

            if len(data) == len(self.module.data_model.properties):
                if state.is_module_active(self):
                    state.pop_module()

                result = None
                if self.module.on_success is not None and self.module.on_success.execute is not None:
                    evaluator = self.configuration.new_evaluator()
                    result = evaluator.eval_code(self.module.on_success.execute, data)

                self.set_data(state, data)
                if self.module.on_success is not None and self.module.on_success.response is not None:
                    data['result'] = result
                    return TaskSuccessResponse(replace_values(self.module.on_success.response, data))
                else:
                    collected_data = ",".join([f'{k} = {v}' for k, v in data.items()])
                    # return "Stop using the tool. The following data has been collected: " + collected_data
                    return TaskSuccessResponse("The following data has been collected: " + collected_data)

        except json.JSONDecodeError:
            pass

        if not state.is_module_active(self):
            state.push_state(State(self))

        missing_properties = [p.name for p in self.module.data_model.properties if p.name not in data]
        instruction = "Do not use the " + self.name() + " tool and ask the user the following:" \
                                                        "Please provide " + ", ".join(missing_properties)
        return TaskInProgressResponse(instruction, module=self)
        # return "Do not use the " + self.name + " tool and ask the user the following:" \
        #                                       "Please provide " + ", ".join(
        #    [p.name for p in self.module.data_model.properties])


class QuestionAnsweringRuntimeModule(RuntimeChatbotModule):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tools.append(self)

    def run_as_tool(self, state: StateManager, tool_input: str):
        new_llm = self.configuration.llm()
        question = self.get_question(tool_input)

        prompt_template = ChatPromptTemplate.from_template(self.prompt)
        prompt_template.append("Please answer the following question:")
        prompt_template.append(question)

        result = new_llm(prompt_template.format_messages())
        return TaskSuccessResponse(result.content)

    def get_question(self, tool_input):
        if tool_input.startswith("Question:"):
            return tool_input.replace("Question:", "").strip()
        else:
            import json
            json_query = json.loads(tool_input)
            if "question" in json_query:
                return json_query["question"].strip()

        raise ValueError("The query should start with \"Question:\" but it was: " + tool_input)


class SequenceChatbotModule(RuntimeChatbotModule):
    def run_as_tool(self, state_manager: StateManager, tool_input: str):
        # traverse self.tools in reverse order and add each tool to state.push_state
        for tool in reversed(self.tools[1:]):
            new_state = State(tool)
            new_state.linked_to_previous_response = True
            state_manager.push_state(new_state)

        initial_tool = self.tools[0]
        # state.push_module(self)
        state_manager.push_state(State(initial_tool))

        postfix = ""
        if tool_input is not None and tool_input.strip() != "":
            postfix = "following this request: " + tool_input

        return TaskInProgressResponse("Do your task " + postfix, module=initial_tool)


class ActionChatbotModule(RuntimeChatbotModule):
    # This is overriding run to avoid launching the LLM. Probably we need another super-class to split behaviors.

    def run(self, state: StateManager, input: str) -> ModuleResponse:
        available_data = state.data[self.previous_tool.id]
        if available_data is None:
            raise ValueError(
                "Data is None. Expected data for module " + self.previous_tool.name() + " - " + self.previous_tool.id)

        # Extract the data needed
        data = {}
        for p in self.module.data_model.properties:
            if p.name not in available_data:
                raise ValueError("Data is missing the property " + p.name)

            data[p.name] = available_data[p.name]

        if self.module.on_success is not None and self.module.on_success.execute is not None:
            evaluator = self.configuration.new_evaluator()
            result = evaluator.eval_code(self.module.on_success.execute, data)

            state.pop_module()

            data['result'] = result
            return TaskSuccessResponse(replace_values(self.module.on_success.response, data))
        else:
            raise ValueError("Action module should have an on_success.execute")
