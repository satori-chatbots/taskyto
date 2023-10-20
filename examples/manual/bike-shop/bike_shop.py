from langchain.chat_models import ChatOpenAI

import utils
from bike_modules import TopLevel
from modules import State

utils.check_keys(["OPENAI_API_KEY"])

llm = ChatOpenAI(temperature=0., model_name="gpt-3.5-turbo-0301")
# gpt-3.5-turbo-0613
# https://github.com/hwchase17/langchain/issues/6418

state = State(llm=llm)
state.push_module(TopLevel(state=state))
while True:
    agent_chain = state.get_chain()

    module_name = type(state.current_module()).__name__
    user_prompt = "You [" + module_name + "]: "

    # read from stdin
    inp = input(user_prompt)
    # run the agent
    ans = agent_chain.run(input=inp)
    print("BikeShop: " + ans)
