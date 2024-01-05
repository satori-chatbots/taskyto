import abc
import re
import uuid
from abc import ABC
from typing import List, Optional, Union
from engine.custom.events import ActivateModuleEvent, AIResponseEvent, TaskFinishEvent

from langchain.agents.conversational.output_parser import ConvoOutputParser
from langchain.memory import ConversationBufferMemory
from langchain.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, SystemMessagePromptTemplate
from langchain.prompts.chat import MessageLike
from langchain.schema import AgentAction, OutputParserException, HumanMessage, AIMessage, AgentFinish
from pydantic import BaseModel, ConfigDict

import spec
import utils
from engine.common import Configuration, logger, get_property_value, replace_values, Rephraser
from engine.common.prompts import FORMAT_INSTRUCTIONS
from engine.common.validator import Formatter, FallbackFormatter
from utils import get_unparsed_output

from engine.common import Configuration, logger, get_property_value, replace_values, Rephraser, prompts
from engine.common.memory import ConversationMemory, MemoryPiece
from engine.common.prompts import FORMAT_INSTRUCTIONS, NO_TOOL_INSTRUCTIONS
from engine.custom.events import ActivateModuleEvent, AIResponseEvent


class ExecutionState:

    def __init__(self, initial, channel: "Channel"):
        self.current = initial
        self.channel = channel
        self.action_listeners = []
        self.event_stack = []
        self.memory = {}

        # To pass data between modules
        self.data = {}

    def add_action_listener(self, listener):
        self.action_listeners.append(listener)

    def notify_action_listeners(self, action):
        for listener in self.action_listeners:
            listener(action)

    def update_memory(self, module, memory_piece: "MemoryPiece", memory_id: str):
        memory = self.get_or_create_memory(module, memory_id)
        memory.add_memory(memory_piece)

    def get_memory(self, module, memory_id):
        return self.get_or_create_memory(module, memory_id)
        # TODO: For the moment, create the memory if it doesnt' exist, but maybe we need a protocol to make sure
        #       that the memory is created at the beginning of the conversation
        # module_id = module.name
        # return self.memory[module_id][memory_id]

    def get_or_create_memory(self, module, memory_id):
        module_id = module.name
        if module_id not in self.memory:
            self.memory[module_id] = {}
        if memory_id not in self.memory[module_id]:
            self.memory[module_id][memory_id] = ConversationMemory()

        return self.memory[module_id][memory_id]

    def pop_event(self):
        return self.event_stack.pop()

    def more_events(self):
        return len(self.event_stack) > 0

    def push_event(self, event):
        self.event_stack.append(event)


class Channel(abc.ABC):
    pass


class ConsoleChannel(Channel):

    def input(self):
        import utils
        user_prompt = utils.get_user_prompt()
        try:
            inp = input(user_prompt)
            if inp == 'exit':
                return None
            return inp
        except EOFError as e:
            return None

    def output(self, msg, who=None):
        utils.print_chatbot_answer2(msg, who)


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


# HUMAN_MESSAGE_TEMPLATE = "{input}\n\n{agent_scratchpad}"
HUMAN_MESSAGE_TEMPLATE = "Begin!\n\nPrevious conversation history:\n{history}\n\n{input}\n\n{agent_scratchpad}\n"


