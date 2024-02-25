import contextlib
from typing import Optional, List

import spec
import utils
from engine.common import Configuration, ChatbotResult, DebugInfo, compute_init_module, Engine
from engine.common.memory import HumanMessage, AIResponse
from engine.custom.events import ActivateModuleEventType, UserInput, UserInputEventType, ActivateModuleEvent, \
    TaskInProgressEventType, TaskInProgressEvent, AIResponseEventType, TaskFinishEventEventType, TaskFinishEvent, \
    AIResponseEvent
from engine.custom.generator import ModuleGenerator
from engine.custom.runtime import RuntimeChatbotModule, ExecutionState, MemoryPiece
from engine.custom.statemachine import StateMachine, State, CompositeState, Initial, TriggerEventMatchByClass, Action, \
    TriggerEvent
from recording import RecordedInteraction
from spec import Visitor, ChatbotModel


class RunModuleAction(Action):

    def __init__(self, runtime_module: RuntimeChatbotModule, prompts_disabled: list[str] = []):
        self.runtime_module = runtime_module
        self.prompts_disabled = prompts_disabled

    def execute(self, execution_state, event):
        if not isinstance(event, UserInput):
            raise ValueError(f"Expected UserInput, but got {event}. No other event type is supported now.")

        self.runtime_module.run(execution_state, event.message, prompts_disabled=self.prompts_disabled)

    def __str__(self):
        disabled = " , -" + ",".join(self.prompts_disabled) if len(self.prompts_disabled) > 0 else ""
        return f"RunModuleOnInput({self.runtime_module.module.name}{disabled})"


class ApplyLLM(Action):

    def __init__(self, tool: RuntimeChatbotModule, allow_tools=True, prompts_disabled: list[str] = []):
        self.tool = tool
        self.allow_tools = allow_tools
        self.prompts_disabled = prompts_disabled

    def execute(self, execution_state, event):
        self.tool.run(execution_state, None, allow_tools=self.allow_tools, prompts_disabled=self.prompts_disabled)

    def __str__(self):
        use_tools = "with tools" if self.allow_tools else "without tools"
        disabled = " , -" + ",".join(self.prompts_disabled) if len(self.prompts_disabled) > 0 else ""
        return f"ApplyLLM({self.tool.module.name}, {use_tools}{disabled})"


class SayAction(Action):

    def __init__(self, message, consume_event=False):
        self.message = message
        self.consume_event = consume_event

    def execute(self, execution_state, event):
        who = execution_state.current.state_id()
        if self.consume_event:
            self.message = event.message

        execution_state.channel.output(self.message, who=who)
        # return ChatbotResult(self.message, DebugInfo(current_module=execution_state.current.name()))


class RunTool(Action):
    def __init__(self, tool: RuntimeChatbotModule):
        self.tool = tool

    def execute(self, execution_state, event):
        input = event.input if isinstance(event, ActivateModuleEvent) else None
        # assert isinstance(event, ActivateModuleEvent)
        self.tool.run_as_tool(execution_state, input, activating_event=event)

    def __str__(self):
        return f"RunTool({self.tool.module.name})"


class CompositeAction(Action):
    def __init__(self, actions):
        self.actions = actions

    def execute(self, execution_state, event):
        for a in self.actions:
            a.execute(execution_state, event)
            execution_state.notify_action_listeners(a)

    def __str__(self):
        return "\n".join([str(a) for a in self.actions])


class UpdateMemory(Action):

    def __init__(self, module: spec.Module, copy_from: spec.Module = None, filter=None):
        self.module = module
        self.copy_from = copy_from
        self.filter = filter

    def execute(self, execution_state, event):
        if self.copy_from is not None:
            execution_state.copy_memory(self.copy_from, self.module, 'history', filter=self.filter)
            return

        if isinstance(event, ActivateModuleEvent):
            # TODO: Do not hardcode history here... maybe ask self.module??
            execution_state.update_memory(self.module, event.previous_answer, 'history')
        elif isinstance(event, UserInput):
            memory_piece = MemoryPiece().add_human_message(event.message)
            execution_state.update_memory(self.module, memory_piece, 'history')
        elif isinstance(event, AIResponseEvent):
            memory_piece = MemoryPiece().add_ai_response(event.message)
            execution_state.update_memory(self.module, memory_piece, 'history')
        elif isinstance(event, TaskInProgressEvent) or isinstance(event, TaskFinishEvent):
            for memory_id, memory_piece in event.memory.items():
                execution_state.update_memory(self.module, memory_piece, memory_id)

    def __str__(self):
        str_copy_from = f", from {self.copy_from.name}" if self.copy_from is not None else ""
        return f"UpdateMemory({self.module.name}{str_copy_from})"


