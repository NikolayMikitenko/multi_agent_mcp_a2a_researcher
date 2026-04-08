from config import settings, CRITIC_SYSTEM_PROMPT 
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
# from langgraph.checkpoint.memory import MemorySaver
from schemas import CritiqueResult

# memory = MemorySaver()

def build_critic_agent(tools):
    llm = ChatOpenAI(
        model=settings.openai_lm_model,
        temperature=settings.temperature,
        base_url=settings.openai_api_base,
        api_key=settings.openai_api_key.get_secret_value(),
    )
    return create_agent(
        model=llm,
        tools=tools,
        system_prompt=CRITIC_SYSTEM_PROMPT,
        # checkpointer=memory,
        response_format=CritiqueResult,
    )