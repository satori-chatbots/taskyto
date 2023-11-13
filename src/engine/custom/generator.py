import spec
from engine.common import prompts, Configuration
from engine.custom.runtime import RuntimeChatbotModule, DataGatheringChatbotModule, QuestionAnsweringRuntimeModule, \
    SequenceChatbotModule, ActionChatbotModule
from spec import Visitor


class ModuleGenerator(Visitor):
    """
    This is in charge of generating the different types of modules, setting the appropriate prompts.
    """

    def __init__(self, chatbot_model: spec.ChatbotModel, configuration: Configuration):
        self.chatbot_model = chatbot_model
        self.configuration = configuration
        self.generated = {}

    def generate(self, module: spec.Module) -> RuntimeChatbotModule:
        if module.name in self.generated:
            return self.generated[module.name]

        runtime_module = module.accept(self)
        self.generated[module.name] = runtime_module
        return runtime_module

    def visit_menu_module(self, module: spec.MenuModule) -> RuntimeChatbotModule:
        prompt = module.accept(MenuModulePromptGenerator())
        tools = [i.accept(self) for i in module.items if
                 isinstance(i, spec.ToolItem) or isinstance(i, spec.SequenceItem)]

        return RuntimeChatbotModule(module=module, prompt=prompt, tools=tools, configuration=self.configuration)

    def visit_question_answering_module(self, module: spec.QuestionAnsweringModule) -> RuntimeChatbotModule:
        activation_prompt = (module.description +
                             # The list of questions is not needed in GPT-4
                             "\nThe tool is able to answer the following questions:\n" +
                             "\n".join([f"- Question: {q.question}" for q in module.questions]) +
                             "\n"
                             "\nProvide the question given by the user using the JSON format "
                             "\"question\": <question>\".\n")

        prompt = prompts.question_answering_prompt(module)
        return QuestionAnsweringRuntimeModule(module=module, prompt=prompt, activation_prompt=activation_prompt,
                                              tools=[],
                                              configuration=self.configuration)

    def visit_data_gathering_module(self, module: spec.DataGatheringModule) -> RuntimeChatbotModule:
        property_names = ", ".join([p.name for p in module.data_model.properties])

        activation_prompt = module.description
        activation_prompt = activation_prompt + "\nThe tool needs the following data:\n"
        for p in module.data_model.properties:
            if p.is_simple_type():
                activation_prompt += f'- {p.name} which is of type {p.type}\n'
            elif p.type == 'enum':
                activation_prompt += f'- {p.name} which can be one of the following values: {",".join(p.values)}\n'
            else:
                raise ValueError(f'Unknown type {p.type}')

        activation_prompt += f'\nProvide the values as JSON with the following fields: {property_names}.\n'
        activation_prompt += f"\nOnly provide the values for {property_names} if given by the user. If no value is given, provide the empty string.\n"

        prompt = (
            f"Your task is collecting the following data from the user: {property_names}. Pass this information to the corresponding tool.\n"
            f"If there is missing data, ask for it politely.\n"
            # f"Focus on the data to be collected and do not provide any other information or ask other stuff.\n"
            f"\n")
        return DataGatheringChatbotModule(module=module, prompt=prompt, activation_prompt=activation_prompt, tools=[],
                                          configuration=self.configuration)

    def visit_sequence_module(self, module: spec.SequenceModule):
        activation_prompt = module.description
        prompt = ''

        called_modules = [self.chatbot_model.resolve_module(ref) for ref in module.references]
        seq_tools = [t for m in called_modules if (t := m.accept(self)) is not None]

        for i, tool in enumerate(seq_tools[:-1]):
            seq_tools[i + 1].previous_tool = tool

        return SequenceChatbotModule(module=module, prompt=prompt, activation_prompt=activation_prompt, tools=seq_tools,
                                     configuration=self.configuration)

    def visit_action_module(self, module: spec.ActionModule):
        prompt = ""
        activation_prompt = None
        return ActionChatbotModule(module=module, prompt=prompt, tools=[],
                                     configuration=self.configuration)


    def visit_tool_item(self, item: spec.Item) -> str:
        return self.generate(self.chatbot_model.resolve_module(item.reference))

    def visit_sequence_item(self, item: spec.SequenceItem) -> str:
        seq = item.get_sequence_module()
        return self.generate(seq)


class MenuModulePromptGenerator(Visitor):
    def visit_menu_module(self, module: spec.Module) -> str:
        def handle_item(mod):
            handling = '\nThe following items specify how to handle each task:\n'
            handling = handling + '\n'.join([f'{i}: {item.accept(self)}. ' for i, item in enumerate(mod.items)])
            return handling

        prompt = prompts.menu_prompt(module, handle_item)
        return prompt

    def visit_answer_item(self, item: spec.Item) -> str:
        return f'You have to answer "{item.answer}"'

    def visit_tool_item(self, item: spec.Item) -> str:
        return f'You have to use the tool "{item.reference}"'

    def visit_sequence_item(self, item: spec.SequenceItem) -> str:
        seq = item.get_sequence_module()
        return f'You have to use the tool "{seq.name}"'
