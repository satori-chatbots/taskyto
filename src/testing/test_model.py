from typing import Literal, List

import pydantic
from pydantic import BaseModel, Field


class InteractionElement(BaseModel):
    pass


class UserSays(InteractionElement):
    message: str


class ChatbotAnswer(InteractionElement):
    answers: List[str] = []


class Interaction(BaseModel):
    interactions: List[InteractionElement]

