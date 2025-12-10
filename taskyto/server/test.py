import os

def main() -> None:
    pass

    chatbots = os.listdir("/home/ubuntu/chatbot-llm/chatbots")

    print(f"chatbots -> {chatbots}")

def main2():
    pass

    cmd = "/.venv/bin/python /home/ubuntu/chatbot-llm/taskyto/serve.py --chatbot /home/ubuntu/chatbot-llm/chatbots/beta-bot/ --port 5001"

    os.system(cmd)

def main3():
    pass

    cmd = "echo $OPENAI_API_KEY"

    os.system(cmd)

if __name__ == "__main__":
    main()
    # main2()
    # main3()