class CustomRephraser(Rephraser):
    def rephrase(self, message: str, context: Optional[str] = None) -> str:
        prompt = "Please rephrase the following message:\n" + message
        if context is not None:
            prompt = "Context: " + context + "\n" + prompt

        formatted_message = HumanMessagePromptTemplate.from_template(prompt).format()
        return self.configuration.llm()([formatted_message]).content


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

    # Not needed anymore
    # previous_tool: Optional["RuntimeChatbotModule"] = None

    def name(self):
        return self.module.name

    def set_data(self, state: ExecutionState, data):
        """
        To be used by sub-classes
        """
        state.data[self.id] = data

    def get_prompts_disabled(self, prompt_id):
        return []

    def get_human_prompt(self) -> prompts.Prompt:
        return prompts.section("default", HUMAN_MESSAGE_TEMPLATE).to_prompt()

    def memory_types(self):
        return {}

    def get_tool_names(self):
        return ", ".join([tool.name() for tool in self.tools])

    def get_tools_prompt(self):
        activations = [f'> {tool.name()}: {tool.activation_prompt}' for tool in self.tools if
                       tool.activation_prompt is not None]
        if len(activations) == 0:
            return ""

        return "Tools:\n" + "\n\n".join(activations)

    def run_as_tool(self, state: ExecutionState, tool_input: str, activating_event=None):
        # Activating event is here just for sequence module...
        raise NotImplementedError("This module cannot be run as a tool")

    def find_tool_by_name(self, tool_name: str):
        for tool in self.tools:
            if tool.name() == tool_name:
                return tool
        raise ValueError(f"Unknown tool {tool_name}")

    def execute_tool(self, state: ExecutionState, tool_name: str, tool_input: str, previous_answer: MemoryPiece):
        module = self.find_tool_by_name(tool_name)
        event = ActivateModuleEvent(module, tool_input, previous_answer)
        state.push_event(event)

    def execute_action(self, action: Optional[spec.Action], data: dict, default_response: str = None) -> str:
        if action is not None and action.execute is not None:
            evaluator = self.configuration.new_evaluator()
            result = evaluator.eval_code(action.execute, data)

            if action.response is not None:
                data['result'] = result
                response_element = action.get_response_element()
                response = replace_values(response_element.text, data)
                response = self.configuration.new_rephraser()(
                    response) if response_element.is_simple_rephrase() else response
                return response
            else:
                return result
        elif default_response is not None:
            return default_response
        else:
            raise ValueError("No response available")

    def run(self, state: ExecutionState, input: str, allow_tools=True, prompts_disabled=[]):
        # From ConversationalAgent, but modified
        prefix = self.prompt
        format_instructions = FORMAT_INSTRUCTIONS.format(tool_names=self.get_tool_names(), ai_prefix=self.ai_prefix)
        formatted_tools = self.get_tools_prompt()
        suffix = ""

        if not allow_tools:
            format_instructions = NO_TOOL_INSTRUCTIONS.format(ai_prefix=self.ai_prefix)
            formatted_tools = ""

        template = "\n\n".join([prefix,
                                formatted_tools,
                                format_instructions,
                                suffix])

        # input_variables = ["input", "history", "agent_scratchpad"]
        input_variables = ["input", "agent_scratchpad"]

        # TODO: Allow passing as parameters the section of the prompt that we want to use
        human_prompt = self.get_human_prompt()
        variables = human_prompt.variables()
        input_variables.extend(variables)

        memory_types = self.memory_types()
        substitutions = {}
        # The variable is the same as the memory_id... by convention
        for memory_id in variables:
            m = state.get_memory(self.module, memory_id)
            memory_type = memory_types.get(memory_id) or "default"
            substitutions[memory_id] = m.to_text_messages(memory_type)

        #_memory_prompts = state.get_memory(self.module).buffer_as_messages
        messages = [
            SystemMessagePromptTemplate.from_template(template),
            HumanMessagePromptTemplate.from_template(human_prompt.to_text(prompts_disabled=prompts_disabled)),
            #HumanMessagePromptTemplate.from_template(HUMAN_MESSAGE_TEMPLATE),
        ]
        template = ChatPromptTemplate(input_variables=input_variables, messages=messages)

        llm = self.configuration.llm(module_name=self.name())

        if input is None or input.strip() == "":
            prompt_input = ""
        else:
            prompt_input = "New input: " + input

        substitutions['input'] = prompt_input
        substitutions['agent_scratchpad'] = ""

        formatted_prompt = template.format_messages(**substitutions)
        # agent_scratchpad="Thought: ")
        logger.debug_prompt(formatted_prompt)

        result = llm(formatted_prompt, stop=["\nObservation:"])

        # TODO: Handle langchain.schema.output_parser.OutputParserException smoothly
        try:
            parsed_result = self.parser.parse(result.content)
        except OutputParserException as ope:
            # for the moment, just try to continue
            message = get_unparsed_output(str(ope))
            # jesus: not sure if this has to be a finish event (task is completed) or AIResponse
            state.push_event(TaskFinishEvent(message))

        if isinstance(parsed_result, AgentAction):
            previous_answer = (MemoryPiece().
                               add_human_message(input).
                               add_ai_reasoning_message(parsed_result.log))
            self.execute_tool(state, parsed_result.tool, parsed_result.tool_input, previous_answer)
        else:
            output = parsed_result.return_values['output']
            state.push_event(AIResponseEvent(output))

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

