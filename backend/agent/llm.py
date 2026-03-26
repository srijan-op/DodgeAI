from __future__ import annotations

from typing import Any

from groq import RateLimitError
from langchain_groq import ChatGroq

from ..config import get_settings


def get_chat_llm(*, temperature: float = 0.1) -> Any:
    """
    Groq chat model. With multiple keys (``GROQ_API_KEY`` plus optional comma-separated
    ``GROQ_API_KEYS``), the next key is used when Groq raises ``RateLimitError`` (429 / TPD).
    """
    s = get_settings()
    keys = s.groq_api_key_list
    if not keys:
        raise RuntimeError("Set GROQ_API_KEY and/or GROQ_API_KEYS")

    def _client(api_key: str) -> ChatGroq:
        return ChatGroq(
            model=s.groq_model,
            groq_api_key=api_key,
            temperature=temperature,
        )

    primary = _client(keys[0])
    if len(keys) == 1:
        return primary

    return primary.with_fallbacks(
        [_client(k) for k in keys[1:]],
        exceptions_to_handle=(RateLimitError,),
    )
