import uuid
import os

from flask import Flask, jsonify
from flask import request

from engine.custom.runtime import Channel


class Conversation:
    def __init__(self, engine):
        self.engine = engine
        self.channel = FlaskChannel()


class FlaskChannel(Channel):

    def __init__(self):
        self.responses = []

    def clear(self):
        self.responses.clear()

    def input(self):
        raise NotImplementedError("Input is handled separately via HTTP")

    def output(self, msg, who=None):
        self.responses.append(msg)


class FlaskChatbotApp:
    def __init__(self, configuration, app: Flask = None):
        if app is None:
            app = Flask(__name__)

            # This is to setup the session, probably not the best way to do it
            os.environ['FLASK_SECRET_KEY'] = str(uuid.uuid4())
            # Load configuration from environment variables
            app.config.from_prefixed_env()

        self.configuration = configuration
        self.app = app

        self.data = {}

        def get_data():
            # I don't know if this is fully correct, it assumes that data is accessed by only one thread.
            # Session can't be used easily since we can't currently serialize a Conversation object.
            # Alternative, check: multiprocessing.Manager, memcached, redis, etc.
            return self.data

        @app.post("/conversation/new")
        def init_conversation():
            engine = configuration.new_engine()

            # Generate an unique uuid
            id = str(uuid.uuid4())
            conversation = Conversation(engine)
            get_data()[id] = conversation

            engine.start(conversation.channel)

            return jsonify({"id": id})

        @app.post('/conversation/user_message')
        def user_message():
            id = request.json['id']
            message = request.json['message']

            conversation = get_data()[id]
            conversation.channel.clear()

            conversation.engine.execute_with_input(message)

            chatbot_response = "\n".join(conversation.channel.responses)
            return jsonify({"id": id, "type": "chatbot_response", "message": chatbot_response})

    def run(self):
        self.app.run()
