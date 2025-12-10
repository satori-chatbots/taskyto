import requests
from requests import Response

import os
import sys
from colorama import Fore, Style
import readline
import json

HOST = "0.0.0.0"
PORT = 5000

CB_PROMPT_COL = Fore.LIGHTRED_EX

URL = f"http://{HOST}:{PORT}"

SUCCESS, ERROR = 1, 0

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.append(SRC_DIR)

from envars import DB_PORT

# ALTERNATIVE
# Command line usage

# This is an example (The ID must be previously generated with /new)

# curl -X POST -H "Content-Type: application/json" -d '{"id":"a5894a5d-4c9c-4449-a99e-40c1c1f95443", "message": "hi"}' http://localhost:5001/conversation/user_message

# change "/user_message" to "/new" to start a new conversation

# Monitor the chatbot servers (in chatbot-llm)

# watch -n 0.1 "netstat -nlp"

# Throught the new API (PORT 5000)
 
# curl -X POST -H "Content-Type: application/json" -d '{"cmd":"power", "chatbot": "beta-bot", "data":"on"}' http://localhost:5000/chatbot_manage/ctrl 


class Chatbot:
    def __init__(self, url: str):
        self.url = url

    def execute_with_input(self, user_msg):
        return ""


class ChatbotTaskyto(Chatbot):
    def __init__(self, url: str, id=None):
        Chatbot.__init__(self, url)
        # conversation_id = id

    def execute_with_input(self, user_msg: str, conversation_id=None, 
                           full_dict=True) -> dict:

        success = SUCCESS
        debug_msg = ""
        data = None

        print(f"DB_PORT -> {DB_PORT}")
        print(f"conversation_id -> {conversation_id}")
        print(f"user_msg -> {user_msg}")

        if conversation_id == None:
            post_response_json: dict = {}
            endpoint: str = self.url + "/conversation/new"
            # it should return {id: <id>}
            post_response: Response = requests.post(url=endpoint)


            #mirar donde se imprime
            #             Nonene
            # JSONDecodeError!!. debug_msg is not a json string
            # None
            # JSONDecodeError!!. debug_msg is not a json string

            # print(f"############################")
            # print(f"post_response -> {post_response}")
            # print(f"############################")

            ## PENING VALUE ERROR!!! -> response.json()
            try:
                # ver el tipo que de vuelve response.json()
                post_response_json = post_response.json()


                # print(f"post_response_json -> {post_response_json}")
                # print(f"type(post_response_json) -> {type(post_response_json)}")

            except ValueError:
                invalid_json = {
                    "error": "execute_with_input(): post_response.json() is not a valid JSON",
                    "endpoint": endpoint,
                }

                debug_msg: str = " ".join(
                    [debug_msg, 
                    #  json.dumps(invalid_json, indent=2)]
                    str(invalid_json)]
                ).strip()

                response = {"success": ERROR, "debug_msg": debug_msg, "data": None}
                return response

            #           pending type
            conversation_id = post_response_json.get("id")

            if not conversation_id:
                success = ERROR

                # It will be '' because this endpont only returns the id
                incomming_debug_msg = (
                    msg if (msg := post_response_json.get("debug_msg")) else ""
                )
                debug_msg: str = " ".join([debug_msg, incomming_debug_msg]).strip()

                invalid_id = "Chatbot is unable to get a new id"
                debug_msg: str = " ".join([debug_msg, invalid_id]).strip()

                response = {"success": ERROR, "debug_msg": debug_msg, "data": None}
                return response

        if conversation_id != None:
            post_response_json: dict = {}

            new_data = {"id": conversation_id, "message": user_msg}
            endpoint = self.url + "/conversation/user_message"
            

            post_response: Response = requests.post(url=endpoint, json=new_data)
            # print(f"post_response -> {post_response}")
            # print(f"post_response.text -> {post_response.text}")
            # print(f"post_response.json() -> {post_response.json()}")

            ## PENING VALUE ERROR!!! -> response.json()
            try:
                post_response_json = post_response.json()
            except ValueError:
                invalid_json = {
                    "error": "execute_with_input(): post_response.json() is not a valid JSON",
                    "endpoint": endpoint,
                }

                debug_msg: str = " ".join(
                    [debug_msg, str(invalid_json)]
                ).strip()

                response = {"success": ERROR, "debug_msg": debug_msg, "data": None}
                return response
            

            if not post_response_json.get("success"):
                success = ERROR

            incoming_debug_msg = (
                msg if (msg := post_response_json.get("debug_msg")) else ""
            )
            debug_msg: str = " ".join([debug_msg, str(incoming_debug_msg)]).strip()

            # It can be None
            data = post_response_json.get("data")

        if not full_dict:
            return data
        else:
            import json

            # return json.dumps(post_response_json, indent=2)

            response = {
                "success": success,
                # "debug_msg": json.dumps(debug_msg, indent=2),
                "debug_msg": debug_msg,
                "data": data,
            }

            return response


