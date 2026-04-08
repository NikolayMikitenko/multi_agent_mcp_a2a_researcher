# multi_agent_mcp_a2a_researcher
# Multi-Agent MCP / ACP Researcher

Autonomous **protocol-based multi-agent LLM-powered research system**

This project using **distributed protocol-based system**:

- **MCP servers** for tools and resources
- **ACP server** for remote sub-agents
- **Local Supervisor** for orchestration and Human-in-the-Loop approval

The system combines:

- **Supervisor orchestration**
- **Planner / Researcher / Critic** sub-agents
- **local RAG pipeline**
- **web research**
- **Markdown report generation**
- **approval before saving reports**

---

## Demo

![Research Agent Demo 1](demo1.png)

![Research Agent Demo 2](demo2.png)

![Research Agent Demo 3](demo3.png)

---

# Architecture

```text
User (REPL)
  │
  ▼
Local Supervisor Agent
  │
  ├── delegate_to_planner(...)     → ACP Server → Planner Agent
  ├── delegate_to_researcher(...)  → ACP Server → Researcher Agent
  ├── delegate_to_critic(...)      → ACP Server → Critic Agent
  │
  └── save_report(...)             → ReportMCP Server
```

Protocol layer:

```text
SearchMCP   → web_search / read_url / knowledge_search / knowledge-base-stats resource
ReportMCP   → save_report / output-dir resource
ACP Server  → planner / researcher / critic
Supervisor  → local orchestrator with HITL
```

---

# Installation

This project uses **uv** and dependencies defined in `pyproject.toml`.

### 1. Install dependencies

```bash
uv sync
```

---

# Environment Variables

Create a `.env` file in the project root.

Example:

```env
OPENAI_API_KEY=sk-***
OPENAI_API_BASE=https://***.com/api/v1
OPENAI_LM_MODEL=gpt-5-mini

AZURE_API_KEY=***
AZURE_EMBED_ENDPOINT=https://***.services.ai.azure.com/openai/v1/
AZURE_EMBED_MODEL=embed-v-4-0
AZURE_RERANK_ENDPOINT=https://***.services.ai.azure.com/providers/cohere/
AZURE_RERANK_MODEL=cohere-rerank-v4.0-pro
```

### Variables

| Name | Description | Example |
|------|-------------|---------|
| `OPENAI_API_KEY` | API key for chat model access | `sk-***` |
| `OPENAI_API_BASE` | Base URL for OpenAI-compatible chat API | `https://***.com/api/v1` |
| `OPENAI_LM_MODEL` | Chat model used by agents | `gpt-5-mini` |
| `AZURE_API_KEY` | API key for embeddings and rerank endpoints | `***` |
| `AZURE_EMBED_ENDPOINT` | Azure endpoint for embeddings | `https://***.services.ai.azure.com/openai/v1/` |
| `AZURE_EMBED_MODEL` | Embedding model | `embed-v-4-0` |
| `AZURE_RERANK_ENDPOINT` | Azure rerank endpoint | `https://***.services.ai.azure.com/providers/cohere/` |
| `AZURE_RERANK_MODEL` | Reranker model | `cohere-rerank-v4.0-pro` |

---

# Prepare Local Knowledge Base

Before running the system, ingest local documents:

```bash
uv run python ingest.py
```

This command:
- loads documents from `data/`
- creates chunks
- generates embeddings
- stores the index in Qdrant local storage
- prepares chunk metadata for retrieval

---

# Run Order

Start the services in this order.

## 1. SearchMCP

```bash
uv run python -m mcp_servers.search_mcp
```

## 2. ReportMCP

```bash
uv run python -m mcp_servers.report_mcp
```

## 3. ACP Server

```bash
uv run python acp_server.py
```

## 4. Local Supervisor / REPL

```bash
uv run python main.py
```

---

# Multi-agent workflow

1. The **Supervisor** receives the user request in the local REPL
2. The Supervisor delegates planning to the **Planner ACP agent**
3. The **Planner** returns a structured `ResearchPlan`
4. The Supervisor delegates execution to the **Researcher ACP agent**
5. The **Researcher** uses MCP tools to gather evidence from:
   - the web
   - local knowledge base
