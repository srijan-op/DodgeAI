"""Tool implementations: analyze_flow (LLM + schema), graph_query (2 LLM + Neo4j)."""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from neo4j.exceptions import Neo4jError
from neo4j.graph import Node

from ..config import get_settings
from ..cypher_guard import CypherGuardError, extract_cypher_block, validate_read_only_cypher
from ..neo4j_db import run_read_query
from ..prompts import (
    format_cypher_user_message,
    format_graph_refine_user_message,
    load_cypher_generator_prompt,
)
from ..schema_provider import build_schema_prompt_block, get_live_schema_snapshot
from ..serializers import collect_highlight_node_ids, serialize_node
from .llm import get_chat_llm
from .models import GraphAgentAnswer, GraphQueryResult

logger = logging.getLogger(__name__)

MAX_RESULT_CHARS = 12_000


def _truncate(s: str, limit: int = MAX_RESULT_CHARS) -> str:
    if len(s) <= limit:
        return s
    return s[: limit - 40] + "\n... [truncated] ...\n"


def _rows_to_text(rows: list[dict[str, Any]]) -> str:
    """JSON-serialize query results for the presenter."""
    serializable: list[dict[str, Any]] = []
    for row in rows:
        out_row: dict[str, Any] = {}
        for k, v in row.items():
            if isinstance(v, Node):
                out_row[k] = serialize_node(v)
            else:
                out_row[k] = str(v)[:500]
        serializable.append(out_row)
    return _truncate(json.dumps(serializable, indent=2, default=str))


def _cypher_system_message(max_lim: int) -> str:
    doc = load_cypher_generator_prompt()
    live = get_live_schema_snapshot()
    return (
        "You write read-only Neo4j Cypher for Neo4j 5. "
        "Use only MATCH / OPTIONAL MATCH / WITH / WHERE / RETURN / ORDER BY / UNWIND as needed. "
        f"Every query MUST end with RETURN and MUST include LIMIT between 1 and {max_lim}.\n"
        "When listing or showing specific entities (customers, orders, lines, invoices, products, paths), "
        "RETURN those as node/path variables in addition to any scalars — see GRAPH HIGHLIGHT CONTRACT in the pack below.\n"
        "Output ONLY a single fenced ```cypher``` block, no other prose.\n\n"
        f"{doc}\n\n### Live database snapshot (labels / rel types)\n{live}"
    )


async def run_analyze_flow(
    user_prompt: str, *, conversation_context: str | None = None
) -> str:
    """Single LLM call: O2C / process explanation grounded in canonical schema text."""
    llm = get_chat_llm(temperature=0.3)
    schema = build_schema_prompt_block()
    human = user_prompt.strip()
    if conversation_context and conversation_context.strip():
        human = (
            "**Prior conversation (for follow-ups):**\n"
            f"{conversation_context.strip()}\n\n"
            f"**Current request:**\n{human}"
        )
    messages = [
        SystemMessage(
            content=(
                "You are an expert on SAP Order-to-Cash (O2C) and the graph model below. "
                "Answer clearly in plain language. Use bullet points when helpful. "
                "Do not invent database facts (counts, specific document numbers); "
                "for those, say the user should ask the data assistant. "
                "If the question is unrelated to O2C, SAP, or this graph model, reply in one or two sentences that you only cover those topics and ask for an on-topic question.\n\n"
                f"{schema}"
            )
        ),
        HumanMessage(content=human),
    ]
    resp = await llm.ainvoke(messages)
    return (resp.content or "").strip()


async def run_graph_query(
    user_question: str,
    *,
    conversation_context: str | None = None,
    max_retries: int = 2,
) -> GraphQueryResult:
    """
    Two LLM calls: (1) refine question, (2) Cypher generator using resources/prompts/o2c_cypher_prompt.md.
    Returns structured result for the answer presenter.
    """
    settings = get_settings()
    max_lim = settings.cypher_max_limit
    llm = get_chat_llm(temperature=0.0)
    agent_llm = llm.with_structured_output(GraphAgentAnswer)

    agent_msg = [
        SystemMessage(
            content=(
                "You are an expert SAP Order-to-Cash analyst. "
                "You prepare a single refined question for a Neo4j Cypher generator. "
                "The graph has Customer, SalesOrder, SalesOrderItem, Delivery, Invoice, InvoiceItem, "
                "JournalEntry, Payment, Product, and related nodes."
            )
        ),
        HumanMessage(
            content=format_graph_refine_user_message(
                user_question, conversation_context=conversation_context
            )
        ),
    ]
    agent_out: GraphAgentAnswer = await agent_llm.ainvoke(agent_msg)
    refined = agent_out.refined_question.strip()

    cypher_sys = _cypher_system_message(max_lim)

    last_err: str | None = None
    cypher_text = ""
    for attempt in range(max_retries + 1):
        cypher_human = format_cypher_user_message(refined, last_err)
        resp = await llm.ainvoke(
            [SystemMessage(content=cypher_sys), HumanMessage(content=cypher_human)]
        )
        raw = (resp.content or "").strip()
        cypher_text = extract_cypher_block(raw)
        try:
            safe = validate_read_only_cypher(cypher_text, max_limit=max_lim)
        except CypherGuardError as e:
            last_err = str(e)
            logger.info("cypher_guard_reject attempt=%s err=%s", attempt, last_err)
            if attempt >= max_retries:
                return GraphQueryResult(
                    success=False,
                    refined_question=refined,
                    cypher_executed=cypher_text or None,
                    row_count=0,
                    result_rows_json="[]",
                    highlights=[],
                    error_message=last_err,
                )
            continue

        try:
            rows = run_read_query(safe, {})
        except Neo4jError as e:
            last_err = str(e)
            logger.info("neo4j_error attempt=%s err=%s", attempt, last_err)
            if attempt >= max_retries:
                return GraphQueryResult(
                    success=False,
                    refined_question=refined,
                    cypher_executed=safe,
                    row_count=0,
                    result_rows_json="[]",
                    highlights=[],
                    error_message=last_err,
                )
            continue

        summary = _rows_to_text(rows) if rows else "[]"
        highlights = collect_highlight_node_ids(rows)
        return GraphQueryResult(
            success=True,
            refined_question=refined,
            cypher_executed=safe,
            row_count=len(rows),
            result_rows_json=summary,
            highlights=highlights,
            error_message=None,
        )

    return GraphQueryResult(
        success=False,
        refined_question=refined,
        cypher_executed=cypher_text or None,
        row_count=0,
        result_rows_json="[]",
        highlights=[],
        error_message=last_err or "unknown",
    )
