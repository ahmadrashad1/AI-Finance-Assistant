"""Drive the PRD success-criterion demo conversations against a running backend.

Prerequisites (see the root README):
  * docker compose up -d ; database migrated and seeded with seed=42
  * backend running: uvicorn app.main:app (port 8000)
  * LLM_API_KEY set in backend/.env (Groq key by default)

Usage:
    .venv/Scripts/python scripts/run_demo.py            # all demos
    .venv/Scripts/python scripts/run_demo.py --demo 2   # one demo (1-based)
    .venv/Scripts/python scripts/run_demo.py --pause 90 # slower pacing

Each turn sends the full planning prompt (~5-9k tokens), so consecutive
turns can exhaust the LLM provider's per-minute token budget. The script
pauses between turns (default 60s) and retries a turn once if the
provider reports it is busy.

Prints a Markdown transcript (message, streamed reply, and the request
trace: plan branch, tools, parameters, duration) for docs/DEMO.md.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid

import httpx

BASE_URL = "http://localhost:8000/api"
BUSY_MARKER = "busy right now"

# Each demo: (title, PRD criterion, conversations); each conversation is a
# list of user turns sharing one conversation_id.
DEMOS: list[tuple[str, str, list[list[str]]]] = [
    (
        "Varied phrasings route to the same tool",
        "Understands natural English",
        [
            ["Show unpaid invoices."],
            ["Which customers haven't paid us?"],
            ["Outstanding invoices?"],
        ],
    ),
    (
        "Multi-turn context retention",
        "Holds multi-turn conversations and remembers context",
        [
            [
                "Show me invoices for Anchor Components",
                "Only the ones above $5,000",
                "What's their total balance?",
            ]
        ],
    ),
    (
        "Tool selection and parameter extraction",
        "Chooses the correct tools and extracts correct parameters",
        [
            ["Show invoices overdue by more than 60 days"],
            ["Generate an aging report"],
            ["Find duplicate invoices"],
            ["What's our cash position?"],
        ],
    ),
    (
        "Honesty under missing data",
        "Accurate data from the simulator; zero hallucinated finance data",
        [
            ["Show me invoice INV-99999"],
            ["Show me unpaid invoices over $10,000,000"],
            ["Show me Anchor's invoices"],
        ],
    ),
    (
        "Clear explanations and scope honesty",
        "Explains results clearly; refuses out-of-scope actions",
        [
            ["Generate an aging report and explain which bucket worries you most"],
            ["Delete all invoices"],
        ],
    ),
]


def run_turn(
    client: httpx.Client, session_id: str, conversation_id: str | None, message: str
) -> tuple[str, str | None, str | None]:
    """POST one chat turn. Returns (reply_text, conversation_id, request_id)."""
    reply_parts: list[str] = []
    new_conversation_id = conversation_id
    request_id: str | None = None
    with client.stream(
        "POST",
        f"{BASE_URL}/chat",
        json={
            "session_id": session_id,
            "message": message,
            "conversation_id": conversation_id,
        },
        timeout=120.0,
    ) as response:
        response.raise_for_status()
        request_id = response.headers.get("x-request-id")
        for line in response.iter_lines():
            if not line.startswith("data: "):
                continue
            event = json.loads(line[len("data: ") :])
            if event["type"] == "token" and event.get("content"):
                reply_parts.append(event["content"])
            elif event["type"] == "done" and event.get("conversation_id"):
                new_conversation_id = event["conversation_id"]
            elif event["type"] == "error":
                reply_parts.append(f"[error event] {event.get('message')}")
    return "".join(reply_parts), new_conversation_id, request_id


def fetch_trace(client: httpx.Client, request_id: str) -> dict[str, object] | None:
    response = client.get(f"{BASE_URL}/trace/{request_id}")
    if response.status_code != 200:
        return None
    payload: dict[str, object] = response.json()
    return payload


def print_trace(trace: dict[str, object] | None) -> None:
    if trace is None:
        print("> trace: unavailable")
        return
    print("> **Trace evidence:**")
    print("> ```json")
    for line in json.dumps(trace, indent=2, default=str).splitlines():
        print(f"> {line}")
    print("> ```")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", type=int, default=None, help="1-based demo number")
    parser.add_argument(
        "--pause", type=int, default=60, help="Seconds to wait between turns (default 60)"
    )
    args = parser.parse_args()

    selected = [DEMOS[args.demo - 1]] if args.demo is not None else DEMOS
    first_turn = True
    with httpx.Client() as client:
        for title, criterion, conversations in selected:
            print(f"\n## Demo: {title}")
            print(f"*PRD criterion: {criterion}*\n")
            for conversation in conversations:
                session_id = f"demo-{uuid.uuid4().hex[:8]}"
                conversation_id: str | None = None
                for message in conversation:
                    if not first_turn:
                        time.sleep(args.pause)
                    first_turn = False
                    print(f"**User:** {message}\n")
                    reply, conversation_id, request_id = run_turn(
                        client, session_id, conversation_id, message
                    )
                    if BUSY_MARKER in reply:
                        # Provider rate limit, not model behavior - wait and retry once.
                        time.sleep(max(args.pause, 90))
                        reply, conversation_id, request_id = run_turn(
                            client, session_id, conversation_id, message
                        )
                    print(f"**Assistant:** {reply}\n")
                    if request_id is not None:
                        print_trace(fetch_trace(client, request_id))
                    print()


if __name__ == "__main__":
    try:
        main()
    except httpx.ConnectError:
        print(
            "Backend not reachable at http://localhost:8000 — start it with "
            "`uvicorn app.main:app` first.",
            file=sys.stderr,
        )
        sys.exit(1)
