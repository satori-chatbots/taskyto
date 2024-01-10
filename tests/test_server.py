import os

import pytest
import uuid


@pytest.fixture()
def app():
    from server import FlaskChatbotApp
    from main import CustomConfiguration
    import main
    import utils

    utils.check_keys(["OPENAI_API_KEY"])

    chatbot_folder = "examples/yaml/bike-shop"
    config_model = main.load_configuration_model(chatbot_folder)
    configuration = CustomConfiguration(chatbot_folder, config_model)

    chatbot_app = FlaskChatbotApp(configuration)
    yield chatbot_app.app
    # clean up / reset resources here


@pytest.fixture()
def client(app):
    return app.test_client()


def test_conversation_init(client):
    response = client.post('/conversation/new')
    assert response.status_code == 200
    assert 'id' in response.json

    id = response.json['id']
    # Check is response.json['id'] is a valid uuid. Exception is thrown if not.
    uuid.UUID(id)

    response = client.post(f'/conversation/user_message', json={"id": id, "message": "Hi"})
    assert response.status_code == 200

    data = response.json
    assert data['id'] == id
    assert data['type'] == 'chatbot_response'
    assert "Welcome to my bike shop" in data['message']

