from __future__ import annotations

from fastmcp import FastMCP
from pathlib import Path
from config import settings
import json
import asyncio

report_mcp = FastMCP(name="Report")

@report_mcp.tool
def save_report(filename: str, content: str) -> str:
    """Save the final Markdown report to the output directory and return the absolute path."""
    try:
        safe_name = Path(filename).name
        if not safe_name.endswith(".md"):
            safe_name += ".md"

        if isinstance(content, list):
            text_parts = []
            for block in content:
                if isinstance(block, dict) and "text" in block:
                    text_parts.append(block["text"])
                else:
                    text_parts.append(str(block))
            content = "\n".join(text_parts)

        output_path = Path(settings.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        output_path = output_path / safe_name
        output_path.write_text(content, encoding="utf-8")
        return str(output_path.resolve())
    except Exception as e:
        return f"save_report failed for file '{filename}' in folder '{settings.output_dir}': {e}"
    
@report_mcp.resource("resource://output-dir")
def output_dir_resource() -> str:
    """Output directory path and saved reports list."""
    output_dir = Path(settings.output_dir)

    if not output_dir.exists():
        return json.dumps(
            {
                "path": str(output_dir.resolve()),
                "reports": [],
                "status": "output directory does not exist",
            },
            ensure_ascii=False,
        )

    reports = sorted(p.name for p in output_dir.glob("*.md"))
    return json.dumps(
        {
            "path": str(output_dir.resolve()),
            "reports": reports,
            "status": "ok",
        },
        ensure_ascii=False,
    )

async def amain():
    await report_mcp.run_async(
        transport="streamable-http",
        host=settings.mcp_host,
        port=settings.report_mcp_port,
    )

if __name__ == "__main__":
    asyncio.run(amain())