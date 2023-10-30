import traceback
from typing import Optional

from langchain.callbacks.manager import CallbackManagerForToolRun, AsyncCallbackManagerForToolRun
from langchain.indexes.vectorstore import VectorStoreIndexWrapper
from langchain.tools import BaseTool, Tool
from langchain.utilities import SerpAPIWrapper

from engine.langchain.modules import ChatbotModule, State


class TopLevel(ChatbotModule):
    def __init__(self, state: State):
        self.state = state

    def get_prompt(self):
        return f"""   
        You are a chatbot which helps users of the HealthyAI platform. HealthyAI is a platform designed to help humans keep fit.

        You are able to assist only in these aspects:
        - Provide general information about the platform. For example, questions like "What can you do for me?" or "What is this platform about?"
        - Request to login into the platform.
        - Request to register into the platform.

        For any question not related to these three aspects you have to answer: "You need to login or register first.". 
        Examples of questions that need to be answered like this are:
        - Which are the calories of a meal?
        - How many calories can I burn in a workout?
         
        """

    def get_tools(self):
        return [RegisterTool(state=self.state)]


class LoggedInModule(ChatbotModule):
    def get_prompt(self):
        PREFIX_GENERAL = """HealthyAI is a chatbot designed to help humans to keep fit.

        As a friendly chatbot, HealthyAI is able to generate human-like text based on the input it receives, allowing it to
        engage in natural-sounding conversations and provide responses that are coherent and relevant to the topic at hand.

        """

        PREFIX_REGISTERED = f"""{PREFIX_GENERAL}   
        You are in normal mode, which means that are able to assist in these aspects:
        - Request about the calories of a meal.
        - Request about the calories burned in a workout.
        - Request information about specific workouts, how to exercise muscles, etc.
        - Request to log out from the platform.

        Any user request outside these aspects will be ignored and you have to answer: "This is out of my scope."

        HealthyAI should not ask for any other information.

        Overall, HealthyAI is a powerful chatbot that can help with those tasks and provide valuable insights and information for the user to keep fit.
        """

        return PREFIX_REGISTERED

    def get_tools(self):
        search = SerpAPIWrapper()
        all_tools = [
            Tool(
                name="Search tool",
                func=search.run,
                description="useful for searching which are the calories of a meal and the calories burned in a workout"
            ),
            LogOutTool(state=self.state),
            RegisterExerciseTool(state=self.state),
            QueryExerciseDBTool(state=self.state),
            DocumentSearchTool(state=self.state)
        ]
        return all_tools


class TracingExercisesModule(ChatbotModule):
    def get_prompt(self):
        return """
                    HealthyAI is a chatbot designed to help humans to keep fit.
                    You are the exercise registration chatbot of Healthy AI. 
                    You are in charge of getting the exercise and time from the user and query the exercise dataset."""

    def get_tools(self):
        all_tools = [
            LogOutTool(state=self.state),
            RegisterExerciseTool(state=self.state),
            QueryExerciseDBTool(state=self.state)
        ]
        return all_tools


