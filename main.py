from __future__ import annotations

import asyncio
import json
from typing import Any

from langgraph.types import Command

from config import settings
from supervisor import supervisor


STAGE_LABELS = {
    "delegate_to_planner": "Planner",
    "delegate_to_researcher": "Researcher",
    "delegate_to_critic": "Critic",
    "save_report": "save_report",
}


class ConsoleState:
    def __init__(self) -> None:
        self.current_stage: str | None = None
        self.research_round = 0

    def reset(self) -> None:
        self.current_stage = None
        self.research_round = 0

    def stage_header(self, stage: str) -> str:
        if stage == "Researcher":
            self.research_round += 1
            return f"[Supervisor → ACP → {stage}]  (round {self.research_round})"
        if stage == "save_report":
            return "[Supervisor → MCP → save_report]"
        return f"[Supervisor → ACP → {stage}]"


STATE = ConsoleState()


def short_args(args: dict[str, Any]) -> str:
    if "request" in args:
        return repr(args["request"])
    if "plan" in args:
        return repr(args["plan"])
    if "findings" in args:
        return repr(args["findings"])
    if "filename" in args and "content" in args:
        preview = args["content"][:80].replace("\n", " ")
        if len(args["content"]) > 80:
            preview += "..."
        return f"filename={args['filename']!r}, content={preview!r}"
    return json.dumps(args, ensure_ascii=False)


def show_interrupt(interrupt_value: dict) -> dict:
    requests = interrupt_value.get("action_requests", [])

    print("\n" + "=" * 60)
    print("⏸️  ACTION REQUIRES APPROVAL")
    print("=" * 60)

    first_request = {}
    for request in requests:
        first_request = request
        action_name = request.get("action") or request.get("name") or "N/A"
        args = request.get("args") or request.get("arguments") or {}
        print(f"  Tool:  {action_name}")
        print(f"  Args:  {json.dumps(args, indent=2, ensure_ascii=False)}")

        if action_name == "save_report":
            content = args.get("content", "")
            preview = content[:1000]
            if len(content) > 1000:
                preview += "\n...[truncated preview]..."
            print("\n  Preview:")
            print(preview)

    print()
    return first_request


def build_resume_command(decision_type: str, interrupt_request: dict) -> Command:
    if decision_type == "approve":
        return Command(resume={"decisions": [{"type": "approve"}]})

    if decision_type == "edit":
        original_name = interrupt_request.get("action") or interrupt_request.get("name")
        original_args = (interrupt_request.get("args") or interrupt_request.get("arguments") or {}).copy()

        print("Leave fields empty to keep original values.")
        new_filename = input("📝 New filename (optional): ").strip()
        if new_filename:
            original_args["filename"] = new_filename

        print("📝 Paste replacement report content. Finish with a single line: :::end")
        lines = []
        while True:
            line = input()
            if line.strip() == ":::end":
                break
            lines.append(line)

        edited_content = "\n".join(lines).strip()
        if edited_content:
            original_args["content"] = edited_content

        return Command(
            resume={
                "decisions": [
                    {
                        "type": "edit",
                        "edited_action": {
                            "name": original_name,
                            "args": original_args,
                        },
                    }
                ]
            }
        )

    return Command(
        resume={
            "decisions": [
                {
                    "type": "reject",
                    "message": "User rejected this action.",
                }
            ]
        }
    )


def format_structured_payload(stage: str, text: str) -> str | None:
    try:
        data = json.loads(text)
    except Exception:
        return None

    if stage == "Planner":
        return (
            "ResearchPlan(\n"
            f"  goal={data.get('goal')!r},\n"
            f"  search_queries={data.get('search_queries', [])!r},\n"
            f"  sources_to_check={data.get('sources_to_check', [])!r},\n"
            f"  output_format={data.get('output_format')!r}\n"
            ")"
        )

    if stage == "Critic":
        return (
            "CritiqueResult(\n"
            f"  verdict={data.get('verdict')!r},\n"
            f"  is_fresh={data.get('is_fresh')!r},\n"
            f"  is_complete={data.get('is_complete')!r},\n"
            f"  is_well_structured={data.get('is_well_structured')!r},\n"
            f"  strengths={data.get('strengths', [])!r},\n"
            f"  gaps={data.get('gaps', [])!r},\n"
            f"  revision_requests={data.get('revision_requests', [])!r}\n"
            ")"
        )

    return None


async def handle_update_chunk(chunk: dict[str, Any], config: dict) -> bool:
    data = chunk["data"]

    if "__interrupt__" in data:
        interrupt = data["__interrupt__"][0]
        interrupt_value = getattr(interrupt, "value", interrupt)
        request = show_interrupt(interrupt_value)

        decision = input("👉 approve / edit / reject: ").strip().lower()
        if decision == "approve":
            print("\n✅ Approved! Resuming...\n")
        elif decision == "edit":
            print("\n✏️  Editing tool call...\n")
        else:
            print("\n❌ Rejected.\n")

        cmd = build_resume_command(
            decision if decision in {"approve", "edit"} else "reject",
            request,
        )
        await stream_graph(cmd, config)
        return True

    for step_name, update in data.items():
        if not isinstance(update, dict):
            continue

        messages = update.get("messages", [])
        if not messages:
            continue

        last = messages[-1]
        tool_calls = getattr(last, "tool_calls", None)

        if tool_calls:
            for call in tool_calls:
                name = call["name"]
                stage = STAGE_LABELS.get(name)
                if stage:
                    STATE.current_stage = stage
                    print("\n" + STATE.stage_header(stage))
                else:
                    print("\n[Supervisor]")
                print(f"🔧 {name}({short_args(call['args'])})")
            continue

        content = getattr(last, "content", None)
        if not content:
            continue

        text = content if isinstance(content, str) else str(content)
        text = text.strip()
        if not text:
            continue

        stage = STATE.current_stage or "Supervisor"
        structured = format_structured_payload(stage, text)
        if structured:
            print("  📎 " + structured.replace("\n", "\n  "))
        else:
            summary = text.splitlines()[0]
            if len(summary) > 220:
                summary = summary[:220] + "..."
            print(f"  📎 {summary}")

    return False


async def stream_graph(payload, config: dict) -> None:
    async for chunk in supervisor.astream(
        payload,
        config=config,
        stream_mode="updates",
        version="v2",
    ):
        if chunk["type"] != "updates":
            continue

        should_stop = await handle_update_chunk(chunk, config)
        if should_stop:
            return


async def amain():
    print("Homework 9: MCP + ACP Multi-Agent Research System (type 'exit' to quit)")
    config = {"configurable": {"thread_id": settings.thread_id}}

    while True:
        query = input("\nYou: ").strip()
        if query.lower() in {"exit", "quit"}:
            break
        if not query:
            continue

        STATE.reset()
        await stream_graph(
            {"messages": [{"role": "user", "content": query}]},
            config,
        )
        print()


def main():
    asyncio.run(amain())


if __name__ == "__main__":
    main()