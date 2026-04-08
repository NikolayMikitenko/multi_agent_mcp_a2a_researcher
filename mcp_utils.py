from typing import Optional
from pydantic import Field, create_model
from langchain_core.tools import StructuredTool

def filter_tools(lc_tools, allowed_names: set[str]):
    return [tool for tool in lc_tools if tool.name in allowed_names]

# def extract_mcp_result(tool_result) -> str:
#     """Normalize FastMCP call_tool result into a clean string for LLM tools."""
#     structured = getattr(tool_result, "structured_content", None)
#     if structured:
#         payload = structured.get("result", structured)
#         if isinstance(payload, str):
#             return payload
#         return json.dumps(payload, ensure_ascii=False)

#     content = getattr(tool_result, "content", None)
#     if content:
#         texts = []
#         for item in content:
#             text = getattr(item, "text", None)
#             if text:
#                 texts.append(text)
#         if texts:
#             return "\n".join(texts)

#     return str(tool_result)

def mcp_tools_to_langchain(mcp_tools, mcp_client):
    """Convert MCP tool definitions to LangChain StructuredTool objects."""
    lc_tools = []
    for tool in mcp_tools:
        schema = tool.inputSchema or {"type": "object", "properties": {}}
        props = schema.get("properties", {})
        required = set(schema.get("required", []))

        # Build pydantic model from JSON Schema
        type_map = {"string": str, "integer": int, "number": float, "boolean": bool}
        fields = {}
        for name, prop in props.items():
            py_type = type_map.get(prop.get("type"), str)
            default = ... if name in required else prop.get("default")
            fields[name] = (
                py_type if name in required else Optional[py_type],
                Field(default=default, description=prop.get("description", "")),
            )

        args_model = create_model(f"{tool.name}_args", **fields) if fields else None

        # Closure: each tool calls MCP server
        _name, _client = tool.name, mcp_client

        async def _invoke(_name=_name, _client=_client, **kwargs):
            return str(await _client.call_tool(_name, kwargs))
            # result = await _client.call_tool(_name, kwargs)
            # return extract_mcp_result(result)

        lc_tools.append(
            StructuredTool.from_function(
                coroutine=_invoke, 
                name=tool.name,
                description=tool.description or tool.name, 
                args_schema=args_model,
            )
        )

    return lc_tools