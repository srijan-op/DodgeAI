"""LangGraph wiring + streaming entrypoint for /api/chat."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, AsyncIterator, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from ..chat_memory import format_history_for_llm
from .llm import get_chat_llm
from .models import GraphQueryResult, RouterPlan
from .presenter import present_graph_answer, present_graph_answer_stream
from .tools_run import run_analyze_flow, run_graph_query

logger = logging.getLogger(__name__)

ROUTER_SYSTEM = """You are the router for **Dodge AI**: SAP Order-to-Cash (O2C), the project's Neo4j graph
(Customers, SalesOrders, Deliveries, Invoices, Payments, Products, etc.), and **business analytics on that data**.

## Scope guard (evaluate before tools)

1) **off_topic** — Not about O2C, this database, or analytics on these entities.
   Examples: restaurants/food, weather, jokes, unrelated coding, personal advice.
   Set scope `off_topic`, both run flags **false**, prompts null. Set `direct_reply`: briefly decline, state your scope, invite an on-topic question.
   Never invent unrelated facts (e.g. where to get pizza).

2) **needs_clarification** — The user cannot be answered faithfully without more detail:
   - Deictic/context phrases when **no prior conversation** exists, or prior turns do not define the referent: "that list", "the first order in that list", "those customers", "same as before", "it", "they".
   - Vague terms that block a correct query: unknown ids, "the problem account", "biggest seller" without definition.
   Set scope `needs_clarification`, both run flags **false**. Set `direct_reply` to a short message that **asks specific clarifying questions**.

3) **in_scope** — O2C concepts and/or data questions. Set scope `in_scope`, then choose tools.

## Tools (only when scope is `in_scope`)

**analyze_flow** — O2C / SAP process and graph concepts (no invented row-level DB facts).

**graph_query** — Live Neo4j: counts, lists, filters, aggregates.

Both may be true; split into analyze_flow_prompt and graph_query_prompt (null when that branch is off).
If one intent covers the message, one prompt gets the full text and the other flag is false.

