# pending 
SUCCESS, ERROR = 1, 0
from icecream import ic
import openai
from openai import OpenAI


def api_key_check(request_data: dict):
    """
    Checks if the provided OpenAI API key has access to the 'gpt-4o-mini' model.
    """
    api_key = request_data.get('api_key')
    is_valid = False

    if not api_key:
        return {"is_valid": False}

    try:
        client = OpenAI(api_key=api_key)
        # Listing the available models for the API key is an efficient way
        # to check permissions without running a completion task.
        models = client.models.list()
        for model in models.data:
            if model.id == 'gpt-4o-mini':
                is_valid = True
                break
    except openai.AuthenticationError:
        # The API key is invalid or has been revoked.
        ic("AuthenticationError: The API key is invalid.")
        is_valid = False
    except Exception as e:
        # Catch other possible exceptions (e.g. network issues).
        ic(f"Ocurrió un error inesperado al verificar la API key: {e}")
        is_valid = False
    
    return {
        "is_valid": is_valid
    }

