import os

import pytest

from main import load_chatbot_model
from testing.reader import load_test_model


@pytest.mark.parametrize("name", [
    "bike-shop",
    "smart_calculator",
    "song-recommender"
])
def test_chatbot_model(name):
    path = os.path.join("examples", "yaml", name)
    model = load_chatbot_model(path)
    assert model is not None
    assert len(model.modules) >= 1


@pytest.mark.parametrize("name", [
    "bike-shop"
])
def test_test_model(name):
    path = os.path.join("examples", "yaml", name, "tests")
    model = load_test_model(path)
    assert model is not None