When scope is not `in_scope`, leave both prompts null and both run flags false.
"""


_DEFAULT_OFF_TOPIC_REPLY = (
    "I'm here to help with SAP Order-to-Cash,"
    "(customers, orders, deliveries, billing, payments), and related business analytics. "
    "I can't help with that."
    "what would you like to know about your O2C data or process?"
)

_DEFAULT_CLARIFICATION_REPLY = (
    "I don't have enough context to that question yet. Which list, document, customer or order id, "
    "or filter do you mean? You can also ask a fresh question such as "
    "\"list the 10 most recent sales orders\" so I can answer from the database."
)


def _router_human_content(user_message: str, history: list[dict]) -> str:
    block = format_history_for_llm(history)
    if not history:
        session_note = (
            "**Session:** There is **no prior conversation**. Any reference to "
            "\"that list\", \"the first order\", \"those items\", \"same customer\", "
            "\"as before\", etc. is **undefined** — use scope `needs_clarification` and ask what they mean.\n\n"
        )
    else:
        session_note = (
            "**Session:** Prior messages exist; you may use them to resolve follow-ups.\n\n"
        )
    if not block.strip():
        return f"{session_note}--- Current message ---\n{user_message}"
    return (
        f"{session_note}"
        "Route and split the **current** message; use prior turns only to interpret references.\n\n"
        f"--- Prior conversation ---\n{block}\n\n--- Current message ---\n{user_message}"
    )


def _conversation_context(history: list[dict]) -> str | None:
    s = format_history_for_llm(history)
    return s if s.strip() else None


class ChatState(TypedDict, total=False):
    user_message: str
    conversation_history: list[dict]
    plan: RouterPlan | None
    analyze_text: str
    graph_text: str
    graph_highlights: list[str]
    final_answer: str


@dataclass
class TurnResult:
    analyze_text: str
    graph_text: str
    highlights: list[str]
    final_answer: str


def _normalize_plan(user_message: str, plan: RouterPlan) -> RouterPlan:
    if plan.scope in ("off_topic", "needs_clarification"):
        reply = (plan.direct_reply or "").strip()
        if not reply:
            reply = (
                _DEFAULT_OFF_TOPIC_REPLY
                if plan.scope == "off_topic"
                else _DEFAULT_CLARIFICATION_REPLY
            )
        return plan.model_copy(
            update={
                "run_analyze_flow": False,
                "run_graph_query": False,
                "direct_reply": reply,
            }
        )

    if not plan.run_analyze_flow and not plan.run_graph_query:
        return RouterPlan(
            scope="in_scope",
            direct_reply=None,
            run_analyze_flow=True,
            run_graph_query=True,
            analyze_flow_prompt=user_message,
            graph_query_prompt=user_message,
        )
    return plan.model_copy(update={"scope": "in_scope", "direct_reply": None})


def _graph_debug(gr: GraphQueryResult) -> str:
    """Non-user-facing trace for logs / secondary storage."""
    return (
        f"refined_question: {gr.refined_question}\n"
        f"cypher_executed: {gr.cypher_executed}\n"
        f"row_count: {gr.row_count}\n"
        f"success: {gr.success}\n"
        f"error_message: {gr.error_message}\n"
    )


async def _synthesize(user_message: str, conceptual: str, data_natural_language: str) -> str:
    llm = get_chat_llm(temperature=0.2)
    resp = await llm.ainvoke(
        [
            SystemMessage(
                content=(
                    "You merge two assistant outputs into one clear reply. "
                    "The 'Data answer' is already written for a business user from the database — "
                    "integrate it with the conceptual part; do not replace it with raw JSON or Cypher."
                )
            ),
            HumanMessage(
                content=(
                    f"User question:\n{user_message}\n\n"
                    f"Conceptual explanation:\n{conceptual}\n\n"
                    f"Data answer (from graph query):\n{data_natural_language}"
                )
            ),
        ]
    )
    return (resp.content or "").strip()


async def execute_turn(
    user_message: str,
    plan: RouterPlan,
    *,
    history: list[dict] | None = None,
) -> TurnResult:
    plan = _normalize_plan(user_message, plan)
    u = user_message
    if plan.scope != "in_scope":
        dr = (plan.direct_reply or "").strip()
        return TurnResult(
            analyze_text="",
            graph_text="",
            highlights=[],
            final_answer=dr,
        )

    ap = (plan.analyze_flow_prompt or "").strip() or u
    gp = (plan.graph_query_prompt or "").strip() or u
    hist = history or []
    ctx = _conversation_context(hist)

    if plan.run_analyze_flow and plan.run_graph_query:
        analyze_text, graph_res = await asyncio.gather(
            run_analyze_flow(ap, conversation_context=ctx),
            run_graph_query(gp, conversation_context=ctx),
        )
        data_nl = await present_graph_answer(u, graph_res, conversation_context=ctx)
        highlights = list(graph_res.highlights)
        final = await _synthesize(u, analyze_text, data_nl)
        return TurnResult(
            analyze_text=analyze_text,
            graph_text=_graph_debug(graph_res),
            highlights=highlights,
            final_answer=final,
        )

    if plan.run_analyze_flow:
        at = await run_analyze_flow(ap, conversation_context=ctx)
        return TurnResult(analyze_text=at, graph_text="", highlights=[], final_answer=at)

    if plan.run_graph_query:
        graph_res = await run_graph_query(gp, conversation_context=ctx)
        data_nl = await present_graph_answer(u, graph_res, conversation_context=ctx)
        return TurnResult(
            analyze_text="",
            graph_text=_graph_debug(graph_res),
            highlights=list(graph_res.highlights),
            final_answer=data_nl,
        )

    return TurnResult(analyze_text="", graph_text="", highlights=[], final_answer="")


async def router_node(state: ChatState) -> dict[str, Any]:
    llm = get_chat_llm(temperature=0.0).with_structured_output(RouterPlan)
    hist = list(state.get("conversation_history") or [])
    router_human = _router_human_content(state["user_message"], hist)
    plan: RouterPlan = await llm.ainvoke(
        [SystemMessage(content=ROUTER_SYSTEM), HumanMessage(content=router_human)]
    )
    return {"plan": plan}


async def execute_node(state: ChatState) -> dict[str, Any]:
    plan = state.get("plan")
    if plan is None:
        raise RuntimeError("Missing plan")
    hist = list(state.get("conversation_history") or [])
    tr = await execute_turn(state["user_message"], plan, history=hist)
    return {
        "analyze_text": tr.analyze_text,
        "graph_text": tr.graph_text,
        "graph_highlights": tr.highlights,
        "final_answer": tr.final_answer,
    }


def build_chat_graph():
    """Compiled LangGraph for tests and non-streaming invoke."""
    g = StateGraph(ChatState)
    g.add_node("router", router_node)
    g.add_node("execute", execute_node)
    g.set_entry_point("router")
    g.add_edge("router", "execute")
    g.add_edge("execute", END)
    return g.compile()


def _chunk_text(text: str, size: int = 160) -> list[str]:
    if not text:
        return []
    return [text[i : i + size] for i in range(0, len(text), size)]


async def stream_chat_turn(
    user_message: str,
    *,
    session_id: str = "",
    history: list[dict] | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """
    SSE-friendly event stream: meta, plan, graph_highlight, token deltas, done.
    Graph answers are streamed from the presenter LLM (natural language).
    """
    yield {"type": "meta", "session_id": session_id}

    hist = history or []
    ctx = _conversation_context(hist)
    router_human = _router_human_content(user_message, hist)

    llm = get_chat_llm(temperature=0.0)
    router = llm.with_structured_output(RouterPlan)
    plan = await router.ainvoke(
        [SystemMessage(content=ROUTER_SYSTEM), HumanMessage(content=router_human)]
    )
    plan = _normalize_plan(user_message, plan)
    yield {"type": "plan", "plan": plan.model_dump()}

    u = user_message
    if plan.scope != "in_scope":
        for part in _chunk_text((plan.direct_reply or "").strip()):
            yield {"type": "token", "delta": part}
        yield {"type": "done"}
        return

    ap = (plan.analyze_flow_prompt or "").strip() or u
    gp = (plan.graph_query_prompt or "").strip() or u

    if plan.run_analyze_flow and plan.run_graph_query:
        analyze_text, graph_res = await asyncio.gather(
            run_analyze_flow(ap, conversation_context=ctx),
            run_graph_query(gp, conversation_context=ctx),
        )
        yield {"type": "graph_highlight", "node_ids": list(graph_res.highlights)}
        data_nl = await present_graph_answer(u, graph_res, conversation_context=ctx)

        syn_llm = get_chat_llm(temperature=0.2)
        syn_msgs = [
            SystemMessage(
                content=(
                    "You merge two assistant outputs into one clear, **concise** reply for a business user. "
                    "Integrate conceptual and data parts; do not dump JSON/Cypher. "
                    "If the question is about process gaps or broken flows (not money), **omit** redundant amounts "
                    "or currency detail unless the user asked for financial figures."
                )
            ),
            HumanMessage(
                content=(
                    f"User question:\n{u}\n\n"
                    f"Conceptual explanation:\n{analyze_text}\n\n"
                    f"Data answer (from graph query):\n{data_nl}"
                )
            ),
        ]
        async for chunk in syn_llm.astream(syn_msgs):
            c = getattr(chunk, "content", None) or ""
            if c:
                yield {"type": "token", "delta": c}
        yield {"type": "done"}
        return

    if plan.run_analyze_flow:
        text = await run_analyze_flow(ap, conversation_context=ctx)
        for part in _chunk_text(text):
            yield {"type": "token", "delta": part}
        yield {"type": "done"}
        return

    if plan.run_graph_query:
        graph_res = await run_graph_query(gp, conversation_context=ctx)
        yield {"type": "graph_highlight", "node_ids": list(graph_res.highlights)}
        async for delta in present_graph_answer_stream(
            u, graph_res, conversation_context=ctx
        ):
            yield {"type": "token", "delta": delta}
        yield {"type": "done"}
        return

    yield {"type": "done"}
