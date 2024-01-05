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
            json_query = json.loads(tool_input)
            for p in self.module.data_model.properties:
                value = get_property_value(p, json_query)
                if value is not None and p.type in validators:
                    formatted_value = validators[p.type].do_format(value, p, self.configuration)
                    if formatted_value is not None:
                        data[p.name] = formatted_value
                else:
                    formatted_value = FallbackFormatter().do_format(value, p, self.configuration)
                    if formatted_value is not None:
                        data[p.name] = value


            if len(data) == len(self.module.data_model.properties):
                collected_data = ",".join([f'{k} = {v}' for k, v in data.items()])
                result = self.execute_action(self.module.on_success, data,
                                             default_response=f"The following data has been collected: {collected_data}")

                # TODO: This is probably not needed anymore
                self.set_data(state, data)

                data_memory = MemoryPiece().add_data_message(collected_data)
                inst_memory = MemoryPiece().add_instruction_message("Tell the user:" + result)
                state.push_event(
                    TaskFinishEvent(result, memory={'collected_data': data_memory, 'instruction': inst_memory}, data=data))
                return None
        except json.JSONDecodeError:
            pass

        collected_data = ",".join([f'{k} = {v}' for k, v in data.items()])
        missing_properties = [p.name for p in self.module.data_model.properties if p.name not in data]

        data_memory = MemoryPiece().add_data_message(collected_data)
        inst_memory = MemoryPiece().add_instruction_message("Respond the following to the Human:" \
                                                            "Please provide " + ", ".join(missing_properties))

        state.push_event(TaskInProgressEvent(memory={'collected_data': data_memory, 'instruction': inst_memory}))


class QuestionAnsweringRuntimeModule(RuntimeChatbotModule):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tools.append(self)

    def run_as_tool(self, state: ExecutionState, tool_input: str, activating_event=None):
        new_llm = self.configuration.llm(module_name=self.name())
        question = self.get_question(tool_input)

        prompt_template = ChatPromptTemplate.from_template(self.prompt)
        prompt_template.append("Please answer the following question:")
        prompt_template.append(question)

        result = new_llm(prompt_template.format_messages())
        state.push_event(TaskFinishEvent(result.content))

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