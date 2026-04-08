from fastmcp import FastMCP
from ddgs import DDGS
from config import settings
import trafilatura
from retriever import HybridRetriever
import asyncio
from pathlib import Path
import json
from datetime import datetime, timezone

from trafilatura.settings import use_config

traf_config = use_config("trafilatura_settings.cfg")

search_mcp = FastMCP(name="Search")

# resource://knowledge-base-stats — кількість документів, дата останнього оновлення

@search_mcp.resource("resource://knowledge-base-stats")
def knowledge_base_stats() -> str:
    """Knowledge base metadata: number of documents and last update time."""
    try:
        chunks_path = Path(settings.qdrant_path) / settings.chunk_file_name
        if not chunks_path.exists():
            return json.dumps(
                {
                    "documents": 0,
                    "chunks": 0,
                    "last_updated": None,
                    "status": "index not found",
                }
            )

        chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
        sources = set()
        for item in chunks:
            source_id = item.get("source_id")
            if source_id is not None:
                sources.add(str(source_id))

        last_updated = datetime.fromtimestamp(
            chunks_path.stat().st_mtime, tz=timezone.utc
        ).isoformat()

        return json.dumps(
            {
                "documents": len(sources),
                "chunks": len(chunks),
                "last_updated": last_updated,
            }
        )
    except Exception as e:
        return json.dumps({"error": str(e)})

def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n\n[truncated to {limit} characters]"

@search_mcp.tool
def web_search(query: str) -> list[dict]:
    """Search in the web and return compact results with title, url, and snippet.
    
    Args:
        query: Search query (e.g. 'authentication API' or 'frontend performance')
    """
    try:
        results = list(DDGS(timeout=5).text(query, max_results=settings.max_search_results) or [])

        if not results:
            return [{"title": "Absent search results", "url": "", "snippet": f"No results found for query: {query}"}]
        
        normalized: list[dict[str, str]] = []
        for item in results:
            normalized.append(
                {
                    "title": str(item.get("title", "")).strip(),
                    "url": str(item.get("href", "")).strip(),
                    "snippet": str(item.get("body", "")).strip(),
                }
            )
        # print(f"Founed {len(normalized)} web sites")
        if not normalized:
            return [{"title": "No results", "url": "", "snippet": f"No results found for query: {query}"}]
        return normalized
    except Exception as e:
        return [
            {
                "title": "Search error",
                "url": "",
                "snippet": f"web_search error: failed for query '{query}': {e}", 
            }
        ]

@search_mcp.tool
def read_url(url: str) -> str:
    """Fetch a URL and extract the page content. Returns a compact, truncated text payload or a readable error.
    
    Args:
        url: URI of webpage for read and extract content
    """
    try:
        downloaded = trafilatura.fetch_url(url, config=traf_config)
        if not downloaded:
            return f"read_url error: Could not download URL: {url}"
        
        extracted = trafilatura.extract(downloaded)
        if not extracted:
            return f"read_url error: Could not extract meaningful text from URL: {url}"
        
        return _truncate(extracted, settings.max_url_content_length)
    except Exception as e:
        return f"read_url error: Failed read '{url}': {e}"

@search_mcp.tool
def knowledge_search(query: str) -> str:
    """Search the local knowledge base."""
    try:
        retriever = HybridRetriever()
        results = retriever.search(query)

        if not results:
            return "No relevant documents found in the local knowledge base."
        
        # print(retriever.info_output(results))

        return retriever.format_output(results)

    except Exception as e:
        return f"knowledge_search error: Local knowledge_search error: {e}"

async def amain():
    await search_mcp.run_async(
        transport="streamable-http",
        host=settings.mcp_host,
        port=settings.search_mcp_port,
    )

if __name__ == "__main__":
    asyncio.run(amain())