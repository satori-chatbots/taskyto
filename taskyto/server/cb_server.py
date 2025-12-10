import time
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.append(SRC_DIR)

ROOT_DIR = os.path.dirname(SRC_DIR)

from client.main import URL, PORT
from client.main import ChatbotTaskyto

import time
import json

from envars import DB_PORT
from icecream import ic

SIGINT = 2

SUCCESS, ERROR = 1, 0


class ChatBotServer:

    def __init__(self, port, name) -> None:
        self._port = port
        self.name = name
        self.cb = ChatbotTaskyto(URL.replace(str(PORT), str(port)))

    @property
    def port(self):
        return self._port
    
    @port.setter
    def port(self, value):
        # Updating the chatbot url when updating the port

        # print("\033[92m" + "========== Before Port Update ==========" + "\033[0m")
        # print(f"\033[92mself._port: {self._port}\033[0m")
        # print(f"\033[92mvalue: {value}\033[0m")
        # print(f"\033[92mself.cb.url: {self.cb.url}\033[0m")
        
        self.cb.url = self.cb.url.replace(str(self._port), str(value))
        self._port = value
        
        # print("\033[93m" + "========== After Port Update ==========" + "\033[0m")
        # print(f"\033[93mself._port: {self._port}\033[0m")
        # print(f"\033[93mvalue: {value}\033[0m")
        # print(f"\033[93mself.cb.url: {self.cb.url}\033[0m")

    def on(self, api_key: str=None) -> dict:
        # check if it is off
        if self.is_on():
            print('Server is already on')

            return {"success": SUCCESS,
                    "debug_msg": "server is already on",
                    "data": None}

        ########################################################
        # If the server is not started yet
        ########################################################

        # python_path = os.getenv("PYTHON_PATH", "/.venv/bin/python")
        NAME_TOKEN = "%name%"
        PORT_TOKEN = "%port%"
        
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
            # ic("ha pasao")
        # ic(api_key)
        
        raw_cmd = f"sudo --preserve-env=OPENAI_API_KEY -u ubuntu /.venv/bin/python /home/ubuntu/chatbot-llm/taskyto/serve.py --chatbot /home/ubuntu/chatbot-llm/chatbots/%name%/ --port %port% &"


        cmd = raw_cmd.replace(NAME_TOKEN, self.name).replace(
            PORT_TOKEN, str(self.port))

        # print("cmd: ", cmd)
        # out = self._execute_cmd(cmd, True)

        # out = json.dumps(out, indent=4)
        # stderr = self._execute_cmd(cmd, True)
        stderr = self._execute_cmd2(cmd, True)
        if stderr:
            print("====================")
            print("stderr: ", stderr)
            print("====================")
        else:
            print("No stderr output, command executed successfully.")

        threshold = 600
        i = 0
        while not (status := SUCCESS if self.is_on() else ERROR):
            time.sleep(0.1)
            i+=1
            if i > threshold:
                break


        err_msg = '' if status else f"Chatbot {self.name} could not be started :(. Error: {stderr}"

        # err_msg = json.dumps(err_msg, indent=4)


        # print(f"on->status: {status}")
        # print(f"on->err_msg: {err_msg}")

        response = {"success": status,
                    "debug_msg": err_msg,
                    "data": None}

        return response

    def off(self) -> dict:

        success = SUCCESS

        if self.is_on():
            success = self._kill_server()
            self.port = None if success else self.port

        err_msg = '' if success else f"Chatbot '{self.name}' is still running :("

        if success:
            pass
            # ******FABADA: MongoDB******
            # Poner todas las conversaciones a <is_dead = True>

        return {"success": success,
                "debug_msg": err_msg,
                "data": None}

    def msg(self, data: dict) -> dict:
        pass
        

        success = SUCCESS
        debug_msg = ''
        incoming_debug_msg = ''

        # print("********** SERVER DETAILS **********")
        # print(f"Server Name: {self.name}")
        # print(f"Server Port: {self.port}")
        # print("********** CHATBOT DETAILS **********")
        # print(f"Chatbot URL: {self.cb.url}")
        # print(f"Chatbot ID: {self.cb.id}")
        # print("************************************")

        
        # Pending error control
        # It should return the response dict we are used to
        print(f"data: {data}")
        print(f"data type: {type(data)}")
        print(f"data type: {data.get('message')}")
        print(f"[*data.keys()]: {[*data.keys()]}")

        if not self.is_on():
            success = ERROR
            server_off = "Chatbot server is off"
            debug_msg: str = " ".join([debug_msg, server_off]).strip()


        else:
            # Communicate with the chatbot using port <puerto self.cb.port>
            # ******FABADA: Tener en cuenta la id!!!! ******
            response = self.cb.execute_with_input(
                user_msg = data.get("message"),
                conversation_id = data.get("conversation_id")
            )
            success = SUCCESS if (response.get("success")) else ERROR
            data = response.get("data")

            incoming_debug_msg: dict | str = msg if (
                msg := response.get("debug_msg")) else ''
            
            
            # debug_msg: str = " ".join([debug_msg, incoming_debug_msg]).strip()

        response = build_message_response(success, data, incoming_debug_msg, debug_msg)
        # print(f"response: {json.dumps(response, indent=4)}")
        # print(f"'debug_msg' type: {type(response.get('debug_msg'))}")

        return response

    print("-------------------")

    def is_on(self) -> bool:
        pid = self._get_pid()
        return bool(pid)
    
    # def _execute_cmd(self, cmd: str, show_output=False) -> str:
        
    #     # Create a unique temp file name
    #     timestamp = int(time.time())
    #     temp_file = f"/tmp/server_output_{timestamp}"

    #     print()
    #     tmp_cmd = cmd.strip(" &")
    #     print(f"Executing command: {tmp_cmd}")
    #     print()

    #     # Initialize output variable
    #     output = ""
        
    #     modified_cmd = tmp_cmd + f" > {temp_file} 2>&1 &"
    #     os.system(modified_cmd)

    #     # Wait a bit for output to be written
    #     time.sleep(5)

    #     # Read the output
    #     try:
    #         print(f"Reading output from: {temp_file}")
    #         with open(temp_file, 'r') as f:
    #             output = f.read()
    #             if show_output:
    #                 print(f"Command output: {output}")
    #     except FileNotFoundError:
    #         print("No output file found.")
    #         output = "Error: Command output not captured"

    #     # Clean up
    #     try:
    #         os.remove(temp_file)
    #     except:
    #         pass

    #     return output
    
    def _execute_cmd2(self, raw_cmd: str, show_output=False) -> str:
        import subprocess

        # cmd = raw_cmd.split(" ")
        raw_cmd = raw_cmd.strip(" &")
        print(f"Executing command: {raw_cmd}")
        print()
        cmd = raw_cmd.split(" ")

        try:
            # Start the process without waiting for completion
            process = subprocess.Popen(raw_cmd, shell=True, 
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            # Wait briefly to catch immediate failures
            time.sleep(2)
            
            # Check if it failed immediately
            if process.poll() is not None:
                _, stderr = process.communicate()
                return stderr or "Process failed with no error output"
            
            # Process is running in background
            return ""
        except Exception as e:
            return f"Failed to execute command: {str(e)}"

       

        
       


    def _get_pid(self) -> int | None:
        import subprocess

        get_pid_cmd = \
            f"netstat -nlp 2>/dev/null | grep :{self.port} | awk '{{print $7}}'"

        raw_pid = subprocess.getoutput(get_pid_cmd)
        pid_str = raw_pid.split("/")[0]

        # FABADA: Actualizar la DB con el estado en el que se encuentre
        # ON or OFF (bool(int(pid_str)))

        pid = None

        try:
            pid = int(pid_str)
        except ValueError:
            pass

        # print(f"raw_pid: {raw_pid}")
        # print(f"pid_str: {pid_str}")

        return pid

    def _kill_server(self) -> int:
        import signal

        THRESHOLD = 4
        count = 0

        while pid_str := self._get_pid():
            os.kill(pid_str, signal.SIGKILL)
            count += 1

            if count > THRESHOLD:
                time.sleep(1)
                status = ERROR if self.is_on() else SUCCESS
                return status

        return SUCCESS
    
def build_message_response(success: int, data: None | dict, incoming_debug_msg: dict | str, append_debug_msg: str = None) -> dict:

    print(data)

    debug_msg = _user_message_debug_msg(incoming_debug_msg, append_debug_msg)

    response = {
        "success": success,
        "debug_msg": debug_msg,
        "data": data,
    }

    return response

def _user_message_debug_msg(incoming_debug_msg: dict | str, append_debug_msg: str = None) -> dict | str: 

    debug_msg = ''

    # We assume that append_debug_msg will always be a string
    append_debug_msg = append_debug_msg if append_debug_msg else ''
    try:
        incoming_debug_msg = json.loads(incoming_debug_msg) if isinstance(incoming_debug_msg, str) else incoming_debug_msg
    except json.JSONDecodeError:
        pass
        print("JSONDecodeError!!. debug_msg is not a json string")
    

    match incoming_debug_msg:
        case str():
            debug_msg: str = " ".join([incoming_debug_msg, append_debug_msg]).strip()

        case dict():
            current_debug_msg = msg if (msg:=incoming_debug_msg.get("debug_msg")) else ''

            temp_debug_msg = " ".join([current_debug_msg, append_debug_msg]).strip()
            
            incoming_debug_msg["debug_msg"] = temp_debug_msg if temp_debug_msg else "All Ok :)"
            
            debug_msg = incoming_debug_msg
        case _:
            pass

    
    return debug_msg

def test2(port=5005):
    import subprocess
    import time

    cmd = f"/.venv/bin/python /home/ubuntu/chatbot-llm/taskyto/serve.py --chatbot chatbots/test/ --port {port} &"

    os.system(cmd)

    get_cmd_pid = f"pgrep -f \"{cmd}\""
    pid = subprocess.getoutput(get_cmd_pid)

    print("-------------------")
    print(f"PID: {pid}")
    print("-------------------")


if __name__ == '__main__':

    arg = None
    if len(sys.argv) > 1:
        arg = sys.argv[1]

    # test2(arg)
    print(SRC_DIR)
