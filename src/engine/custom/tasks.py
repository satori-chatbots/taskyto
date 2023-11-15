from typing import Optional

from langchain.prompts import ChatPromptTemplate

from engine.common import get_property_value, replace_values
from engine.custom.runtime import RuntimeChatbotModule, StateManager, TaskSuccessResponse, State, \
    TaskInProgressResponse, ModuleResponse
from spec import Action


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

                collected_data = ",".join([f'{k} = {v}' for k, v in data.items()])
                result = self.execute_action(self.module.on_success, data,
                                      default_response=f"The following data has been collected: {collected_data}")

                self.set_data(state, data)
                return TaskSuccessResponse(result)
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

        if self.module.on_success.execute is None:
            raise ValueError("Action module should have an on_success.execute")

        result = self.execute_action(self.module.on_success, data)
        state.pop_module()
        return TaskSuccessResponse(result)
