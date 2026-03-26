"""Read-only Cypher validation for chat-generated queries."""

from __future__ import annotations

import re
from typing import Final

# Block write / admin patterns (case-insensitive word boundaries where sensible)
_FORBIDDEN: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"\b(?:CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|LOAD)\b", re.I),
    re.compile(r"\b(?:FOREACH|CALL\s+dbms\.|CALL\s+apoc\.)\b", re.I),
    re.compile(r"\b(?:GRANT|DENY|REVOKE|SHOW\s+USER|ALTER\s+DATABASE)\b", re.I),
)

# Allow CALL db.labels / db.relationshipTypes for schema introspection if we ever allow it
_ALLOWED_CALL_PREFIXES: Final[frozenset[str]] = frozenset(
    {
        "CALL db.labels(",
        "CALL db.relationshipTypes(",
        "CALL db.propertyKeys(",
    }
)


class CypherGuardError(ValueError):
    """Raised when generated Cypher fails validation."""


def _normalize_for_check(cypher: str) -> str:
    s = cypher.strip()
    if not s:
        raise CypherGuardError("Empty Cypher.")
    # Strip trailing semicolon for checks
    if s.endswith(";"):
        s = s[:-1].strip()
    return s


def validate_read_only_cypher(cypher: str, *, max_limit: int) -> str:
    """
    Ensure query is read-only and has a LIMIT <= max_limit.
    Returns normalized Cypher (single statement, no trailing semicolon for execution).
    """
    raw = cypher.strip()
    if not raw:
        raise CypherGuardError("Empty Cypher.")

    # Single statement only (best-effort)
    if raw.count(";") > 1 or (raw.endswith(";") and raw[:-1].strip().count(";") > 0):
        raise CypherGuardError("Multiple statements are not allowed.")

    s = _normalize_for_check(raw)

    upper = s.upper()
    if not upper.startswith(("MATCH", "OPTIONAL MATCH", "WITH", "UNWIND", "CALL", "RETURN")):
        # CALL ... is allowed only for allowlisted introspection
        if not upper.startswith("CALL"):
            raise CypherGuardError("Query must start with MATCH, OPTIONAL MATCH, WITH, UNWIND, CALL, or RETURN.")

    if upper.startswith("CALL"):
        allowed = any(s.strip().upper().startswith(p.upper()) for p in _ALLOWED_CALL_PREFIXES)
        if not allowed:
            raise CypherGuardError("CALL is restricted to db.labels / db.relationshipTypes / db.propertyKeys.")

    for pat in _FORBIDDEN:
        if pat.search(s):
            raise CypherGuardError(f"Forbidden pattern in query: {pat.pattern}")

    # Require LIMIT with bounded value
    limit_m = re.search(r"\bLIMIT\s+(\d+)\b", s, flags=re.I)
    if not limit_m:
        raise CypherGuardError(f"Query must include LIMIT <= {max_limit}.")
    lim = int(limit_m.group(1))
    if lim < 1 or lim > max_limit:
        raise CypherGuardError(f"LIMIT must be between 1 and {max_limit}.")

    # Require RETURN (read queries should return something)
    if not re.search(r"\bRETURN\b", s, flags=re.I):
        raise CypherGuardError("Query must include RETURN.")

    return s if not raw.endswith(";") else s


def extract_cypher_block(text: str) -> str:
    """Pull ```cypher ... ``` or first fenced block from model output."""
    fence = re.search(r"```(?:cypher)?\s*([\s\S]*?)```", text, re.I)
    if fence:
        return fence.group(1).strip()
    return text.strip()