6. The Supervisor delegates evaluation to the **Critic ACP agent**
7. The **Critic** returns a structured `CritiqueResult`
8. If needed, the Supervisor launches one additional research revision round
9. The Supervisor prepares the final Markdown report
10. Before writing the file, **Human-in-the-Loop approval** is required
11. After approval, the report is saved through **ReportMCP**

---

# Main Features

- **Protocol-based multi-agent system**
- **2 MCP servers**
- **1 ACP server**
- **local Supervisor agent**
- **structured planner output**
- **structured critic output**
- **iterative research loop**
- **Human-in-the-Loop approval before save_report**
- **local RAG knowledge base**
- **web + local search**
- **Markdown report generation**
- **async streaming console interface**

---

# Components

## 1. SearchMCP
Search server that exposes research-related tools and resources.

### Tools
- `web_search(query)`
- `read_url(url)`
- `knowledge_search(query)`

### Resources
- `resource://knowledge-base-stats`

This server is responsible for:
- internet search
- page reading
- access to the local knowledge base
- read-only metadata about the local index

---

## 2. ReportMCP
Server responsible for saving generated reports.

### Tools
- `save_report(filename, content)`

### Resources
- `resource://output-dir`

This server is responsible for:
- persisting Markdown reports
- exposing metadata about the output directory and saved reports

---

## 3. ACP Server
Remote agent server exposing three specialized agents:

- `planner`
- `researcher`
- `critic`

The ACP server:
- builds the role-specific agents
- injects the appropriate MCP tools
- handles remote execution of planning, research, and critique

---

## 4. Local Supervisor
The local Supervisor coordinates the whole process.

Responsibilities:
- receives the user request
- calls ACP agents in the correct order
- interprets critique results
- controls revision loops
- prepares the final report
- asks for HITL approval before saving

---

# RAG Layer

This project reuses the local RAG system from previous homeworks.

## Ingestion pipeline (`ingest.py`)
The ingestion pipeline:
- loads local documents from `data/`
- extracts text
- splits documents into chunks
- generates embeddings
- stores vectors in Qdrant
- saves chunk metadata for retrieval

## Retrieval pipeline (`retriever.py`)
The retriever supports:
- **semantic vector search**
- **BM25 lexical search**
- **hybrid retrieval**
- **reranking**

This allows the Researcher and Critic to use:
- **external web sources**
- **local knowledge base sources**

---

# Example Session