def get_user_input(promt_msg="User") -> str:
    prompt_msg = f"{Fore.GREEN}{promt_msg}: {Style.RESET_ALL}"
    input_msg = input(prompt_msg)

    return input_msg


def build_chatbot_rpropmpt(chatbot: Chatbot) -> str:

    # cb_id_str = f"{Fore.CYAN}{chatbot.id}{CB_PROMPT_COL}"
    # cb_prompt = f"{CB_PROMPT_COL}Bot [id: {cb_id_str}]"
    cb_prompt = f"{CB_PROMPT_COL}Bot"

    return cb_prompt


def get_chatbot_response(response_msg: str, prompt_msg="Chatbot") -> str:
    cb_response = f"{CB_PROMPT_COL}{prompt_msg}{Style.RESET_ALL}: {response_msg}"

    return cb_response


def chatbot_log(id) -> None:
    if id:
        print(f"Restoring chatbot with -> {id}")
    else:
        print("Spawning new chatbot...")


def error_and_exit(error_msg: str) -> None:
    print(f"{Fore.RED}Error: {Fore.LIGHTRED_EX}{error_msg}{Style.RESET_ALL}")
    sys.exit(1)


def main() -> None:

    # id = sys.argv[1] if len(sys.argv)>1 else None
    id = None
    port = PORT

    match len(sys.argv):
        case 1:
            # No args
            print("No args")
            print("Usage: python main.py [port] [id]")
        case 2:
            # Only port
            port = sys.argv[1]
        case 3:
            # Port and id
            port = sys.argv[1]
            id = sys.argv[2]

            chatbot_log(id)
        case _:
            print("Usage: python main.py [port] [id]")
            error_and_exit("Invalid number of arguments")

    chatbot_log(id)

    url = URL.replace(str(PORT), str(port))

    cb = ChatbotTaskyto(url, id)

    try:
        _, error = cb.execute_with_input("Hello")

        if error:
            error_and_exit(error)
    except requests.exceptions.ConnectionError as e:
        print(f"Cnnection Exception: {e}")
        error_and_exit("Chatbot Server is not ready :(")

    print("Chatbot ready!")

    try:
        while (user_msg := get_user_input("You")) != "exit":
            try:
                response_msg, error = cb.execute_with_input(user_msg, full_dict=False)

                if error:
                    error_and_exit(error)
            except requests.exceptions.ConnectionError:
                error_and_exit("Chatbot Server is disconnected :(")

            # cb_response = get_chatbot_response(response_msg, "> ")
            cb_response = get_chatbot_response(response_msg, build_chatbot_rpropmpt(cb))
            # cb_response = get_chatbot_response(response_msg)

            print(cb_response)
    except KeyboardInterrupt:
        print("exit")


if __name__ == "__main__":
    main()
    # main2()
