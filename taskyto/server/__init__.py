import uuid
import os

from flask import Flask, jsonify
from flask import request

import json

## FABADA: Ver si el nuevo imort de abajo funciona
from taskyto.engine.custom.runtime import Channel
# from engine.custom.runtime import Channel

import datetime

SUCCESS, ERROR = 1, 0


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

    def thinking(self, text: str):
        pass

    def stop_thinking(self):
        pass

class FlaskChatbotApp:
    def __init__(self, configuration, app: Flask = None):
        if app is None:
            app = Flask(__name__)

            # This is to setup the session, probably not the best way to do it
            os.environ["FLASK_SECRET_KEY"] = str(uuid.uuid4())
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

        @app.post("/conversation/user_message")
        def user_message():
            success = SUCCESS
            debug_msg = ""
            data = None

            if not request.is_json:
                success = ERROR

                no_json_request = "Request must be JSON"
                debug_msg: str = " ".join([debug_msg, no_json_request]).strip()

                print(no_json_request)

                response = _user_message_payload(request, debug_msg, success, data)
                return jsonify(response)

            # They can be None
            id = request.json.get("id")
            message = request.json.get("message")

            print(f"message: {message}")

            import os

            os.system(f"echo \"message: {message}\, id: {id}\" > /tmp/message.txt")


            # At least one key (message, id) is None or is missing in the request
            if None in (id, message):
                success = ERROR
                wrong_format = "At least one key (message, id) is None or is missing in the request."
                debug_msg: str = " ".join([debug_msg, wrong_format]).strip()

                print(wrong_format)

            valid_id = id and (conversation := get_data().get(id))

            if not valid_id:
                success = ERROR
                invalid_id = f"Invalid conversation id."
                debug_msg: str = " ".join([debug_msg, invalid_id]).strip()

                print(invalid_id)

            if success == ERROR:
                response = _user_message_payload(request, debug_msg, success, data)
                return jsonify(response)

            # Success if we reach this point

            # FABADA: UNABLE TO get the stderr in case the chatbot, for watever reason fails.

            a = conversation.channel.clear()
            os.system(f"echo \"{a}\" > /tmp/debug.txt")
            b = conversation.engine.execute_with_input(message)
            os.system(f"echo \"b-> {b}\" > /tmp/debug.txt")


            chatbot_response = "\n".join(conversation.channel.responses)
            
            data = {
                "id": id, 
                "type": "chatbot_response", 
                "message": chatbot_response,
                "timestamp": datetime.datetime.now().strftime("%d/%m/%Y, %H:%M:%S")
            }


            response = _user_message_payload(request, debug_msg, success, data)

            return jsonify(response)

        def _user_message_payload(
            request, debug_msg: str, success: int, data: None | dict
        ) -> dict:
            debug_dict = _user_msg_debug_dict(request, debug_msg)

            debug_dict = json.dumps(debug_dict, indent=4)

            response = {
                "success": success,
                "debug_msg": debug_dict,
                "data": data,
            }

            return response

        def _user_msg_debug_dict(request, debug_msg: str) -> dict:
            expected_body = {"id": "<conversation id>", "message": "<message>"}

            your_request = {"your_URL": request.base_url, "your_body": request.json}

            debug_dict = {
                "your_request": your_request,
                "expected_body": expected_body,
                "debug_msg": debug_msg if debug_msg else "All Ok :)",
            }

            return debug_dict

    def run(self, host, port, debug=True):

        self.app.run(debug=debug, host=host, port=port)
