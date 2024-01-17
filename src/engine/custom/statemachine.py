import abc

import spec
import pydot


class Vertex(abc.ABC):
    pass


class Initial(Vertex):

    def __str__(self):
        return f"Initial"


class State:
    def __init__(self, module: spec.Module, runtime_module: object):
        self.module = module
        self.runtime_module = runtime_module

    def state_id(self):
        return self.module.name

    def __str__(self):
        return f"<{self.state_id()}>"


class Trigger:

    def __init__(self, event, action):
        self.event = event
        self.action = action

    def __str__(self):
        return f"{self.event}/{self.action}"

class Action(abc.ABC):

    @abc.abstractmethod
    def execute(self, execution_state, event):
        pass

    def __str__(self):
        return f"{self.__class__.__name__}"


class TriggerEvent(abc.ABC):
    @abc.abstractmethod
    def is_compatible(self, event):
        pass


class TriggerEventMatchByClass(TriggerEvent):
    def __init__(self, cls):
        self.cls = cls

    def is_compatible(self, event):
        return isinstance(event, self.cls)

    def __str__(self):
        return f"{self.cls.__name__}"


EMPTY_TRIGGER = Trigger(None, None)


class Transition:

    def __init__(self, source: Vertex, target: Vertex, trigger: Trigger):
        self.source = source
        self.target = target
        self.trigger = trigger

    def __str__(self):
        return f"{self.source} -> {self.target} [{self.trigger}]"

class StateMachine:

    def __init__(self):
        self.vertices = []
        self.transitions = []

    def add_transition(self, src: Vertex, tgt: Vertex, event=None, action=None):
        if event is None and action is None:
            trigger = EMPTY_TRIGGER
        else:
            trigger = Trigger(event, action)

        self.transitions.append(Transition(src, tgt, trigger))

    def add_state(self, current_state):
        self.vertices.append(current_state)

    def initial_state(self):
        return [v for v in self.vertices if isinstance(v, Initial)][0]

    def get_all_transitions(self):
        transitions = []
        for v in self.vertices:
            if isinstance(v, CompositeState):
                transitions.extend(v.get_all_transitions())
        transitions.extend(self.transitions)
        return transitions

    def transition_for(self, current, event):
        if isinstance(current, CompositeState):
            # Try to find a transition in the subgraph, otherwise it is probably an out-transition
            t = current.transition_for(current.initial_state(), event)
            if t is not None:
                return t

        for t in self.get_all_transitions():
            if t.source == current:
                if event is None and t.trigger.event is None:
                    return t
                elif t.trigger.event.is_compatible(event):
                    return t

        return None

    def to_visualization(self):
        graph = pydot.Dot("my_graph", graph_type="digraph", bgcolor="white", layout="dot")
        self.fill_graph_(graph)

        import tempfile
        import os

        graph.write_raw(os.path.join(tempfile.gettempdir(), "output_raw.dot"))
        graph.write_png(os.path.join(tempfile.gettempdir(), "output.png"))
        graph.write_svg(os.path.join(tempfile.gettempdir(), "output.svg"))

    @staticmethod
    def to_node_id(v, parent=None):
        node_str = str(v).replace("<", "").replace(">", "")
        if parent is None:
            return node_str
        else:
            return parent + "_" + node_str

    def fill_graph_(self, graph, parent=None):
        NODE_STYLE = {"shape": "plaintext"}

        self_transitions = {}
        for t in self.transitions:
            src = StateMachine.to_node_id(t.source, parent)
            tgt = StateMachine.to_node_id(t.target, parent)

            transition_label = str(t.trigger.event) + "/\n" + str(t.trigger.action)

            if t.source != t.target:
                graph.add_edge(pydot.Edge(src, tgt, color="blue", label=transition_label))
            else:
                if t.source not in self_transitions:
                    self_transitions[t.source] = []
                self_transitions[t.source].append(escape(transition_label))

        for v in self.vertices:
            node_id = StateMachine.to_node_id(v, parent)
            node_label = str(v)
            if v in self_transitions:
                # v_self = '<br/>'.join(self_transitions[v]).replace('\n', '<br/>')
                v_self = ''
                for vs in self_transitions[v]:
                    v_self = v_self + '<tr><td>' + vs.replace('\n', '<br/>') + '</td></tr>'

                node_label = '<<table BORDER="0" CELLBORDER="1"><tr><td BGCOLOR="lightgrey">' + escape(
                    node_label) + '</td></tr>' + v_self + '</table>>'

            if isinstance(v, CompositeState):
                subgraph = pydot.Subgraph("cluster_" + node_id, label=node_label, **NODE_STYLE)
                linking_node = pydot.Node(node_id, label="-", shape="point", width="0.01", height="0.01")
                subgraph.add_node(linking_node)

                v.fill_graph_(subgraph, node_id)
                graph.add_subgraph(subgraph)
            else:
                node = pydot.Node(node_id, label=node_label, **NODE_STYLE)
                graph.add_node(node)


def escape(str):
    return str.replace("<", "&lt;").replace(">", "&gt;")


class CompositeState(State, StateMachine):

    def __init__(self, module, runtime_module):
        State.__init__(self, module, runtime_module)
        StateMachine.__init__(self)
