from typing import Optional

import spec
from engine.common import Configuration, ChatbotResult, DebugInfo, compute_init_module
from engine.custom.events import ActivateModuleEventType, UserInput, UserInputEventType, ActivateModuleEvent, \
    TaskInProgressEventType, TaskInProgressEvent, AIResponseEventType, TaskFinishEventEventType, TaskFinishEvent
from engine.custom.generator import ModuleGenerator
from engine.custom.runtime import RuntimeChatbotModule, ExecutionState, MemoryPiece
from engine.custom.statemachine import StateMachine, State, CompositeState, Initial, TriggerEventMatchByClass, Action, \
    TriggerEvent
from recording import RecordedInteraction
from spec import Visitor, ChatbotModel


class RunModuleAction(Action):

    def __init__(self, runtime_module: RuntimeChatbotModule):
        self.runtime_module = runtime_module

    def execute(self, execution_state, event):
        if not isinstance(event, UserInput):
            raise ValueError(f"Expected UserInput, but got {event}. No other event type is supported now.")

        self.runtime_module.run(execution_state, event.message)

    def __str__(self):
        return f"RunModuleOnInput({self.runtime_module.module.name})"

class ApplyLLM(Action):

    def __init__(self, tool: RuntimeChatbotModule):
        self.tool = tool

    def execute(self, execution_state, event):
        self.tool.run(execution_state, None)

    def __str__(self):
        return f"ApplyLLM({self.tool.module.name})"


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

    def __init__(self, module: spec.Module):
        self.module = module

    def execute(self, execution_state, event):
        if isinstance(event, ActivateModuleEvent):
            execution_state.update_memory(self.module, event.previous_answer)
        elif isinstance(event, TaskInProgressEvent):
            execution_state.update_memory(self.module, MemoryPiece(input=None, output="Observation: " + event.continuation_prompt))
        elif isinstance(event, TaskFinishEvent):
            execution_state.update_memory(self.module, MemoryPiece(input=None, output="Observation: " + event.message))

    def __str__(self):
        return f"UpdateMemory({self.module.name})"

class StateMachineTransformer(Visitor):

    def __init__(self, chatbot_model: spec.ChatbotModel, configuration: Configuration):
        self.sm = StateMachine()
        self.chatbot_model = chatbot_model

        self.module_generator = ModuleGenerator(chatbot_model, configuration)
        self.sm_stack = []

    def new_state(self, sm, module: spec.Module) -> State:
        runtime_module = self.module_generator.generate(module)
        state = State(module, runtime_module)

        sm.add_transition(state, state, UserInputEventType, RunModuleAction(runtime_module))
        sm.add_transition(state, state, AIResponseEventType, SayAction(message=None, consume_event=True))

        return state

    def visit_chatbot_model(self, model: spec.ChatbotModel) -> StateMachine:
        initial = compute_init_module(model)
        # nodes_by_name = [{m.name: State(m)} for m in model.modules]

        initial_module_state = initial.accept(self)

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

            if hasattr(state.module, 'on_success'):
                action = state.module.on_success
                response = action.get_response_element()
                if response.is_direct_response():
                    self.sm.add_transition(current_state, state, ActivateModuleEventType(state.module),
                                           CompositeAction([RunTool(state.runtime_module), UpdateMemory(state.module)]))

                    self.sm.add_transition(state, current_state, TaskFinishEventEventType,
                                           CompositeAction([SayAction(None, consume_event=True)]))
                elif response.is_in_caller_rephrase():
                    self.sm.add_transition(current_state, state, ActivateModuleEventType(state.module),
                                           CompositeAction([UpdateMemory(current_state.module), RunTool(state.runtime_module), UpdateMemory(state.module)]))

                    self.sm.add_transition(state, current_state, TaskFinishEventEventType,
                                           CompositeAction([UpdateMemory(current_state.module), ApplyLLM(current_state.runtime_module)]))
                else:
                    raise ValueError(f"Unsupported response type: {response}")
            else:
                # TODO: Decide which is the default kind of response
                self.sm.add_transition(current_state, state, ActivateModuleEventType(state.module),
                                       CompositeAction([RunTool(state.runtime_module), UpdateMemory(state.module)]))

                self.sm.add_transition(state, current_state, TaskFinishEventEventType,
                                       CompositeAction([SayAction(None, consume_event=True)]))

                #self.sm.add_transition(state, current_state, TaskFinishEventEventType,
                #                       CompositeAction([UpdateMemory(current_state.module), ApplyLLM(current_state.runtime_module)]))

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
                               CompositeAction([UpdateMemory(state.module), ApplyLLM(state.runtime_module)]))

        self.sm.add_transition(state, state, ActivateModuleEventType(state.module),
                               CompositeAction([RunTool(state.runtime_module), UpdateMemory(state.module)]))

        return state

    def visit_sequence_item(self, item: spec.SequenceItem) -> State:
        seq_module = item.get_sequence_module()
        runtime_module = self.module_generator.generate(seq_module)

        composite = CompositeState(seq_module, runtime_module)
        self.sm_stack.append(self.sm)
        self.sm = composite

        #self.sm.add_state(composite)

        initial = Initial()
        composite.add_state(initial)

        last = initial
        for r in item.references:
            resolved_module = self.chatbot_model.resolve_module(r)
            #state = self.new_state(composite, resolved_module)
            state = resolved_module.accept(self)
            composite.add_state(state)

            event_type = ActivateModuleEventType(state.module) if last == initial else TaskFinishEventEventType

            composite.add_transition(last, state, event_type,
                                     CompositeAction([RunTool(state.runtime_module), UpdateMemory(state.module)]))
            last = state

        # Or use a final state
        composite.add_transition(last, composite, TaskFinishEventEventType, CompositeAction([RunTool(runtime_module)]))

        self.sm = self.sm_stack.pop()

        return composite


def compute_statemachine(chatbot_model: spec.ChatbotModel, configuration: Configuration) -> StateMachine:
    transformer = StateMachineTransformer(chatbot_model, configuration)
    return chatbot_model.accept(transformer)


class CustomPromptEngine(Visitor):
    DEBUG = True

    def __init__(self, chatbot_model: ChatbotModel, configuration: Configuration):
        self._chatbot_model = chatbot_model
        self.statemachine = compute_statemachine(chatbot_model, configuration)
        self.configuration = configuration
        self.state_manager = None
        self.recorded_interaction = RecordedInteraction()

        self.execution_state = None

        if self.DEBUG:
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


    def execute(self) -> ChatbotResult:
        while True:
            event = None
            if self.execution_state.more_events():
                event = self.execution_state.pop_event()
                transition = self.statemachine.transition_for(self.execution_state.current, event=event)
            else:
                # Check transitions with empty events
                transition = self.statemachine.transition_for(self.execution_state.current, event=event)

            if transition is None:
                break

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
