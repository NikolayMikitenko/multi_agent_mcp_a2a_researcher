from acp_sdk.server import Server
from fastmcp import Client
from mcp_utils import mcp_tools_to_langchain, filter_tools

from acp_sdk.models import Message, MessagePart
from agents.planner import build_planner_agent
from agents.research import build_research_agent
from agents.critic import build_critic_agent

from config import settings

acp_server = Server()

# async def get_mcp_tools(url):
#     async with Client(url) as mcp_client:
#         # Convert MCP tools to LangChain format
#         mcp_tools = await mcp_client.list_tools()
#         lc_tools = mcp_tools_to_langchain(mcp_tools, mcp_client)
#         return lc_tools

@acp_server.agent(
    name="planner",
    description="Creates a structured research plan using SearchMCP tools if needed."
)
async def planner_handler(input: list[Message]) -> Message:
    user_text = input[-1].parts[0].content
    async with Client(settings.search_mcp_url) as mcp_client:
        # Convert MCP tools to LangChain format
        mcp_tools = await mcp_client.list_tools()
        planner_tools = mcp_tools_to_langchain(mcp_tools, mcp_client)

        # planner_tools = await get_mcp_tools(settings.search_mcp_url)
        planner_tools = filter_tools(planner_tools, {"web_search", "knowledge_search"})
        planner_agent = build_planner_agent(planner_tools)
        result = await planner_agent.ainvoke({"messages": [("user", user_text)]})
        plan_result = result["structured_response"]
        return Message(
            role="agent", 
            parts=[MessagePart(content=plan_result.model_dump_json(indent=2, ensure_ascii=False))],
        )

@acp_server.agent(
    name="researcher",
    description="Executes the plan using SearchMCP tools and returns findings.",
)
async def research_handler(input: list[Message]) -> Message:
    user_text = input[-1].parts[0].content
    async with Client(settings.search_mcp_url) as mcp_client:
        # Convert MCP tools to LangChain format
        mcp_tools = await mcp_client.list_tools()
        research_tools = mcp_tools_to_langchain(mcp_tools, mcp_client)

        # research_tools = await get_mcp_tools(settings.search_mcp_url)
        research_tools = filter_tools(research_tools, {"web_search", "read_url", "knowledge_search"})
        research_agent = build_research_agent(research_tools)
        result = await research_agent.ainvoke({"messages": [("user", user_text)]})

        return Message(
            role="agent", 
            parts=[MessagePart(content=result["messages"][-1].content)],
        )

@acp_server.agent(
    name="critic",
    description="Verifies findings and returns a structured critique.",
)
async def critic_handler(input: list[Message]) -> Message:
    user_text = input[-1].parts[0].content
    async with Client(settings.search_mcp_url) as mcp_client:
        # Convert MCP tools to LangChain format
        mcp_tools = await mcp_client.list_tools()
        critic_tools = mcp_tools_to_langchain(mcp_tools, mcp_client)

        # critic_tools = await get_mcp_tools(settings.search_mcp_url)
        critic_tools = filter_tools(critic_tools, {"web_search", "read_url", "knowledge_search"})
        critic_agent = build_critic_agent(critic_tools)
        result = await critic_agent.ainvoke({"messages": [("user", user_text)]})
        critic_result = result["structured_response"]
        return Message(
            role="agent", 
            parts=[MessagePart(content=critic_result.model_dump_json(indent=2, ensure_ascii=False))],
        )

if __name__ == "__main__":
    acp_server.run(host=settings.acp_host, port=settings.acp_port)