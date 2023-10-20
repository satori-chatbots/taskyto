import os

import pytest

from main import load_chatbot_model


@pytest.mark.parametrize("name", [
    "bike-shop",
    "smart_calculator",
    "song-recommender"
])
def test_chatbot_model(name):
    path = os.path.join("examples", "yaml", name)
    model = load_chatbot_model(path)
    assert model is not None