"""Canonical O2C schema text for LLM prompts + optional Neo4j introspection cache."""

from __future__ import annotations

import json
import time
from functools import lru_cache
from pathlib import Path

from .config import get_settings
from .neo4j_db import run_read_query

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DATA_MODEL_PATH = _PROJECT_ROOT / "resources" / "neo4j" / "o2c_data_model.json"

_INTROSPECTION_TTL_SEC = 300
_cache: tuple[float, str] | None = None


def _load_canonical_schema_text() -> str:
    if not _DATA_MODEL_PATH.is_file():
        return "(o2c_data_model.json not found — use Neo4j introspection only.)"
    data = json.loads(_DATA_MODEL_PATH.read_text(encoding="utf-8"))
    nodes = data.get("nodes") or []
    rels = data.get("relationships") or []
    lines: list[str] = [
        "## Canonical O2C model (labels & relationships)",
        f"Version: {data.get('metadata', {}).get('version', '?')}",
        "",
        "### Node labels (key property)",
    ]
    for n in nodes:
        label = n.get("label")
        kp = (n.get("key_property") or {}).get("name")
        lines.append(f"- {label}: key `{kp}`")
    lines.append("")
    lines.append("### Relationships")
    for r in rels:
        lines.append(
            f"- ({r.get('start_node_label')})-[:{r.get('type')}]->({r.get('end_node_label')})"
        )
    return "\n".join(lines)


@lru_cache
def get_canonical_schema_cached() -> str:
    """Static canonical schema (from repo JSON)."""
    return _load_canonical_schema_text()


def get_live_schema_snapshot() -> str:
    """
    Short live snapshot from Neo4j (cached a few minutes).
    Merges with canonical text for prompts.
    """
    global _cache
    now = time.monotonic()
    if _cache is not None and (now - _cache[0]) < _INTROSPECTION_TTL_SEC:
        return _cache[1]

    try:
        labels = run_read_query("CALL db.labels() YIELD label RETURN label ORDER BY label", {})
        rels = run_read_query(
            "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType ORDER BY relationshipType",
            {},
        )
        lb = [r["label"] for r in labels]
        rt = [r["relationshipType"] for r in rels]
        snap = (
            "### Live Neo4j (introspection)\n"
            f"Labels ({len(lb)}): {', '.join(lb)}\n"
            f"Relationship types ({len(rt)}): {', '.join(rt)}\n"
        )
    except Exception as exc:  # noqa: BLE001 — prompt should still work if DB down
        snap = f"(Neo4j introspection failed: {exc})\n"

    _cache = (now, snap)
    return snap


def build_schema_prompt_block() -> str:
    """Full block for Cypher-generation system prompt."""
    return get_canonical_schema_cached() + "\n\n" + get_live_schema_snapshot()
