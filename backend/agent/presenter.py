"""Turn GraphQueryResult into natural-language chat answers."""

from __future__ import annotations

import json
from typing import AsyncIterator

from langchain_core.messages import HumanMessage, SystemMessage

from ..prompts import format_presenter_user_message, load_presenter_system_prompt
from .llm import get_chat_llm
from .models import GraphQueryResult


def _payload_for_llm(result: GraphQueryResult) -> str:
    d = result.model_dump()
    # Keep payload bounded; result_rows_json already truncated in tools_run
    return json.dumps(d, indent=2, default=str)


async def present_graph_answer(
    user_question: str,
    result: GraphQueryResult,
    *,
    conversation_context: str | None = None,
) -> str:
    llm = get_chat_llm(temperature=0.25)
    system = load_presenter_system_prompt()
    human = format_presenter_user_message(
        user_question,
        _payload_for_llm(result),
        conversation_context=conversation_context,
    )
    resp = await llm.ainvoke(
        [SystemMessage(content=system), HumanMessage(content=human)]
    )
    return (resp.content or "").strip()


async def present_graph_answer_stream(
    user_question: str,
    result: GraphQueryResult,
    *,
    conversation_context: str | None = None,
) -> AsyncIterator[str]:
    llm = get_chat_llm(temperature=0.25)
    system = load_presenter_system_prompt()
    human = format_presenter_user_message(
        user_question,
        _payload_for_llm(result),
        conversation_context=conversation_context,
    )
    async for chunk in llm.astream(
        [SystemMessage(content=system), HumanMessage(content=human)]
    ):
        c = getattr(chunk, "content", None) or ""
        if c:
            yield c
