import os

import requests


def invoke(input, model, **kwargs) -> str:
    url = os.environ.get("LLMSERVER_URL")
    if url is None:
        raise Exception("LLMSERVER_URL is not set")

    url = url + "/complete"

    system_messages = [message for message in input if message.type == 'system']
    human_messages = [message for message in input if message.type == 'human']
    assert (len(system_messages) + len(human_messages)) == len(input)

    body = {
        "model": model,
        "system": "\n".join([message.content for message in system_messages]),
        "prompt": "\n".join([message.content for message in human_messages])
    }

    result = requests.post(url, json=body)
    return result.json()['completion']

