# ruff: noqa: E501
"""
O2C agent prompts: user-turn string templates and markdown-backed system prompts.

User messages use the format_* helpers below. Long system instructions are extracted
from ``resources/prompts/o2c_cypher_prompt.md`` (sections between ``<<<...>>>`` markers).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

# --- Graph question refinement (human / user turn, structured output) ---

GRAPH_REFINE_USER_PROMPT_TEMPLATE = """Prepare a precise question for the Cypher generator.

{conversation_section}**User request:**
{user_question}

**Your task:**
1. Rewrite the request as one clear English question the database can answer.
2. Preserve document numbers, customer ids, and filters exactly as given.
3. If the user refers to prior results (e.g. "those orders", "same customer"), fold that into the refined question using the conversation context.

**IMPORTANT:** The next step only sees your refined question — do not omit constraints."""


def format_graph_refine_user_message(
    user_question: str, *, conversation_context: str | None = None
) -> str:
    section = ""
    if conversation_context and conversation_context.strip():
        section = (
            "**Conversation context (resolve references like 'those customers', 'the first one'):**\n"
            f"{conversation_context.strip()}\n\n"
        )
    return GRAPH_REFINE_USER_PROMPT_TEMPLATE.format(
        conversation_section=section,
        user_question=user_question.strip(),
    )


# --- Cypher generation (human / user turn) ---

CYPHER_USER_PROMPT_TEMPLATE = """Generate read-only Neo4j Cypher that answers the refined question below.

**Refined question:**
{refined_question}

{previous_error_section}

Follow the system instructions and **CRITICAL TECHNICAL CONTRACT** exactly (including **GRAPH HIGHLIGHT CONTRACT**: include `Node` or `Path` columns when returning entity rows).

**IMPORTANT:** Your reply must contain only a single ```cypher fenced block with the query — no other text."""


def format_cypher_user_message(refined_question: str, previous_error: str | None) -> str:
    if previous_error:
        prev = f"**Previous error (fix the query):**\n{previous_error}\n"
    else:
        prev = ""
    return CYPHER_USER_PROMPT_TEMPLATE.format(
        refined_question=refined_question.strip(),
        previous_error_section=prev,
    )


# --- Answer presenter (human / user turn) ---

PRESENTER_USER_PROMPT_TEMPLATE = """Compose the chat reply for a business user.

{conversation_section}**User question:**
{user_question}

**Structured query result (JSON):**
{payload_json}

**Your task:**
1. Answer the user question in natural, professional language — **be concise**: prefer a short opening plus bullets or a compact list when many rows exist; avoid filler.
2. Use only facts supported by the structured result.
3. **Relevance:** Mention amounts, currencies, or other financial fields **only** when the question asks for money/totals/pricing. For process/integrity questions (broken flows, missing deliveries, gaps), prioritize **document numbers, statuses, counts, and what is missing** — not illustrative net amounts.
4. Do not dump raw JSON or Cypher in the reply unless the user asked for technical detail.

**IMPORTANT:** Return only the conversational answer text — no markdown headings unless they improve readability inside the message or explicitly requested."""


def format_presenter_user_message(
    user_question: str,
    payload_json: str,
    *,
    conversation_context: str | None = None,
) -> str:
    section = ""
    if conversation_context and conversation_context.strip():
        section = (
            "**Recent conversation (resolve pronouns / follow-ups):**\n"
            f"{conversation_context.strip()}\n\n"
        )
    return PRESENTER_USER_PROMPT_TEMPLATE.format(
        conversation_section=section,
        user_question=user_question.strip(),
        payload_json=payload_json.strip(),
    )


# --- Markdown prompt pack (``resources/prompts/o2c_cypher_prompt.md``) ---

_BACKEND_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _BACKEND_DIR.parent
_PROMPT_FILE = _PROJECT_ROOT / "resources" / "prompts" / "o2c_cypher_prompt.md"

_BEGIN_CYPHER = "<<<BEGIN_CYPHER_GENERATOR>>>"
_END_CYPHER = "<<<END_CYPHER_GENERATOR>>>"
_BEGIN_PRESENTER = "<<<BEGIN_ANSWER_PRESENTER>>>"
_END_PRESENTER = "<<<END_ANSWER_PRESENTER>>>"


def _extract(text: str, start: str, end: str) -> str:
    try:
        i = text.index(start) + len(start)
        j = text.index(end, i)
        return text[i:j].strip()
    except ValueError as e:
        raise ValueError(f"Prompt markers missing in {_PROMPT_FILE}: {e}") from e


@lru_cache
def _file_text() -> str:
    if not _PROMPT_FILE.is_file():
        raise FileNotFoundError(f"Missing prompt file: {_PROMPT_FILE}")
    return _PROMPT_FILE.read_text(encoding="utf-8")


@lru_cache
def load_cypher_generator_prompt() -> str:
    """Schema + example Cyphers for the Cypher-writing LLM."""
    return _extract(_file_text(), _BEGIN_CYPHER, _END_CYPHER)


@lru_cache
def load_presenter_system_prompt() -> str:
    """Instructions for turning structured GraphQueryResult into user-facing prose."""
    return _extract(_file_text(), _BEGIN_PRESENTER, _END_PRESENTER)


def clear_prompt_cache() -> None:
    """For tests or hot-reload in dev."""
    _file_text.cache_clear()
    load_cypher_generator_prompt.cache_clear()
    load_presenter_system_prompt.cache_clear()
