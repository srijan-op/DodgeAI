"""Shortest path between two business-key nodes (for graph UI)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from neo4j.graph import Path
from pydantic import BaseModel, Field

from ..graph_schema import ALLOWED_EXPAND_LABELS, LABEL_KEY_PROPERTY
from ..neo4j_db import run_read_query
from ..serializers import merge_graph_parts, path_to_graph_parts

router = APIRouter()


def _split_api_node_id(node_id: str) -> tuple[str, str]:
    i = node_id.find(":")
    if i <= 0 or i == len(node_id) - 1:
        raise ValueError("Invalid node id; expected Label:key")
    return node_id[:i].strip(), node_id[i + 1 :]


class ShortestPathBody(BaseModel):
    from_id: str = Field(..., description="API node id, e.g. Customer:320000082")
    to_id: str = Field(..., description="API node id, e.g. SalesOrder:740537")
    max_hops: int = Field(8, ge=1, le=16)


@router.post("/path/shortest")
def shortest_path(body: ShortestPathBody) -> dict:
    try:
        la, ka = _split_api_node_id(body.from_id.strip())
        lb, kb = _split_api_node_id(body.to_id.strip())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    for lab in (la, lb):
        if lab not in ALLOWED_EXPAND_LABELS:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown label {lab!r}. Allowed: {sorted(ALLOWED_EXPAND_LABELS)}",
            )

    pa = LABEL_KEY_PROPERTY[la]
    pb = LABEL_KEY_PROPERTY[lb]
    mh = body.max_hops

    cypher = f"""
    MATCH (a:{la} {{{pa}: $ka}})
    MATCH (b:{lb} {{{pb}: $kb}})
    MATCH p = shortestPath((a)-[*..{mh}]-(b))
    RETURN p AS path
    LIMIT 1
    """
    rows = run_read_query(cypher, {"ka": ka, "kb": kb})
    if not rows:
        raise HTTPException(status_code=404, detail="No path found between these nodes.")

    raw = rows[0].get("path")
    if not isinstance(raw, Path):
        raise HTTPException(status_code=404, detail="No path found between these nodes.")

    parts = [path_to_graph_parts(raw)]
    payload = merge_graph_parts(parts)
    path_edge_ids = [e["id"] for e in payload["edges"]]
    path_node_ids = [n["id"] for n in payload["nodes"]]
    return {
        **payload,
        "path_edge_ids": path_edge_ids,
        "path_node_ids": path_node_ids,
    }
