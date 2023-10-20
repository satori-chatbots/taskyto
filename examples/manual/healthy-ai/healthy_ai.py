import os

from langchain.chat_models import ChatOpenAI

import utils
from healthy_workflow import TopLevel, LoggedInModule
from modules import State

utils.check_keys(["SERPAPI_API_KEY", "OPENAI_API_KEY"])

llm = ChatOpenAI(temperature=0., verbose=True)

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
    print("HealthyAI: " + ans)
    # agent_chain.run(input="I want to register to the platform with password 1234")

# print(executor.run(input="I would like to register to the platform", verbose=True))
