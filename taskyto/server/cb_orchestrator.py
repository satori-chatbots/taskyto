from flask import Flask, request
from flask import jsonify
from flask_cors import CORS, cross_origin
from check_api_key import api_key_check

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.append(SRC_DIR)

from cb_server import ChatBotServer
from cb_server import build_message_response

from envars import DB_PORT

app = Flask(__name__)
PORT = 5000

STARTING_PORT = 5001
ENDING_PORT = 5999

SUCCESS, ERROR = 1, 0

cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'


# Command line usage

# curl -X POST -H "Content-Type: application/json" -d '{"cmd":"power", "chatbot": "beta-bot", "data":"on"}' http://localhost:5000/chatbot_manage/ctrl
chatbots = {}


@app.route('/chatbot_manage/ctrl', methods=['POST'])
@cross_origin()
def chatbot_ctrl():
    if not request.is_json:
        return {"success": ERROR,
                "debug_msg": "Request must be JSON",
                "data": None}

    request_data = request.json

    match request_data.get('cmd'):
        case 'power':
            return handle_power_req(request_data)
        case 'msg':
            return handle_msg_req(request_data)
        case 'info':
            return handle_info_req(request_data)
        case 'rename':
            return handle_rename_req(request_data)
        case 'api_key_check':
            return api_key_check(request_data)
            
        case _:
            return {"success": ERROR,
                    "debug_msg": f"cmd not recognized (different to 'power', 'msg' or 'info') -> {request_data.get('cmd')}",
                    "data": None}
def handle_rename_req(request_data: dict) -> dict:

    if not (cb_name := request_data.get('chatbot')):
        return {"success": ERROR,
                "debug_msg": "handle_rename_req(): chatbot \"chatbot (name)\" not provided",
                "data": None}

    if cb_name not in chatbots:
        return {"success": ERROR,
                "debug_msg": f"handle_rename_req(): Chatbot {cb_name} does not exist (not in dict)",
                "data": None}
    
    chatbot = chatbots[cb_name]

    if not (new_name := request_data.get('data')):
        return {"success": ERROR,
                "debug_msg": "handle_rename_req(): chatbot \"chatbot new name (data attr)\" not provided",
                "data": None}

    chatbots[new_name] = chatbot

    del chatbots[cb_name]

    return {"success": SUCCESS,
            "debug_msg": "chatbot renamed :)",
            "data": None}

def handle_power_req(request_data: dict) -> dict:
    pass

    match request_data.get('data'):
        case 'on':
            return start_server(request_data)
        case 'off':
            return stop_server(request_data)
        case _:
            return {"success": ERROR,
                    "debug_msg": "Chatbot power not recognized (different to 'on' or 'off')",
                    "data": None}


def start_server(request_data: dict) -> dict:
    # instanciar nuevo chatbot al dict

    if not (cb_name := request_data.get('chatbot')):
        return {"success": ERROR,
                "debug_msg": "start_server(): chatbot \"chatbot (name)\" not provided",
                "data": None}

    if not chatbot_exists(cb_name):

        common_msg = f"start_server(): Chatbot '{cb_name}' directory doesn't exist."
        debug_msg = f"{common_msg}. It was not added to dict neither."

        if (chatbot := chatbots.get(cb_name)):
            response = chatbot.off()
            del chatbots[cb_name]

            prefix_msg = f"{common_msg}. Deleted from dict."
            status_msg = msg if (msg := response.get(
                "debug_msg")) else "Turned off!!"

            debug_msg = f"start_server(): {prefix_msg} {status_msg}"

        return {"success": ERROR,
                "debug_msg": debug_msg,
                "data": None}

    if not (port := _reserve_port()):

        return {"success": ERROR,
                "debug_msg": "No more ports available",
                "data": None}

    chatbot: ChatBotServer

    if cb_name not in chatbots:
        chatbot = ChatBotServer(port, cb_name)

        # Adding the chatbot to the dict
        chatbots[cb_name] = chatbot

        response = chatbot.on(request_data.get("api_key"))

        if response.get("success") == ERROR:
            # If the chatbot is not running, we remove it from the dict
            del chatbots[cb_name]

        if response.get("success") == SUCCESS:
            response["debug_msg"] = "SUCCESS: Chatbot added to dict and running ;)"
        return response

    elif (chatbot := chatbots[cb_name]).port is None:
        # We asume if port is not None, the chatbot is running
        # Because its port is essential to control its execution
        chatbot.port = port

        # print("***************************************")
        # print(f"*** Chatbot '{cb_name}' assigned to port {chatbot.port} ***")
        # print("***************************************")

        response = chatbot.on(request_data.get("api_key"))

        if response.get("success") == ERROR:
            # If the chatbot is not running, we remove it from the dict
            del chatbots[cb_name]

        if response.get("success") == SUCCESS:
            response["debug_msg"] = "SUCCESS: Chatbot was already in dict but without port. Now running ;)"
        return response

    else:
        chatbot = chatbots[cb_name]
        response = chatbot.on()

        return response


def stop_server(request_data: dict) -> dict:
    # matar y eliminar chatbot del dict
    cb_name = request_data.get('chatbot')

    if not cb_name:
        return {"success": ERROR,
                "debug_msg": "stop_server(): Chatbot name not provided",
                "data": None}

    if cb_name not in chatbots:
        return {"success": ERROR,
                "debug_msg": f"stop_server(): Chatbot {cb_name} does not exist (not in dict)",
                "data": None}

    cb_server: ChatBotServer = chatbots[cb_name]

    response = cb_server.off()

    # del chatbots[cb_name]

    debug_msg = msg if (msg := response.get("debug_msg")) else ''

    if not chatbot_exists(cb_name):
        debug_msg = f"stop_server(): {debug_msg}. Additionally Chatbot '{cb_name}' directory doesn't exist."

    response["debug_msg"] = debug_msg

    return response