```text
Homework 9: MCP + ACP Multi-Agent Research System (type 'exit' to quit)

You: full lenght of mazda cx-5 in centimeters

[Supervisor → ACP → Planner]
🔧 delegate_to_planner('Find the overall length of the Mazda CX-5 in centimeters. If length varies by model year or trim, identify the most recent model year available and report the standard overall length(s) in centimeters, noting any variants (e.g., different wheelbase or market versions). Keep the response concise and include sources to be used in research.')
  📎 ResearchPlan(
    goal='Determine the overall exterior length of the Mazda CX-5 in centimeters. If length differs by model year or trim, identify the most recent model year available and report the standard overall length(s) in cm, noting any variants (e.g., different wheelbase or market versions). Provide concise answer with sources.',
    search_queries=['Mazda CX-5 2024 (or most recent) specifications overall length site:mazdausa.com OR site:mazda.com', "Mazda CX-5 dimensions length wheelbase by model year site:wikipedia.org (or 'Mazda CX-5 dimensions' + 'length' + 'wheelbase' for market/variant differences)"],
    sources_to_check=['web'],
    output_format='Concise bullet (or 1–2 short paragraphs) stating: 1) Most recent model year found and its standard overall length in centimeters (with conversion if source gives inches), 2) Any variants/market versions and their lengths (with brief note e.g., different wheelbase), and 3) 2–3 source links to be cited (manufacturer spec page and a secondary reference such as Wikipedia or an automotive reviewer).'
  )

[Supervisor → ACP → Researcher]  (round 1)
🔧 delegate_to_researcher('Use official Mazda specification pages and reputable automotive sources (Wikipedia, car review sites) to find the overall length of the most recent Mazda CX-5 model. Convert lengths to centimeters if needed. Gather sources and note any variants (e.g., longer-wheelbase Chinese market CX-5 variant if present). Provide concise findings and source links.')
  📎 Answer

[Supervisor → ACP → Critic]
🔧 delegate_to_critic('Most recent Mazda CX-5 overall length is reported as 4,575 mm (180.1 in) which is 457.5 cm. Sources: Mazda USA owner manual/spec pages, Mazda regional spec pages, Wikipedia, Automobile-Catalog, dealer pages. Note: No evidence of a long-wheelbase variant; wheelbase commonly reported as 2,700 mm. Mentioned limitations: manufacturer pages may change; micro-differences possible due to trim or market-specific bumper items; can verify region-specific PDFs or dealer VIN data if needed.')
  📎 CritiqueResult(
    verdict='REVISE',
    is_fresh=False,
    is_complete=False,
    is_well_structured=True,
    strengths=['Findings are consistent across many independent sources (dealers, catalogues, regional Mazda pages) that list the CX-5 length as 4,575 mm and wheelbase as 2,700 mm for the current/outgoing generation (2022–2025).', 'The research notes sensible caveats about manufacturer page changes and small market/trim differences, which is appropriate and useful.', 'The summary is concise and clearly states the main numeric claims and supporting source types.'],
    gaps=['The summary does not acknowledge that Mazda has publicly announced a new third-generation CX-5 (model year 2026) with larger dimensions (reported ~4,690 mm length and a longer wheelbase), which materially affects a statement framed as "most recent."', 'No direct links to the official Mazda USA specification or owner manual PDF pages were included to prove the claim for the U.S. market specifically (only regional/dealer references were cited in the verification).', 'The phrase "most recent" is ambiguous: it\'s unclear whether it refers to the most recent production model available for sale (through 2025) or the newly announced 2026 generation.'],
    revision_requests=['Clarify what you mean by "most recent" — do you mean the current generation in production/sale (2022–2025) or the newly announced 2026 generation?', 'If you intend to claim the current/incoming production model (through 2025) is 4,575 mm, explicitly state the model years covered (e.g., "2022–2025 CX-5: 4,575 mm, wheelbase 2,700 mm") to avoid confusion with the 2026 update.', 'Update the research to mention the 2026 CX-5 announcement and its reported dimensions (approximately 4,690 mm length and ~2,815 mm wheelbase) and cite reputable press releases or major automotive outlets reporting those figures.', 'Add direct links to official Mazda spec/owner-manual pages for the relevant markets (Mazda USA, Mazda Europe, Mazda Japan or regional official brochures) that show the 4,575 mm and 2,700 mm figures, or state if an official PDF could not be found.', 'If you need to make a definitive statement for a particular market/trim, verify micro-differences using region-specific PDF brochures or dealer/VIN data and cite those sources accordingly.']
  )

[Supervisor → ACP → Researcher]  (round 2)
🔧 delegate_to_researcher('Find and cite direct official specification or owner manual pages (PDF or web) from Mazda USA and at least one regional Mazda site that list Mazda CX-5 overall length = 4,575 mm (457.5 cm) and wheelbase = 2,700 mm for the current generation (model years 2022–2025). Also search reputable automotive press (e.g., Automotive News, Car and Driver, Motor1, Autocar, Top Gear) and Mazda press releases for announcements of a new 2026 Mazda CX-5 generation with reported dimensions (~4,690 mm length and ~2,815 mm wheelbase). If exact official 2026 spec is not available, cite major outlets reporting the announced/rumored dimensions and note status. Include links to all sources. Keep findings concise and clearly label model-year groups (2022–2025 vs 2026 announcement).')
  📎 Answer

[Supervisor → ACP → Critic]
🔧 delegate_to_critic('Added clarification: 2022–2025 CX-5 length = 4,575 mm (457.5 cm), wheelbase = 2,700 mm (270.0 cm), with direct links to Mazda owner manuals and regional PDF specs. Also reported the 2026 all-new CX-5 announcement with larger dimensions ~4,690 mm (469.0 cm) and wheelbase ~2,815 mm (281.5 cm); cited Mazda press release and regional spec PDFs plus Car and Driver/MotorTrend coverage. Noted limitations about availability of mm values on Mazda USA pages and reliance on regional/spec PDF for 2026 mm figures.')
  📎 CritiqueResult(
    verdict='APPROVE',
    is_fresh=True,
    is_complete=True,
    is_well_structured=True,
    strengths=['Findings use recent, authoritative sources for the 2026 change (Mazda press release / newsroom plus coverage from Car and Driver and MotorTrend).', 'Numeric conversions and the reported delta (4.5 in ≈ 115 mm) are correct and consistently applied to produce ~4690 mm length and ~2815 mm wheelbase.', 'The report clearly distinguishes model-year ranges (2022–2025 vs. 2026) and calls out the source types (owner manuals, regional spec PDFs, press release, automotive press).', 'It explicitly notes a real limitation: Mazda USA pages present inches rather than mm, so regional PDFs were used for mm values — this transparency about source limitations is appropriate.'],
    gaps=['Some of the cited manufacturer PDF files and regional spec PDFs could not be fetched by verification tools during review (read failures), so direct file-level verification wasn’t possible here — the underlying claims are still supported by the Mazda newsroom release and reputable automotive press.', 'The research references owner manuals and regional PDFs but would be easier to verify if it included the exact URLs (or screenshots) for each manual/spec PDF used.'],
    revision_requests=[]
  )

[Supervisor → MCP → save_report]
🔧 save_report(filename='mazda_cx5_length_report.md', content='# Mazda CX-5 Overall Length — Model-Year Clarification  ## Executive Summary The...')

============================================================
⏸️  ACTION REQUIRES APPROVAL
============================================================
  Tool:  save_report
  Args:  {
  "filename": "mazda_cx5_length_report.md",
  "content": "# Mazda CX-5 Overall Length — Model-Year Clarification\n\n## Executive Summary\nThe Mazda CX-5 overall exterior length differs between the current generation (model years 2022–2025) and the all‑new 2026 generation. Key lengths:\n\n- 2022–2025 Mazda CX-5: 4,575 mm (457.5 cm)\n- 2026 Mazda CX-5 (all‑new generation): 4,690 mm (469.0 cm) — reported by Mazda press materials and major automotive outlets\n\nThese figures were confirmed from Mazda owner manuals/spec PDFs and Mazda press releases, plus independent automotive press coverage.\n\n## Key Findings\n- Official Mazda owner manuals and regional specification PDFs list the current (2022–2025) CX‑5 overall length as 4,575 mm (457.5 cm) with a wheelbase of 2,700 mm (270.0 cm).\n- Mazda’s announcement and product/spec PDFs for the all‑new 2026 CX‑5 report an increased overall length of 4,690 mm (469.0 cm) and a wheelbase of approximately 2,815 mm (281.5 cm). Major outlets (Car and Driver, MotorTrend, etc.) corroborate these numbers in their coverage.\n- No widely available long‑wheelbase market variant of the CX‑5 (beyond the standard and 2026 larger model) was found in Mazda’s global lineup.\n\n## Analysis / Notes\n- \"Most recent\" can mean either the most recent production model available (2022–2025 CX‑5) or the newly announced 2026 generation. This report provides both to avoid ambiguity.\n- The change from 4,575 mm to 4,690 mm between generations represents an increase of 115 mm (11.5 cm).\n- Manufacturer regional spec PDFs (Europe/UK) are the clearest sources for metric (mm) figures; the Mazda USA site and press pages often present dimensions in inches, and owner manuals list both units in many cases.\n\n## Sources\n- Mazda USA — CX-5 owner’s manual / vehicle specification (examples listing 4,575 mm for 2022–2025):\n  - https://www.mazdausa.com/static/manuals/2025/cx-5/contents/10050100.html\n  - https://www.mazdausa.com/static/manuals/2023/cx-5/contents/10020104.html\n- Mazda UK / EU — CX-5 technical/spec PDFs (show 4,575 mm for older generation and 4,690 mm for 2026 launch PDFs):\n  - 2022 CX-5 spec PDF: https://media-assets.mazda.eu/raw/upload//mazdauk/contentassets/59f47a618d1d45f48d950987160eb455/mazda-cx-5-price-and-spec-guide-aug-2022.pdf\n  - 2026 ALL‑NEW CX‑5 PS/spec guide: https://media-assets.mazda.eu/raw/upload//mazdauk/globalassets/pdfs/mazda-cx-5-ps-guide-april26-.pdf\n- Mazda Newsroom — US press release announcing 2026 CX‑5 pricing and packaging (confirmation of new model):\n  - https://news.mazdausa.com/2026-01-13-Mazda-Announces-Pricing-and-Packaging-for-All-New-2026-Mazda-CX-5\n- Automotive press coverage confirming 2026 dimensions:\n  - Car and Driver — comparative reporting: https://www.caranddriver.com/news/a65338197/2026-mazda-cx-5-2025-mazda-cx-5-specs-compared/\n  - MotorTrend — 2026 CX‑5 first‑drive/coverage: https://www.motortrend.com/reviews/first-drive-2026-mazda-cx-5\n\n## Limitations\n- Some regional PDFs or manual pages may be moved or updated by Mazda; a few PDF links may require retries if temporarily inaccessible. Where Mazda USA lists inches, I used regional Mazda PDFs and press/spec guides for metric (mm) values.\n\n---\nPrepared by the Supervisor agent.\n"
}

  Preview:
# Mazda CX-5 Overall Length — Model-Year Clarification

## Executive Summary
The Mazda CX-5 overall exterior length differs between the current generation (model years 2022–2025) and the all‑new 2026 generation. Key lengths:

- 2022–2025 Mazda CX-5: 4,575 mm (457.5 cm)
- 2026 Mazda CX-5 (all‑new generation): 4,690 mm (469.0 cm) — reported by Mazda press materials and major automotive outlets

These figures were confirmed from Mazda owner manuals/spec PDFs and Mazda press releases, plus independent automotive press coverage.

## Key Findings
- Official Mazda owner manuals and regional specification PDFs list the current (2022–2025) CX‑5 overall length as 4,575 mm (457.5 cm) with a wheelbase of 2,700 mm (270.0 cm).
- Mazda’s announcement and product/spec PDFs for the all‑new 2026 CX‑5 report an increased overall length of 4,690 mm (469.0 cm) and a wheelbase of approximately 2,815 mm (281.5 cm). Major outlets (Car and Driver, MotorTrend, etc.) corroborate these numbers in their coverage.

...[truncated preview]...

👉 approve / edit / reject: approve

✅ Approved! Resuming...


[Supervisor → MCP → save_report]
🔧 save_report(filename='mazda_cx5_length_report.md', content="# Mazda CX-5 Exterior Length Report  ## Executive Summary The Mazda CX-5's overa...")
  📎 CallToolResult(content=[TextContent(type='text', text='/Users/user/FUIB/projects/multi_agent_mcp_a2a_researcher/output/mazda_cx5_length_report.md', annotations=None, meta=None)], structured_content={'result': '/Users/use...
  📎 Here’s the concise answer you requested.


You: exit
```