class LogOutTool(BaseTool):
    name = "logout tool"
    description = """
        Useful for logging out from the Healthy platform. 
        """
    state: State = None

    def __init__(self, state):
        super().__init__()
        assert state is not None
        self.state = state

    def _run(self, query: str, run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        self.state.pop_module()
        return "Tell the user that you have been logged out. Ask the user what to do next."

    async def _arun(
            self,
            query: str,
            run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        raise NotImplementedError("LogOutTool does not support async")


class DocumentSearchTool(BaseTool):
    name = "document search tool"
    description = """
        Useful for searching information about workouts, how to exercise muscles, etc.
        """
    state: State = None
    index: VectorStoreIndexWrapper = None

    def __init__(self, state):
        super().__init__()
        assert state is not None
        self.state = state

        from langchain.document_loaders import PyPDFLoader
        loader = PyPDFLoader("data/body-building.pdf")
        from langchain.embeddings import HuggingFaceEmbeddings
        embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        from langchain.indexes import VectorstoreIndexCreator
        self.index = VectorstoreIndexCreator(embedding=embeddings).from_loaders([loader])

    def _run(self, query: str, run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        result = self.index.query_with_sources(query)
        return result

    async def _arun(
            self,
            query: str,
            run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        raise NotImplementedError("DocumentSearchTool does not support async")


class RegistrationModule(ChatbotModule):
    def get_prompt(self):
        return """
            HealthyAI is a chatbot designed to help humans to keep fit.
            You are the registration chatbot of Healthy AI. You are in charge of getting the user and password of the user."""

    def get_tools(self):
        return [RegisterTool(state=self.state)]


class RegisterTool(BaseTool):
    name = "registration tool"
    description = """
        Useful for performing the registration in the Healthy platform. 
        Only provide the username and/or password if given by the user. Use a JSON format to pass the input with keys username and password. 
        If no username or password is given, provide the empty string.
        
        The result is whether is logged in or not. If logged in, ask the user what to do next.
        """
    user_password = []
    state: State = None

    def __init__(self, state):
        super().__init__()
        assert state is not None
        self.state = state

    def _run(self, query: str, run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        try:
            import json
            json_query = json.loads(query)
            user = json_query["username"] if "username" in json_query else None
            password = json_query["password"] if "password" in json_query else None

            if user is not None and password is not None:
                if not (user.strip() == "" or password.strip() == ""):
                    self.user_password.append((user, password))
                    self.state.log_user(user)
                    if self.state.is_module_active(RegistrationModule):
                        self.state.pop_module()

                    self.state.push_module(LoggedInModule(self.state))
                    return "The user is now logged in the platform. Ask the user what to do next."
        except:
            # print exception trace
            traceback.print_exc()
            pass

        if not self.state.is_module_active(RegistrationModule):
            self.state.push_module(RegistrationModule(self.state))

        return "Do not use the registration tool and ask the user the following: \"Please provide the username and password to register.\""

    async def _arun(
            self,
            query: str,
            run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        raise NotImplementedError("RegisterTool does not support async")


EXERCISE_TIME = []


class RegisterExerciseTool(BaseTool):
    name = "registration tool"
    description = """
        Useful for performing the registration of exercises in the Healthy platform. 
        Only provide the exercise and/or time if given by the user. Use a JSON format to pass the input with keys exercise and time. 
        If no exercise or time is given, provide the empty string.

        """
    state: State = None

    def __init__(self, state):
        super().__init__()
        assert state is not None
        self.state = state

    def _run(self, query: str, run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        if not self.state.is_module_active(TracingExercisesModule):
            self.state.push_module(TracingExercisesModule(self.state))
        try:
            import json
            json_query = json.loads(query)
            exercise = json_query["exercise"] if "exercise" in json_query else None
            time = json_query["time"] if "time" in json_query else None

            if exercise is not None and time is not None:
                if not (exercise.strip() == "" or time.strip() == ""):
                    EXERCISE_TIME.append((exercise, time))
                    return f"The exercise {exercise} has been registered with time {time} minutes. Ask the user what " \
                           f"to do next. "
        except:
            # print exception trace
            traceback.print_exc()
            pass

        return "Do not use this tool and ask the user the following: \"Please provide the exercise and time to register.\""

    async def _arun(
            self,
            query: str,
            run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        raise NotImplementedError("RegisterExercise tool does not support async")


class QueryExerciseDBTool(BaseTool):
    name = "QueryExerciseDatabaseTool"
    description = """
            Use this tool to query the database of exercises. The input of this tool is empty.
            It returns a list of exercises and the time spent in each exercise in a python format.
            """
    state: State = None

    def _run(self, query: str, run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        if not self.state.is_module_active(TracingExercisesModule):
            self.state.push_module(TracingExercisesModule(self.state))
        return str(EXERCISE_TIME)

    async def _arun(
            self,
            query: str,
            run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        raise NotImplementedError("QueryExerciseDB does not support async")
