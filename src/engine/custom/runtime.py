import re
from abc import ABC
from typing import List, Optional

from langchain.agents.conversational.output_parser import ConvoOutputParser
from langchain.memory import ConversationBufferMemory
from langchain.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, SystemMessagePromptTemplate
from langchain.prompts.chat import MessageLike
from langchain.schema import AgentAction, OutputParserException, HumanMessage, AIMessage
from pydantic import BaseModel, ConfigDict

import spec
from engine.common import Configuration, logger, get_property_value, replace_values, prompts
from engine.common.prompts import FORMAT_INSTRUCTIONS
from eval import eval_code


class State:
    def __init__(self, module):
        self.module = module
        self.data = {}
        self.memory = ConversationBufferMemory(memory_key="chat_history")

    def add_memory(self, memory_piece: "MemoryPiece"):
        if memory_piece.input is not None:
            self.memory.chat_memory.add_user_message(memory_piece.input)
        if memory_piece.output is not None:
            self.memory.chat_memory.add_ai_message(memory_piece.output)

    def add_user_memory(self, message):
        self.memory.chat_memory.add_user_message(message)

    def add_ai_memory(self, message):
        self.memory.chat_memory.add_ai_message(message)


class StateManager:

    def __init__(self):
        self.active_states = []
        # self.memory = ConversationBufferMemory(memory_key="chat_history")

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
    pass

    # Make sure that it uses the proper format_instructions

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
    def __init__(self, message):
        super().__init__(message)


class MemoryPiece(BaseModel):
    input: str
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

    def name(self):
        return self.module.name

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
            return response
        elif isinstance(response, TaskInProgressResponse):
            previous_answer.output += "\nObservation: " + response.message
            state.current_state().add_memory(previous_answer)
            #new_input = "Observation: " + response.message
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
                                                    #agent_scratchpad="")
                                                    agent_scratchpad="Thought: ")
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
                #prefixed.append("AI: " + message.content)
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
        try:
            json_query = json.loads(tool_input)
            for p in self.module.data_model.properties:
                value = get_property_value(p, json_query)
                if value is not None:
                    data[p.name] = value

            if len(data) == len(self.module.data_model.properties):
                if state.is_module_active(self):
                    state.pop_module()

                result = None
                if self.module.on_success is not None and self.module.on_success.execute is not None:
                    result = eval_code(self.module.on_success.execute, data)
                    print("Result: ", result)

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
        return TaskInProgressResponse(instruction)
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
