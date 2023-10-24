from typing import List

from pydantic import BaseModel


class InteractionItem(BaseModel):
    type: str
    message: str


class RecordedInteraction(BaseModel):
    interactions: List[InteractionItem] = []

    def append(self, type, message):
        self.interactions.append(InteractionItem(type=type, message=message))


def dump_test_recording(recording: RecordedInteraction, file: str):
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

    import yaml
    yaml.dump(data, open(file, "w"))
