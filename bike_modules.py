from typing import Optional

from langchain.callbacks.manager import CallbackManagerForToolRun, AsyncCallbackManagerForToolRun
from langchain.tools import BaseTool

from modules import ChatbotModule, State


class TopLevel(ChatbotModule):
    def __init__(self, state: State):
        self.state = state

    def get_prompt(self):
        return f"""   
        You are a chatbot which helps users of a bike shop.

        You are able to assist only in these aspects:
        - Hours
        - Make Appointment
        - Welcome

        For any question not related to these aspects you have to answer:
        "I'm sorry it's a little loud in my shop, can you say that again?" 
        
        ANSWERS:
        --------
        - Hours: every weekday from 9am to 5:30pm
        
        """

    def get_tools(self):
        return [MakeAppointmentTool(state=self.state)]

class MakeAppointmentTool(BaseTool):
    name = "make appointment tool"
    description = """
        Useful for registering appointments.
        Today is 2023-06-21 15:00:00.
        The tool needs the date and the time of the appointment and
        the type of service. There are two service options: repair or tune-up.
        Provide the values as JSON with three fields: date, time and service.
        
        Only provide the date and/or time and/or service type if given by the user. 
        If no date, time and service type is given, provide the empty string.
        """
    state: State = None

    def __init__(self, state):
        super().__init__()
        assert state is not None
        self.state = state

    def _run(self, query: str, run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        try:
            import json
            json_query = json.loads(query)
            date = json_query["date"] if "date" in json_query else None
            time = json_query["time"] if "time" in json_query else None
            service = json_query["service"] if "service" in json_query else None

            if date is not None and time is not None and service is not None:
                if not (date.strip() == "" or time.strip() == "" or service.strip() == ""):
                    if self.state.is_module_active(MakeAppointmentModule):
                        self.state.pop_module()
                    return "The appointment has been registered at " + date + " " + time + "."
        except:
            pass

        if not self.state.is_module_active(MakeAppointmentModule):
            self.state.push_module(MakeAppointmentModule(self.state))

        return "Do not use the make appointment tool and ask the user the following: \"Please provide the date and " \
               "time and type of service of the appointment."

    async def _arun(
            self,
            query: str,
            run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        raise NotImplementedError("LogOutTool does not support async")

class MakeAppointmentModule(ChatbotModule):
    def __init__(self, state: State):
        self.state = state

    def get_prompt(self):
        return f"""   
        You are a chatbot which helps users of a bike shop.
        
        Ask the date and time of the appointment all the time.
        """

    def get_tools(self):
        return [MakeAppointmentTool(state=self.state)]
