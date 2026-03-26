"""Expand a node by business label + key (stable across restarts)."""

from fastapi import APIRouter, HTTPException, Query

from ..graph_schema import ALLOWED_EXPAND_LABELS, LABEL_KEY_PROPERTY
from ..neo4j_db import run_read_query
from ..serializers import merge_graph_parts, record_values_to_graph

router = APIRouter()


@router.get("/nodes/{label}/{key}/expand")
def expand_node(
    label: str,
    key: str,
    limit: int = Query(
        50,
        ge=1,
        le=200,
        description="Max neighbor rows (each row is n-r-m).",
    ),
) -> dict:
    """
    `label` must be a known node label (e.g. Invoice, Customer).
    `key` must be URL-encoded if it contains reserved characters (e.g. `|` in composite keys).
    """
    label_clean = label.strip()
    if label_clean not in ALLOWED_EXPAND_LABELS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown label. Allowed: {sorted(ALLOWED_EXPAND_LABELS)}",
        )
    prop = LABEL_KEY_PROPERTY[label_clean]
    # Label/property names are from an allowlist only — `key` is parameterized.
    cypher = f"""
    MATCH (n:{label_clean} {{{prop}: $key}})
    OPTIONAL MATCH (n)-[r]-(m)
    WITH n, r, m
    LIMIT $limit
    RETURN n, r, m
    """
    rows = run_read_query(cypher, {"key": key, "limit": limit})
    if not rows:
        raise HTTPException(status_code=404, detail="Node not found.")
    parts = [record_values_to_graph(rec) for rec in rows]
    return merge_graph_parts(parts)
