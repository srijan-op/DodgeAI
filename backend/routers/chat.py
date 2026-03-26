"""Chat endpoint — LangGraph agent with SSE (router → parallel tools → synthesis)."""

import json
import uuid
from typing import Any, AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from ..config import get_settings

router = APIRouter()


@router.post("/chat")
async def chat(request: Request) -> StreamingResponse:
    """
    JSON body: `{ "message": "...", "session_id": "..." }`.
    Streams SSE: `meta`, `plan`, `graph_highlight`, `token`, `done`.
    """
    settings = get_settings()
    if not settings.groq_api_key_list:
        raise HTTPException(
            status_code=503,
            detail="Chat agent requires GROQ_API_KEY and/or GROQ_API_KEYS in the environment (.env).",
        )

    try:
        body = await request.json()
    except Exception:
        body = {}
    msg = (body.get("message") or "").strip()
    if not msg:
        raise HTTPException(status_code=400, detail="Missing non-empty 'message'.")
    sid = str(body.get("session_id") or "").strip()
    if not sid:
        sid = str(uuid.uuid4())

    from ..agent.pipeline import stream_chat_turn
    from ..chat_memory import append_turn, load_messages

    history: list[dict[str, Any]] = load_messages(sid)

    async def event_stream() -> AsyncIterator[bytes]:
        token_buf: list[str] = []
        try:
            async for ev in stream_chat_turn(msg, session_id=sid, history=history):
                if ev.get("type") == "token":
                    d = ev.get("delta")
                    if isinstance(d, str) and d:
                        token_buf.append(d)
                yield f"data: {json.dumps(ev, default=str)}\n\n".encode()
        except Exception as e:  # noqa: BLE001
            err = {"type": "error", "detail": str(e)}
            yield f"data: {json.dumps(err)}\n\n".encode()
            yield f"data: {json.dumps({'type': 'done'})}\n\n".encode()
        else:
            assistant_text = "".join(token_buf)
            append_turn(sid, msg, assistant_text)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
