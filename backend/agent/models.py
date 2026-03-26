from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RouterPlan(BaseModel):
    """First LLM call: decide which branches run and split sub-questions."""

    scope: Literal["in_scope", "off_topic", "needs_clarification"] = Field(
        default="in_scope",
        description=(
            "in_scope: SAP O2C, this Neo4j dataset, or business analytics on orders/customers/billing/delivery/payment. "
            "off_topic: general knowledge, personal life, unrelated products, coding homework, etc. "
            "needs_clarification: question depends on unstated list/entity/ID, ambiguous terms, or prior context that is missing."
        ),
    )
    direct_reply: str | None = Field(
        default=None,
        description=(
            "When scope is off_topic or needs_clarification: the full reply to show the user (polite, concise). "
            "Ask specific clarifying questions when scope is needs_clarification. Must be null when scope is in_scope."
        ),
    )
    run_analyze_flow: bool = Field(description="True if user wants O2C/process explanation or general concepts.")
    run_graph_query: bool = Field(description="True if user needs data from the graph (counts, lists, filters).")
    analyze_flow_prompt: str | None = Field(
        default=None,
        description="Sub-question for conceptual answer; null if not running analyze_flow.",
    )
    graph_query_prompt: str | None = Field(
        default=None,
        description="Sub-question for Neo4j; null if not running graph_query.",
    )


class GraphAgentAnswer(BaseModel):
    """First step of graph_query: refine intent for Cypher generation."""

    refined_question: str = Field(description="Short, precise question for the Cypher generator.")


class GraphQueryResult(BaseModel):
    """Structured output from graph_query (Neo4j execution) for the answer presenter."""

    success: bool = Field(description="True if Cypher ran without guard/Neo4j failure.")
    refined_question: str = ""
    cypher_executed: str | None = None
    row_count: int = 0
    result_rows_json: str = Field(
        default="",
        description="Truncated JSON text of rows for the presenter (not shown raw to end users).",
    )
    highlights: list[str] = Field(default_factory=list)
    error_message: str | None = None
