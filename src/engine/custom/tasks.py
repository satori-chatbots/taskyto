from langchain.prompts import ChatPromptTemplate

from engine.common import get_property_value, prompts
from engine.common.memory import MemoryPiece
from engine.common.validator import FallbackFormatter, Formatter
from engine.custom.events import TaskInProgressEvent, TaskFinishEvent, ActivateModuleEvent
from engine.custom.runtime import RuntimeChatbotModule, ExecutionState


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
        elif prompt_id == "reasoning":
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

    def run_as_tool(self, state: ExecutionState, tool_input: str, activating_event=None):
        import json
        data = {}
        validators = Formatter.get_validators()

        try:
            unknown_values = []
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

            if len(data) == len(self.module.data_model.properties):
                collected_data = ",".join([f'{k} = {v}' for k, v in data.items()])
                result = self.execute_action(self.module.on_success, data,
                                             default_response=f"The following data has been collected: {collected_data}")

                data_memory = MemoryPiece().add_data_message(collected_data)
                inst_memory = MemoryPiece().add_instruction_message("Tell the user:" + result)
                state.push_event(
                    TaskFinishEvent(result, memory={'collected_data': data_memory, 'instruction': inst_memory},
                                    data=data))

                # The data is made available, indexing it by the name of the module
                self.set_data(state, data)

                return None
        except json.JSONDecodeError:
            pass

        collected_data = ",".join([f'{k} = {v}' for k, v in data.items()])
        instruction = "Ask the Human to provide the missing data: " + self.get_missing_data_instruction(data)
        if len(unknown_values) > 0:
            instruction += f"\nIn addition, tell the human that you could not understand: {','.join(unknown_values)}"

        data_memory = MemoryPiece().add_data_message(collected_data)
        inst_memory = MemoryPiece().add_instruction_message(instruction)

        state.push_event(TaskInProgressEvent(memory={'collected_data': data_memory, 'instruction': inst_memory}))

    # TODO: Decide if we want to be more explicit about what information is missing and its shape (specifically for enums)
    def get_missing_data_instruction(self, data):
        missing_properties = [p.name for p in self.module.data_model.properties if p.name not in data]
        return ", ".join(missing_properties)


class QuestionAnsweringRuntimeModule(RuntimeChatbotModule):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tools.append(self)

    def run_as_tool(self, state: ExecutionState, tool_input: str, activating_event=None):
        new_llm = self.configuration.new_llm(module_name=self.name())
        question = self.get_question(tool_input)

        #prompt_template = ChatPromptTemplate.from_template(self.prompt)
        prompt_template = ChatPromptTemplate.from_template(self.task_prompt)
        prompt_template.append("Please answer the following question:")
        prompt_template.append(question)
        prompt_template.append("If you find the answer, reply ANSWER_IS: followed by the answer")
        prompt_template.append("If you do not find the information, reply exactly 'I do not know'"
                               ", followed by a summary of what can you answer, replying in first person")

        result = new_llm(prompt_template.format_messages())
        state.push_event(TaskFinishEvent(self.parse_LLM_output(result.content)))

    def parse_LLM_output(self, output: str):
        return output.replace("ANSWER_IS:", '').strip()


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
    def run_as_tool(self, state_manager: ExecutionState, tool_input: str, activating_event=None):
        assert activating_event is not None

        if isinstance(activating_event, TaskFinishEvent):
            # To exit
            state_manager.push_event(activating_event)
        else:
            # To enter
            state_manager.push_event(ActivateModuleEvent(self.tools[0], tool_input, activating_event.previous_answer))


class ActionChatbotModule(RuntimeChatbotModule):
    def run(self, state: ExecutionState, input: str):
        raise NotImplementedError("ActionChatbotModule should not be run")

    def run_as_tool(self, state_manager: ExecutionState, tool_input: str, activating_event=None):
        available_data = activating_event.get_property_value("data")
        # available_data = state.data[self.previous_tool.id]
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
