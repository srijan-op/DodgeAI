#!/usr/bin/env python3
"""
Exercise analyze_flow and graph_query (Groq + Neo4j) without starting FastAPI.

Run from the DodgeAI project root:

    python scripts/test_chat_agent_tools.py
    python scripts/test_chat_agent_tools.py --mode graph
    python scripts/test_chat_agent_tools.py --mode analyze
    python scripts/test_chat_agent_tools.py --mode combined

Requires .env: GROQ_API_KEY, NEO4J_* (for graph mode).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Project root = parent of scripts/
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _banner(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


async def _test_analyze_flow(prompt: str) -> None:
    from backend.agent.tools_run import run_analyze_flow

    _banner("analyze_flow")
    print("Prompt:", prompt, "\n")
    text = await run_analyze_flow(prompt)
    print(text)


async def _test_graph_query(prompt: str, *, with_presenter: bool = True) -> None:
    from backend.agent.presenter import present_graph_answer
    from backend.agent.tools_run import run_graph_query

    _banner("graph_query (2 LLM steps + Neo4j → GraphQueryResult)")
    print("Prompt:", prompt, "\n")
    gr = await run_graph_query(prompt)
    print(gr.model_dump_json(indent=2))
    if with_presenter:
        _banner("presenter (natural language)")
        nl = await present_graph_answer(prompt, gr)
        print(nl)


async def _test_combined() -> None:
    from backend.agent.models import RouterPlan
    from backend.agent.pipeline import execute_turn

    _banner("combined (parallel analyze_flow + graph_query, then synthesis)")
    user = (
        "In one answer: briefly explain how a sales order relates to billing in this model, "
        "and tell me how many Customer nodes exist in the database."
    )
    plan = RouterPlan(
        run_analyze_flow=True,
        run_graph_query=True,
        analyze_flow_prompt=(
            "Briefly explain how SalesOrder / Invoice / InvoiceItem relate in the O2C graph "
            "(no specific document numbers)."
        ),
        graph_query_prompt="How many Customer nodes are in the graph?",
    )
    print("User message (synthetic full ask):\n", user, "\n")
    print("Using explicit RouterPlan (both branches).\n")
    result = await execute_turn(user, plan)
    print("--- highlights ---")
    print(result.highlights)
    print()
    print("--- final_answer ---")
    print(result.final_answer)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Test chat agent tools (Groq + Neo4j).")
    parser.add_argument(
        "--mode",
        choices=("all", "graph", "analyze", "combined"),
        default="all",
        help="Which tests to run (default: all).",
    )
    args = parser.parse_args()

    from backend.config import get_settings

    s = get_settings()
    if not s.groq_api_key:
        print("ERROR: GROQ_API_KEY is not set in .env / environment.", file=sys.stderr)
        sys.exit(1)

    if args.mode in ("all", "analyze"):
        await _test_analyze_flow(
            "What is the high-level order-to-cash flow in this graph model, "
            "from customer order to payment?"
        )

    if args.mode in ("all", "graph"):
        if not s.neo4j_password:
            print("SKIP graph_query: NEO4J_PASSWORD not set.", file=sys.stderr)
        else:
            await _test_graph_query("How many Customer nodes are in the graph?")
            await _test_graph_query(
                "Return up to 3 SalesOrder nodes with their salesOrder id and totalNetAmount."
            )
            # RETURN must include actual :Customer nodes (not only scalars) for highlights.
            await _test_graph_query(
                "Return up to 3 Customer nodes from the graph as full node objects "
                "(e.g. RETURN c LIMIT 3) so they can be highlighted in the UI."
            )
            await _test_graph_query(
                "Which products have the highest billing volume based on invoice line amounts?",
                with_presenter=True,
            )

    if args.mode == "combined":
        if not s.neo4j_password:
            print("ERROR: combined mode needs Neo4j (NEO4J_PASSWORD).", file=sys.stderr)
            sys.exit(1)
        await _test_combined()


if __name__ == "__main__":
    asyncio.run(main())
