"""Convert Neo4j driver types to JSON-safe structures for API responses."""

from __future__ import annotations

from typing import Any

from neo4j.graph import Node, Path, Relationship

from .graph_schema import LABEL_KEY_PROPERTY


def _walk_value_for_highlight_ids(value: Any, ids: set[str]) -> None:
    """Collect API-style node ids from Neo4j driver values (paths, rels, nested lists/maps)."""
    if isinstance(value, Node):
        ids.add(serialize_node(value)["id"])
        return
    if isinstance(value, Relationship):
        sn = value.start_node
        en = value.end_node
        if sn is not None:
            ids.add(serialize_node(sn)["id"])
        if en is not None:
            ids.add(serialize_node(en)["id"])
        return
    if isinstance(value, Path):
        for n in value.nodes:
            ids.add(serialize_node(n)["id"])
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _walk_value_for_highlight_ids(item, ids)
        return
    if isinstance(value, dict):
        # Already-serialized node shape (e.g. nested in a map column)
        lid = value.get("id")
        labs = value.get("labels")
        if isinstance(lid, str) and isinstance(labs, list):
            ids.add(lid)
            return
        for v in value.values():
            _walk_value_for_highlight_ids(v, ids)


def collect_highlight_node_ids(rows: list[dict[str, Any]]) -> list[str]:
    """Ids for graph_highlight SSE — same format as /api/graph node ``id`` (``Label:key``)."""
    ids: set[str] = set()
    for row in rows:
        for v in row.values():
            _walk_value_for_highlight_ids(v, ids)
    return sorted(ids)


def serialize_node(node: Node) -> dict[str, Any]:
    labels = list(node.labels)
    if not labels:
        return {"id": node.element_id, "labels": [], "properties": dict(node)}
    primary = LABEL_KEY_PROPERTY.get(labels[0])
    props = dict(node)
    pk = props.get(primary)
    if pk is None:
        pk = next(iter(props.values()), node.element_id)
    nid = f"{labels[0]}:{pk}"
    return {"id": nid, "labels": labels, "properties": props}


def record_values_to_graph(record: dict[str, Any]) -> tuple[dict[str, dict], list[dict]]:
    """Extract nodes and edges from a single record.data() result."""
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    for v in record.values():
        if isinstance(v, Node):
            nd = serialize_node(v)
            nodes[nd["id"]] = nd
        elif isinstance(v, Relationship):
            sn = v.start_node
            en = v.end_node
            if sn is None or en is None:
                continue
            s = serialize_node(sn)
            t = serialize_node(en)
            nodes[s["id"]] = s
            nodes[t["id"]] = t
            edges.append(
                {
                    "id": v.element_id,
                    "type": v.type,
                    "properties": dict(v),
                    "source": s["id"],
                    "target": t["id"],
                }
            )

    return nodes, edges


def path_to_graph_parts(path: Path) -> tuple[dict[str, dict], list[dict]]:
    """Serialize a Neo4j Path into the same shape as expand/graph APIs."""
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    for n in path.nodes:
        nd = serialize_node(n)
        nodes[nd["id"]] = nd
    for r in path.relationships:
        sn = r.start_node
        en = r.end_node
        if sn is None or en is None:
            continue
        s = serialize_node(sn)
        t = serialize_node(en)
        nodes[s["id"]] = s
        nodes[t["id"]] = t
        edges.append(
            {
                "id": r.element_id,
                "type": r.type,
                "properties": dict(r),
                "source": s["id"],
                "target": t["id"],
            }
        )
    return nodes, edges


def merge_graph_parts(
    parts: list[tuple[dict[str, dict], list[dict]]],
) -> dict[str, Any]:
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    seen_edges: set[str] = set()
    for n_dict, e_list in parts:
        for nid, n in n_dict.items():
            nodes[nid] = n
        for e in e_list:
            eid = e.get("id")
            if eid and eid not in seen_edges:
                seen_edges.add(eid)
                edges.append(e)
    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "stats": {"nodes": len(nodes), "edges": len(edges)},
    }