class StateMachineTransformer(Visitor):

    def __init__(self, chatbot_model: spec.ChatbotModel, configuration: Configuration):
        self.sm = StateMachine()
        self.chatbot_model = chatbot_model

        self.initial = compute_init_module(chatbot_model)
        self.module_generator = ModuleGenerator(chatbot_model, configuration, initial=self.initial)
        self.sm_stack = []

        # Configured in the specific visitor
        self.allow_go_back_to = []

    def new_state(self, sm, module: spec.Module) -> State:
        runtime_module = self.module_generator.generate(module, allow_go_back_to=self.allow_go_back_to)
        state = State(module, runtime_module)

        prompts_disabled = runtime_module.get_prompts_disabled('input')

        sm.add_transition(state, state, UserInputEventType,
                          CompositeAction([RunModuleAction(runtime_module, prompts_disabled=prompts_disabled), UpdateMemory(state.module)]))
        sm.add_transition(state, state, AIResponseEventType,
                          CompositeAction([UpdateMemory(state.module), SayAction(message=None, consume_event=True)]))

        return state

    def visit_chatbot_model(self, model: spec.ChatbotModel) -> StateMachine:
        initial_module_state = self.initial.accept(self)

        initial = Initial()
        self.sm.add_state(initial)
        self.sm.add_transition(initial, initial_module_state, None, SayAction("Hello"))

        return self.sm

    def visit_menu_module(self, module: spec.MenuModule) -> State:
        current_state = self.new_state(self.sm, module)
        self.sm.add_state(current_state)

        for item_ in module.items:
            state = item_.accept(self)
            if state is None:
                continue

            self.sm.add_state(state)

            if hasattr(state.module, 'on_success') and state.module.on_success is not None:
                action = state.module.on_success
                response = action.get_response_element()
            else:
                # The default response is to say the result
                response = spec.ResponseElement(text='{{result}}', rephrase=None)

            if response.is_direct_response() or response.is_simple_rephrase():
                # Simply rephrase is handled dynamically
                self.sm.add_transition(current_state, state, ActivateModuleEventType(state.module),
                                       CompositeAction([RunTool(state.runtime_module), UpdateMemory(state.module)]))

                self.sm.add_transition(state, current_state, TaskFinishEventEventType,
                                       CompositeAction([SayAction(None, consume_event=True)]))
            elif response.is_in_caller_rephrase():
                self.sm.add_transition(current_state, state, ActivateModuleEventType(state.module),
                                       CompositeAction(
                                           [UpdateMemory(current_state.module), RunTool(state.runtime_module),
                                            UpdateMemory(state.module)]))

                self.sm.add_transition(state, current_state, TaskFinishEventEventType,
                                       CompositeAction([UpdateMemory(current_state.module),
                                                        ApplyLLM(current_state.runtime_module, allow_tools=False)]))
            else:
                raise ValueError(f"Unsupported response type: {response}")

        return current_state

    def visit_answer_item(self, item: spec.AnswerItem) -> Optional[State]:
        return None

    def visit_action_module(self, module: spec.ActionModule) -> State:
        return self.new_state(self.sm, module)

    def visit_tool_item(self, item: spec.ToolItem) -> State:
        resolved_module = self.chatbot_model.resolve_module(item.reference)
        if isinstance(resolved_module, spec.DataGatheringModule):
            return resolved_module.accept(self)

        # TODO: Handle homogeneously
        return self.new_state(self.sm, resolved_module)

    def visit_data_gathering_module(self, module: spec.DataGatheringModule) -> State:
        state = self.new_state(self.sm, module)

        self.sm.add_transition(state, state, TaskInProgressEventType,
                               CompositeAction([UpdateMemory(state.module),
                                                ApplyLLM(state.runtime_module, allow_tools=False)]))

        self.sm.add_transition(state, state, ActivateModuleEventType(state.module),
                               CompositeAction([RunTool(state.runtime_module), UpdateMemory(state.module)]))

        return state

    @contextlib.contextmanager
    def specific_visitor(self, go_back_modules: List[RuntimeChatbotModule] = []):
        old_allow_go_back_to = self.allow_go_back_to
        self.allow_go_back_to = go_back_modules
        try:
            yield self
        finally:
            self.allow_go_back_to = old_allow_go_back_to

    def visit_sequence_item(self, item: spec.SequenceItem) -> State:
        seq_module = item.get_sequence_module()
        runtime_module = self.module_generator.generate(seq_module)

        composite = CompositeState(seq_module, runtime_module)
        self.sm_stack.append(self.sm)
        self.sm = composite

        # self.sm.add_state(composite)

        initial = Initial()
        composite.add_state(initial)

        last = initial
        last_module = None
        previous_states = []

        resolved_modules = [self.chatbot_model.resolve_module(r) for r in item.references]

        for idx, resolved_module in enumerate(resolved_modules):
            with self.specific_visitor(go_back_modules=[s.runtime_module for s in previous_states]) as visitor:
                state = resolved_module.accept(visitor)
                if seq_module.goback:
                    previous_states.append(state)

            composite.add_state(state)

            actions = [RunTool(state.runtime_module), UpdateMemory(state.module)]
            if last == initial:
                event_type = ActivateModuleEventType(state.module)
            else:
                event_type = TaskFinishEventEventType
                actions = [SayAction(message=None, consume_event=True)] + actions

                if seq_module.memory == spec.MemoryScope.full:
                    # We need to update the memory of all subsequent modules
                    for m in resolved_modules[idx:]:
                        actions.append(UpdateMemory(m, copy_from=last_module,
                                                    filter=[HumanMessage, AIResponse]))

                # Handle go back behavior if needed
                if seq_module.goback:
                    for previous_state in previous_states:
                        back_event_type = ActivateModuleEventType(previous_state.module)
                        composite.add_transition(state, previous_state, back_event_type,
                                                 CompositeAction([RunTool(previous_state.runtime_module),
                                                                  UpdateMemory(previous_state.module)]))
                        # Not sure if memory should be updated here


            composite.add_transition(last, state, event_type, CompositeAction(actions))

            last = state
            last_module = resolved_module

        # Or use a final state
        composite.add_transition(last, composite, TaskFinishEventEventType, CompositeAction([SayAction(message=None, consume_event=True), RunTool(runtime_module)]))

        self.sm = self.sm_stack.pop()

        return composite


