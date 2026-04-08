from langchain_openai import ChatOpenAI
from config import settings, SUPERVISOR_SYSTEM_PROMPT

from langchain.tools import tool
from acp_sdk.client import Client as ACPClient
from acp_sdk.models import Message, MessagePart
from fastmcp import Client

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langgraph.checkpoint.memory import InMemorySaver

llm = ChatOpenAI(
        model=settings.openai_lm_model,
        temperature=settings.temperature,
        base_url=settings.openai_api_base,
        api_key=settings.openai_api_key.get_secret_value(),
    )

async def run_acp_agent(agent_name: str, text: str) -> str:
    async with ACPClient(base_url=settings.acp_base_url, headers={"Content-Type": "application/json"}) as client:
        run = await client.run_sync(
            agent=agent_name,
            input=[Message(role="user", parts=[MessagePart(content=text)])],
        )
        # output = run.output[-1].parts[0].content
        # return {"research": output}

        if not getattr(run, "output", None):
            return f"ACP agent '{agent_name}' returned no output."

        output_message = run.output[-1]
        if not output_message.parts:
            return f"ACP agent '{agent_name}' returned an empty message."
        return output_message.parts[0].content or ""

@tool
async def delegate_to_planner(request: str) -> str:
    """Delegate planning to the Planner ACP agent."""
    return await run_acp_agent("planner", request)

@tool
async def delegate_to_researcher(plan: str) -> str:
    """Delegate research to the Researcher ACP agent."""  
    return await run_acp_agent("researcher", plan)

@tool
async def delegate_to_critic(findings: str) -> str:
    """Delegate critique to the Critic ACP agent."""
    return await run_acp_agent("critic", findings)

@tool
async def save_report(filename: str, content: str) -> str:
    """Save report through ReportMCP to the output directory and return the absolute path."""
    async with Client(settings.report_mcp_url) as client:
        return await client.call_tool("save_report", {"filename":filename, "content":content})
        # result = await client.call_tool(
        #     "save_report",
        #     {"filename": filename, "content": content},
        # )
        # return extract_mcp_result(result)

supervisor = create_agent(
    model=llm,
    tools=[delegate_to_planner, delegate_to_researcher, delegate_to_critic, save_report],
    system_prompt=SUPERVISOR_SYSTEM_PROMPT,
    middleware=[
        HumanInTheLoopMiddleware(
            interrupt_on={"save_report": True}
        )
    ],
    checkpointer=InMemorySaver(),
)