def handle_msg_req(request_data: dict) -> dict:

    if not (cb_name := request_data.get('chatbot')):
        return {"success": ERROR,
                "debug_msg": "handle_msg_req(): chatbot \"chatbot (name)\" not provided",
                "data": None}

    if not chatbot_exists(cb_name):

        common_msg = f"handle_msg_req(): Chatbot '{cb_name}' directory doesn't exist."
        debug_msg = f"{common_msg}. It was not added to dict neither."

        if (chatbot := chatbots.get(cb_name)):
            response = chatbot.off()
            del chatbots[cb_name]

            prefix_msg = f"{common_msg}. Deleted from dict."
            status_msg = msg if (msg := response.get(
                "debug_msg")) else "Turned off!!"

            debug_msg = f"handle_msg_req(): {prefix_msg} {status_msg}"

        return {"success": ERROR,
                "debug_msg": debug_msg,
                "data": None}

    if cb_name not in chatbots:
        return {"success": ERROR,
                "debug_msg": f"handle_msg_req(): Chatbot {cb_name} does not exist (not in dict)",
                "data": None}

    cb_server: ChatBotServer = chatbots[cb_name]

    response = send_message(cb_server, request_data.get('data'))

    # debug_msg = msg if (msg := response.get("debug_msg")) else ''

    return response

def send_message(cb_server: ChatBotServer, data: dict) -> dict:
    # enviar msg al server del dict y obtener respuesta
    debug_msg = ""
    status = SUCCESS
    incoming_debug_msg = ''

    if not cb_server:
        status = ERROR
        chatbot_none = "Chatbot server is None"
        debug_msg: str = " ".join([debug_msg, chatbot_none]).strip()

    # FABADA: 
    #       Recordemos que hay que tener en cuenta el id de la conversación!!
    #       Asumamos que ya existe y que el chatbot tiene su lista de ids

    # data: dict
    # { 
    #   message: str,
    #   conversation_id: str
    # }
    
    if isinstance(data, str):
        import json
        print(f"data -> {data}")
        data = json.loads(data)

    cb_response = cb_server.msg(data)

    incoming_debug_msg = msg if (
        msg := cb_response.get("debug_msg")) else ''
        
    if not (cb_response.get("success")):
        status = ERROR
        send_msg_error = "Unable to talk to the chatbot"

        debug_msg: str = " ".join([debug_msg, send_msg_error]).strip()

    data = cb_response.get("data")

    response = build_message_response(status, data, incoming_debug_msg, debug_msg)

    # {
    #  "success": status,
    #  "debug_msg": debug_msg,
    #  "data": data
    # }

    return response


def handle_info_req(request_data: dict) -> dict:
    
    # success
    success = SUCCESS

    # Debug message
    debug_msg = ""

    # Data
    chatbots_info: dict[str, dict] = get_chatbots_info()
    # It can be None. No problem if that happens because this
    # parameter is optional
    selected_chatbot = request_data.get('chatbot')

    data = {
        "chatbots_info": chatbots_info,
        "selected": selected_chatbot
    }

    if selected_chatbot and (selected_chatbot not in chatbots_info):
        ## There is no need to return an error if the chatbot info is ok
        # success = ERROR
        chatbot_not_found = "Chatbot not found in the chatbots info: It doesn't exist"
        debug_msg: str = " ".join([debug_msg, chatbot_not_found]).strip()

        data["selected"] = None


    # Debug message
    response = {
        "success": success,
        "debug_msg": debug_msg,
        "data": data
    }

    return response

def _reserve_port() -> int | None:
    # print("\n\n********** chatbots -> ", chatbots, " **********\n\n")
    if chatbots:
        # list of the used ports
        occupied_ports_raw = [*map(lambda x: x.port, chatbots.values())]

        # eliminating possible Nones (chatbots that are off)
        occupied_ports = [*filter(None, occupied_ports_raw)]

        # ports total range
        ports_range = range(STARTING_PORT, ENDING_PORT+1)

        try:
            # Lowest available port
            port = min(set(ports_range) - set(occupied_ports))

        except ValueError:
            print("No available ports")
            port = None
    else:
        port = STARTING_PORT

    return port


def get_chatbots_list() -> list:
    return os.listdir("/home/ubuntu/chatbot-llm/chatbots")


def get_chatbots_info() -> dict[str, str]:
    
    saved_chatbots = get_chatbots_list()

    # # Saved chatbots and the ones in the dict
    # all_chatbots = set(chatbots) | set(saved_chatbots)
    all_chatbots = set(saved_chatbots)

    chatbots_dict = {}


    for cb in all_chatbots:
        status = "off"
        url = ""
        
        if cb in chatbots and chatbots[cb].is_on():
            status = "on"
            url = f"http://{get_public_ip()}:{chatbots[cb].port}"

        chatbots_dict[cb] = {
            "status": status,
            "url": url
        }

    return chatbots_dict


def chatbot_exists(cb_name: str) -> bool:
    return cb_name in get_chatbots_list()

def get_public_ip():
    import requests
    try:
        # Make a request to an external service to get the public IP
        response = requests.get('https://api.ipify.org?format=json')
        ip_info = response.json()
        return ip_info['ip']
    except Exception as e:
        return f"Error obtaining the public IP: {str(e)}"

if __name__ == '__main__':
    # maybe una función para arrancar los chatbots que haya
    # power on all chatbots
    # ...

    # start_api
    debug_mode = os.environ.get('DEBUG_MODE', 'False').lower() in ('true', '1', 't')
    app.run(host='0.0.0.0', port=PORT, debug=debug_mode)