---

# Human-in-the-Loop Flow

When the Supervisor is ready to save a report, the system pauses and asks for approval.

Available actions:

- `approve` — save the report as-is
- `edit` — modify the report before saving
- `reject` — cancel the save operation

Example:

```text
============================================================
⏸️  ACTION REQUIRES APPROVAL
============================================================
  Tool:  save_report
  Args:  {
    "filename": "rag_report.md",
    "content": "# RAG Report..."
  }

👉 approve / edit / reject:
```

---

 Project Structure

```text
multi_agent_mcp_a2a_researcher/
│
├── agents/
│   ├── __init__.py
│   ├── planner.py
│   ├── research.py
│   └── critic.py
│
├── mcp_servers/
│   ├── search_mcp.py
│   └── report_mcp.py
│
├── data/
├── output/
│
├── acp_server.py
├── config.py
├── ingest.py
├── main.py
├── mcp_utils.py
├── retriever.py
├── trafilatura_settings.cfg
├── schemas.py
├── supervisor.py
│
├── pyproject.toml
├── uv.lock
├── README.md
└── .env
```

---

# Technologies

- Python
- LangChain
- LangGraph
- FastMCP
- ACP SDK
- OpenAI-compatible chat API
- Azure-compatible embeddings API
- Cohere reranking
- Qdrant
- DuckDuckGo Search (`ddgs`)
- Trafilatura
- PyPDF
- Pydantic / Pydantic Settings
- uv

---

# Notes

- `save_report` is executed through **ReportMCP**, but approval remains controlled by the **local Supervisor**
- the ACP agents do not directly own tool implementations — tools are provided through MCP
- `SearchMCP` and `ReportMCP` are independent services
- `Planner` and `Critic` use structured outputs through Pydantic schemas
- `Researcher` returns free-form evidence-based findings

---

# Author

**ai_and_ml_guru**

---

# Usage Restrictions

Use, redistribution, or modification of this software **without explicit permission from the author is forbidden**.