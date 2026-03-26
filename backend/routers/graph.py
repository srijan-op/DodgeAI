"""Initial graph viewport for force-directed UI (bounded, no dense supply mesh by default)."""

from fastapi import APIRouter, Query

from ..neo4j_db import run_read_query
from ..serializers import merge_graph_parts, record_values_to_graph

router = APIRouter()

# O2C spine only — avoids STORED_AT / AVAILABLE_AT explosion
CYPHER_VIEWPORT = """
MATCH (c:Customer)-[r1:PLACED]->(so:SalesOrder)
OPTIONAL MATCH (so)-[r2:HAS_ITEM]->(soi:SalesOrderItem)
WITH c, r1, so, r2, soi
LIMIT $limit_rows
RETURN c, r1, so, r2, soi
"""


@router.get("/graph")
def get_graph(
    limit_rows: int = Query(
        150,
        ge=10,
        le=500,
        description="Max rows from the spine pattern (caps payload size).",
    ),
) -> dict:
    rows = run_read_query(CYPHER_VIEWPORT, {"limit_rows": limit_rows})
    parts: list = []
    for rec in rows:
        filtered = {k: v for k, v in rec.items() if v is not None}
        if not filtered:
            continue
        parts.append(record_values_to_graph(filtered))
    return merge_graph_parts(parts)
