from ollama import Client, Options


def invoke_ollama(input_, host, model, stop=[]):
    client = Client(host=get_host(host))
    messages = prepare_messages(input_)
    options = Options(stop=stop)
    response = client.chat(model=model, messages=messages, options=options)
    return response['message']['content']

def get_host(host):
    if "${OLLAMA_HOST}" in host:
        import os
        env_host = os.environ.get("OLLAMA_HOST")
        if env_host is None:
            raise Exception("OLLAMA_HOST environment variable should be set")
        return host.replace("${OLLAMA_HOST}", env_host)
    return host

def prepare_messages(input_messages):
    messages = []
    for message in input_messages:
        if message.type == 'system':
            messages.append({
                'role': 'system',
                'content': message.content,
            })
        else:
            # Probably type == 'human'
            messages.append({
                'role': 'user',
                'content': message.content,
            })
    return messages
