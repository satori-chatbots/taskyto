import os

import pytest
import uuid

from test_utils import MockedLLM, TestConfiguration


@pytest.fixture()
def app():
    from server import FlaskChatbotApp

    chatbot_folder = "examples/yaml/bike-shop"
    mock = MockedLLM()
    mock.ai_answer(input="Hi", output="Welcome to my bike shop", prefix="New input:")
    mock.module_activation(input="I need a repair", module="make_appointment", query="{'service': 'repair'}")
    mock.ai_answer(input="Ask the Human to provide the missing data: date, time, service", output="Tell me the data!",
                   prefix="Instruction:")

    configuration = TestConfiguration(chatbot_folder, mock)

    chatbot_app = FlaskChatbotApp(configuration)
    yield chatbot_app.app
    # clean up / reset resources here


@pytest.fixture()
def client(app):
    return app.test_client()


def create_conversation(client):
    response = client.post('/conversation/new')
    assert response.status_code == 200
    assert 'id' in response.json

    id_ = response.json['id']
    # Check is response.json['id'] is a valid uuid. Exception is thrown if not.
    uuid.UUID(id_)
    return id_


def test_conversation_init(client):
    id = create_conversation(client)

    response = client.post(f'/conversation/user_message', json={"id": id, "message": "Hi"})
    assert response.status_code == 200

    data = response.json
    assert data['id'] == id
    assert data['type'] == 'chatbot_response'
    assert "Welcome to my bike shop" in data['message']


def test_conversation_steps(client):
    id = create_conversation(client)

    response = client.post(f'/conversation/user_message', json={"id": id, "message": "I need a repair"})
    assert response.status_code == 200

    data = response.json
    assert data['id'] == id
    assert data['type'] == 'chatbot_response'
    assert "Tell me the data!" in data['message']