def compute_statemachine(chatbot_model: spec.ChatbotModel, configuration: Configuration) -> StateMachine:
    transformer = StateMachineTransformer(chatbot_model, configuration)
    return chatbot_model.accept(transformer)


class CustomPromptEngine(Visitor, Engine):

    def __init__(self, chatbot_model: ChatbotModel, configuration: Configuration):
        self._chatbot_model = chatbot_model
        self.configuration = configuration  # to access the languages stored in the configuration when building prompts
        self.statemachine = compute_statemachine(chatbot_model, configuration)
        self.state_manager = None
        self.recorded_interaction = RecordedInteraction()

        self.execution_state = None

        if utils.DEBUG:
            self.statemachine.to_visualization()

    def run_all(self, channel):
        self.start(channel)
        while True:
            inp = channel.input()
            if inp is None:
                break
            self.execute_with_input(inp)

    def record_output_interaction_(self, action):
        if isinstance(action, SayAction):
            self.recorded_interaction.append(type="chatbot", message=action.message)

    def start(self, channel):
        self.execution_state = ExecutionState(self.statemachine.initial_state(), channel)
        self.execution_state.add_action_listener(self.record_output_interaction_)
        self.execute()

    def execute(self):
        while True:
            event = None
            if self.execution_state.more_events():
                event = self.execution_state.pop_event()
                transition = self.statemachine.transition_for(self.execution_state.current, event=event)
            else:
                # Check transitions with empty events
                transition = self.statemachine.transition_for(self.execution_state.current, event=event)

            if transition is None:
                if utils.DEBUG and event is not None:
                    print(f"No transition found for event: {event} in state: {self.execution_state.current}")
                break

            if utils.DEBUG:
                print(f"Executing transition: {transition} for event: {event}")

            self.execute_transition(transition, event)

    def execute_with_input(self, input_: str):
        self.recorded_interaction.append(type="user", message=input_)
        self.execution_state.push_event(UserInput(input_))
        self.execute()

    def execute_transition(self, transition, event):
        self.execution_state.current = transition.target
        if transition.trigger.action is not None:
            transition.trigger.action.execute(self.execution_state, event)
            self.execution_state.notify_action_listeners(transition.trigger.action)
