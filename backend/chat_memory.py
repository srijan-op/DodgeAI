"""Session-scoped chat history: role, content, optional timestamp; last N turns."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from typing import Any

from .config import get_settings

_KEY_PREFIX = "dodgeai:chat:v1:"

_mem_lock = threading.Lock()
_mem_store: dict[str, list[dict[str, Any]]] = {}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _max_message_count() -> int:
    t = get_settings().chat_history_max_turns
    return max(2, t * 2)


def _redis_client():
    url = (get_settings().redis_url or "").strip()
    if not url:
        return None
    try:
        import redis  # type: ignore[import-untyped]
    except ImportError:
        return None
    return redis.Redis.from_url(url, decode_responses=True)


def format_history_for_llm(
    messages: list[dict[str, Any]],
    *,
    max_turns: int | None = None,
    max_chars_per_message: int = 2000,
) -> str:
    """Flatten stored messages into a single block for prompts (bounded size)."""
    if not messages:
        return ""
    settings = get_settings()
    turns = max_turns if max_turns is not None else settings.chat_history_max_turns
    cap = max(1, turns) * 2
    slice_ = messages[-cap:]
    parts: list[str] = []
    for m in slice_:
        role = m.get("role") or "user"
        label = "User" if role == "user" else "Assistant"
        content = (m.get("content") or "")[:max_chars_per_message]
        parts.append(f"{label}: {content}")
    return "\n\n".join(parts)


def load_messages(session_id: str) -> list[dict[str, Any]]:
    """Return prior messages for session (oldest first). Excludes current turn."""
    sid = (session_id or "").strip()
    if not sid:
        return []

    client = _redis_client()
    if client is not None:
        try:
            raw = client.get(_KEY_PREFIX + sid)
            if not raw:
                return []
            data = json.loads(raw)
            if isinstance(data, list):
                return [x for x in data if isinstance(x, dict)]
            return []
        except Exception:
            return []

    with _mem_lock:
        return list(_mem_store.get(sid, []))


def append_turn(session_id: str, user_content: str, assistant_content: str) -> None:
    """Append one user + one assistant message; trim to last N turns; refresh TTL."""
    sid = (session_id or "").strip()
    if not sid:
        return

    max_n = _max_message_count()
    ttl = get_settings().chat_history_ttl_seconds

    now = _utc_now_iso()
    entry_u = {"role": "user", "content": user_content, "ts": now}
    entry_a = {"role": "assistant", "content": assistant_content, "ts": now}

    client = _redis_client()
    if client is not None:
        try:
            raw = client.get(_KEY_PREFIX + sid)
            msgs: list[dict[str, Any]] = []
            if raw:
                data = json.loads(raw)
                if isinstance(data, list):
                    msgs = [x for x in data if isinstance(x, dict)]
            msgs.extend([entry_u, entry_a])
            msgs = msgs[-max_n:]
            payload = json.dumps(msgs, ensure_ascii=False)
            client.set(_KEY_PREFIX + sid, payload, ex=ttl if ttl > 0 else None)
        except Exception:
            pass
        return

    with _mem_lock:
        cur = list(_mem_store.get(sid, []))
        cur.extend([entry_u, entry_a])
        _mem_store[sid] = cur[-max_n:]
