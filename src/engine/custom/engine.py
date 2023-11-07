from engine.common import Configuration, compute_init_module, ChatbotResult, DebugInfo
from engine.custom.generator import ModuleGenerator
from engine.custom.runtime import RuntimeChatbotModule
from recording import RecordedInteraction
from spec import Visitor, ChatbotModel


class CustomPromptEngine(Visitor):
    def __init__(self, chatbot_model: ChatbotModel, configuration: Configuration):
        self._chatbot_model = chatbot_model
        self._init_module = compute_init_module(chatbot_model)
        self.configuration = configuration
        self.state_manager = None
        self.recorded_interaction = RecordedInteraction()

    def first_action(self) -> ChatbotResult:
        self.state_manager = self.configuration.new_state()

        module: RuntimeChatbotModule = ModuleGenerator(self._chatbot_model, self.configuration).generate(self._init_module)
        self.state_manager.push_module(module)

        initial_msg = "Hello"
        self.recorded_interaction.append(type="chatbot", message=initial_msg)
        return ChatbotResult(initial_msg, DebugInfo(current_module=self._init_module.name))


    def run_step(self, query: str) -> ChatbotResult:
        self.recorded_interaction.append(type="user", message=query)

        current = self.state_manager.current_state()
        response = current.module.run(self.state_manager, input=query)

        ans = response.message
        self.recorded_interaction.append(type="chatbot", message=ans)

        module_name = self.state_manager.current_state().module.name()  # type(self._current_state.current_module()).__name__
        return ChatbotResult(ans, DebugInfo(current_module=module_name))