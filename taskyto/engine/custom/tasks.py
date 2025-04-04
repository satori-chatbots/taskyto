from typing import Optional

from langchain.prompts import ChatPromptTemplate

from taskyto.engine.common import get_property_value, prompts, logger
from taskyto.engine.common.memory import MemoryPiece
from taskyto.engine.common.validator import FallbackFormatter, Formatter
from taskyto.engine.custom.events import TaskInProgressEvent, TaskFinishEvent, ActivateModuleEvent
from taskyto.engine.custom.runtime import RuntimeChatbotModule, ExecutionState, HUMAN_MESSAGE_TEMPLATE



class MenuChatbotModule(RuntimeChatbotModule):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def memory_types(self):
        return {
            'default': ['default'],
            'instruction': ['instruction']
        }

    def get_prompts_disabled(self, prompt_id):
        if prompt_id == "input":
            return ['instruction']
        elif prompt_id == "reasoning":
            return ['input']
        return super().get_prompts_disabled(prompt_id)

    def get_human_prompt(self) -> prompts.Prompt:
        default_ = prompts.section("default", HUMAN_MESSAGE_TEMPLATE).to_prompt()
        instruction = prompts.section("instruction", "{instruction}")
        return default_ + instruction

    def run_as_tool(self, state: ExecutionState, tool_input: str, activating_event=None):
        # Here the tool_input has what the user has written and led to the activation of this tool
        # TODO: We don't seem to have access to prompt  
        self.run(state, tool_input)



class DataGatheringChatbotModule(RuntimeChatbotModule):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tools.append(self)

    def memory_types(self):
        return {
            'collected_data': ['data'],
            'history': ['human', 'ai_response'],
            'instruction': ['instruction']
        }

    def get_prompts_disabled(self, prompt_id):
        if prompt_id == "input":
            return ['instruction']
        elif prompt_id == "in-caller-rephrasing":
            # I think we never invoke with this because we keep both the history and the instruction
            return ['input']
        return super().get_prompts_disabled(prompt_id)

    def get_human_prompt(self):
        history = prompts.section("history",
                                  """Previous conversation history:\n{history}""")

        data = prompts.section("collected-data",
                               """Data already collected: {collected_data}""")

        instruction = prompts.section("instruction", "{instruction}")

        input_ = prompts.section("input", "{input}")

        return history + data + instruction + input_

    def run_as_tool(self, state: ExecutionState, tool_input: Optional[str], activating_event=None):
        import json
        data = {}
        validators = Formatter.get_validators()

        try:
            unknown_values = []
            if tool_input is None:
                # This may happen when the tool is invoked explicitly without going through an LLM (e.g., as part of a sequence)
                tool_input = "{}"
            json_query = json.loads(tool_input)
            for p in self.module.data_model.properties:
                value = get_property_value(p, json_query)
                if value is None:
                    continue

                if value is not None and p.type in validators:
                    formatted_value = validators[p.type].do_format(value, p, self.configuration)
                    if formatted_value is not None:
                        data[p.name] = formatted_value
                else:
                    formatted_value = FallbackFormatter().do_format(value, p, self.configuration)
                    if formatted_value is not None:
                        data[p.name] = value
                    else:
                        unknown_values.append(value)

            # if len(data) == len(self.module.data_model.properties):
            if self.all_mandatory_data_provided(data):
                collected_data = ",".join([f'{k} = {v}' for k, v in data.items()])
                result = self.execute_action(self.module.on_success, data,
                                             default_response=f"The following data has been collected: {collected_data}")

                data_memory = MemoryPiece().add_data_message(collected_data, data)
                inst_memory = MemoryPiece().add_instruction_message("Tell the user:" + result)
                state.push_event(
                    TaskFinishEvent(result, memory={'collected_data': data_memory, 'instruction': inst_memory},
                                    data=data))

                # The data is made available, indexing it by the name of the module
                self.set_data(state, data)

                return None
        except json.JSONDecodeError:
            pass
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise e

        collected_data = ",".join([f'{k} = {v}' for k, v in data.items()])
        instruction = ("Check in the previous conversation history, and if the data is not present, ask the Human to provide the missing data: " +
                       self.get_missing_data_instruction(data, lambda param: param.required))
        missing_optionals = self.get_missing_data_instruction(data, lambda param: not param.required)
        if len(missing_optionals) > 0:
            instruction += f"\nIf you have not asked for it before, tell the human that the following data is optional: " + missing_optionals
        if len(unknown_values) > 0:
            instruction += f"\nIn addition, tell the human that you could not understand: {','.join(unknown_values)}"

        data_memory = MemoryPiece().add_data_message(collected_data, data)
        inst_memory = MemoryPiece().add_instruction_message(instruction)

        state.push_event(TaskInProgressEvent(memory={'collected_data': data_memory, 'instruction': inst_memory}))

    def all_mandatory_data_provided(self, data):
        for dp in self.module.data_model.properties:
            if dp.required and dp.name not in data:
                return False
        return True

    # TODO: Decide if we want to be more explicit about what information is missing and its shape (specifically for enums)
    def get_missing_data_instruction(self, data, param_predicate=lambda param: True):
        # missing_properties = [p.name for p in self.module.data_model.properties if p.name not in data and p.required]
        missing_properties = [p.name for p in self.module.data_model.properties
                              if p.name not in data and param_predicate(p)]
        return ", ".join(missing_properties)


