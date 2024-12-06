from typing import List, Optional

from pydantic import BaseModel

from engine.custom.statemachine import Transition


class InteractionItem(BaseModel):
    type: str
    message: str

class InternalTraceItem(BaseModel):
    type: str
    event: object
    #transition: str

class RecordedInteraction(BaseModel):
    interactions: List[InteractionItem] = []
    trace: List[InternalTraceItem] = []
    response_times: List[float] = []

    def append(self, type, message):
        self.interactions.append(InteractionItem(type=type, message=message))

    #def append_trace(self, event, transition: Optional[Transition]):
    def append_trace(self, event):
        self.trace.append(InternalTraceItem(type='event-transition',
                                            event=event.to_dict()))
                                            #transition=transition.to_dict() if transition else None))

    def record_response_time(self, time):
        self.response_times.append(time)

    def average_response_time(self):
        if len(self.response_times) ==0: return 0
        return sum(self.response_times) / len(self.response_times)


def _dump_trace(recording, data):
    data["trace"] = []
    for i in recording.trace:
        data["trace"].append(dict(i))

def dump_test_recording(recording: RecordedInteraction, file: str, trace=False):
    if file is None:
        return

    data = dict()
    data["interaction"] = []
    for i in recording.interactions:
        if i.type == "user":
            data["interaction"].append(dict(user=i.message))
        elif i.type == "chatbot":
            data["interaction"].append(dict(chatbot=[i.message]))
        else:
            raise ValueError("Unknown interaction type", i.type)

    if trace:
        _dump_trace(recording, data)

    import yaml
    with open(file, "w") as f:
        yaml.dump(data, f)