def get_question(tool_input):
    """
    Extracts the question from the tool input. This is a helper function to be used by the RAG module and QA module.
    """
    if tool_input.startswith("Question:"):
        return tool_input.replace("Question:", "").strip()
    else:
        import json
        tool_input = keep_until_last_brace(tool_input)  # remove the extra "\n'''\n" that sometimes this string has
        json_query = json.loads(tool_input)
        if "question" in json_query:
            return json_query["question"].strip()

    raise ValueError("The query should start with \"Question:\" but it was: " + tool_input)


def keep_until_last_brace(s):
    last_brace_index = s.rfind('}')

    if last_brace_index != -1:
        return s[:last_brace_index + 1]
    else:
        return s

from taskyto.engine.rag.loader import InputLoader
from taskyto.engine.rag.embeddings import Indexer
from functools import cached_property

class RagRuntimeModule(RuntimeChatbotModule):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def run_as_tool(self, state: ExecutionState, tool_input: str, activating_event=None):
        question = get_question(tool_input)
        response = self._index.query(question)
        state.push_event(TaskFinishEvent(response))


    @cached_property
    def _index(self):
        loader = InputLoader(self.module.documents, self.configuration)
        return Indexer(loader.load_data(), self.configuration)

class OpenEndedConversationRuntimeModule(RuntimeChatbotModule):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def memory_types(self):
        return {
            'default': ['default'],
            'instruction': ['instruction']
        }

    def get_human_prompt(self) -> prompts.Prompt:
        default_ = prompts.section("default", HUMAN_MESSAGE_TEMPLATE).to_prompt()
        instruction = prompts.section("instruction", "{instruction}")
        return default_ + instruction

    def get_prompts_disabled(self, prompt_id):
        if prompt_id == "input":
            return ['instruction']
        elif prompt_id == "reasoning":
            return ['input']
        return super().get_prompts_disabled(prompt_id)

    def run_as_tool(self, state: ExecutionState, tool_input: str, activating_event=None):
        self.run(state, tool_input)

        #print("Open ended conversation: ", tool_input)
        # This is a simple pass-through module
        #state.push_event(TaskFinishEvent(tool_input))


class QuestionAnsweringRuntimeModule(RuntimeChatbotModule):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tools.append(self)

    def run_as_tool(self, state: ExecutionState, tool_input: str, activating_event=None):
        new_llm = self.configuration.new_llm(module_name=self.name())
        question = get_question(tool_input)

        # prompt_template = ChatPromptTemplate.from_template(self.prompt)
        prompt_template = ChatPromptTemplate.from_template(self.presentation_prompt + "\n" + self.task_prompt)
        prompt_template.append("If you match the user question with questions in the list, reply ANSWER_IS: followed by the answer."
                               "Otherwise, reply exactly 'I do not know', "
                               "followed by a summary of the questions that you know how to answer, replying in first person\n")
        prompt_template.append("Please answer the following question:")
        prompt_template.append(question)

        formatted_prompt = prompt_template.format_messages()
        logger.debug_prompt(formatted_prompt)

        result = new_llm(formatted_prompt)

        response = self.parse_LLM_output(result.content)
        data = {'result': response, 'question': question}
        response = self.execute_action(self.module.on_success, data, response)

        state.push_event(TaskFinishEvent(response))

    def parse_LLM_output(self, output: str):
        return output.replace("ANSWER_IS:", '').strip()


class SequenceChatbotModule(RuntimeChatbotModule):
    def run_as_tool(self, state_manager: ExecutionState, tool_input: str, activating_event=None):
        assert activating_event is not None

        if isinstance(activating_event, TaskFinishEvent):
            # To exit
            # We do not propagate this event as is because we do not want to use the response contained here
            # in a SayAction, because this will cause the response to be repeated twice (it has already been said from
            # the last state to the sequence state end state).
            # state_manager.push_event(activating_event)
            state_manager.push_event(TaskFinishEvent(None, memory=activating_event.memory))
        else:
            # To enter
            state_manager.push_event(ActivateModuleEvent(self.tools[0], tool_input, activating_event.previous_answer))


class ActionChatbotModule(RuntimeChatbotModule):
    def run(self, state: ExecutionState, input: str):
        raise NotImplementedError("ActionChatbotModule should not be run")

    def run_as_tool(self, state_manager: ExecutionState, tool_input: str, activating_event=None):
        history = state_manager.get_memory(self.module, 'collected_data')
        available_data = history.data

        if available_data is None:
            raise ValueError(
                "Data is None. Expected data for module " + self.previous_tool.name() + " - " + self.previous_tool.id)

        # Extract the data needed
        data = {}
        for p in self.module.data_model.properties:
            if p.name not in available_data:
                raise ValueError("Data is missing the property " + p.name)

            data[p.name] = available_data[p.name]

        if self.module.on_success.execute is None:
            raise ValueError("Action module should have an on_success.execute")

        result = self.execute_action(self.module.on_success, data)
        state_manager.push_event(TaskFinishEvent(result))
