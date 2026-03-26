"""Read-only O2C graph analytics: integrity checks and structural summaries (no GDS required)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .graph_schema import LABEL_KEY_PROPERTY
from .neo4j_db import run_read_query


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _one_int(rows: list[dict[str, Any]], key: str = "c") -> int:
    if not rows:
        return 0
    v = rows[0].get(key)
    try:
        return int(v) if v is not None else 0
    except (TypeError, ValueError):
        return 0


def _label_counts() -> dict[str, int]:
    """Count nodes per label (UNWIND labels(n); compatible with Community edition)."""
    q = """
    MATCH (n)
    UNWIND labels(n) AS lb
    RETURN lb, count(DISTINCT n) AS c
    """
    rows = run_read_query(q, {})
    out: dict[str, int] = {lb: 0 for lb in LABEL_KEY_PROPERTY.keys()}
    for row in rows:
        lb = row.get("lb")
        if isinstance(lb, str) and lb in out:
            out[lb] = int(row.get("c") or 0)
    return out


def _check_count(cypher: str) -> int:
    rows = run_read_query(cypher, {})
    return _one_int(rows)


def _sample_ids(
    cypher: str,
    label: str,
    *,
    sample_limit: int,
) -> list[str]:
    rows = run_read_query(cypher, {"sample_limit": sample_limit})
    out: list[str] = []
    for row in rows:
        key = row.get("k")
        if key is None or key == "":
            continue
        out.append(f"{label}:{key}")
    return out


def build_o2c_analytics_report(*, sample_limit: int) -> dict[str, Any]:
    """
    Aggregate label counts, O2C integrity metrics, degree leaders, and order-volume buckets.
    Uses only declarative Cypher (Neo4j Community; no Graph Data Science plugin).
    """
    sl = max(1, min(50, sample_limit))

    label_counts = _label_counts()

    integrity_specs: list[dict[str, Any]] = [
        {
            "id": "sales_order_without_items",
            "title": "Sales orders with no line items (HAS_ITEM)",
            "label": "SalesOrder",
            "count_cypher": (
                "MATCH (so:SalesOrder) WHERE NOT (so)-[:HAS_ITEM]->() RETURN count(so) AS c"
            ),
            "sample_cypher": """
            MATCH (so:SalesOrder)
            WHERE NOT (so)-[:HAS_ITEM]->()
            RETURN so.salesOrder AS k
            LIMIT $sample_limit
            """,
        },
        {
            "id": "sales_order_item_not_fulfilled",
            "title": "Sales order lines with no delivery link (FULFILLED_BY)",
            "label": "SalesOrderItem",
            "count_cypher": (
                "MATCH (soi:SalesOrderItem) WHERE NOT (soi)-[:FULFILLED_BY]->() "
                "RETURN count(soi) AS c"
            ),
            "sample_cypher": """
            MATCH (soi:SalesOrderItem)
            WHERE NOT (soi)-[:FULFILLED_BY]->()
            RETURN soi.salesOrderItemKey AS k
            LIMIT $sample_limit
            """,
        },
        {
            "id": "delivery_item_not_invoiced",
            "title": "Delivery lines with no billing line (INVOICED_AS)",
            "label": "DeliveryItem",
            "count_cypher": (
                "MATCH (di:DeliveryItem) WHERE NOT (di)-[:INVOICED_AS]->() "
                "RETURN count(di) AS c"
            ),
            "sample_cypher": """
            MATCH (di:DeliveryItem)
            WHERE NOT (di)-[:INVOICED_AS]->()
            RETURN di.deliveryItemKey AS k
            LIMIT $sample_limit
            """,
        },
        {
            "id": "invoice_not_posted",
            "title": "Invoices with no journal lines (POSTED_AS)",
            "label": "Invoice",
            "count_cypher": (
                "MATCH (inv:Invoice) WHERE NOT (inv)-[:POSTED_AS]->() RETURN count(inv) AS c"
            ),
            "sample_cypher": """
            MATCH (inv:Invoice)
            WHERE NOT (inv)-[:POSTED_AS]->()
            RETURN inv.billingDocument AS k
            LIMIT $sample_limit
            """,
        },
        {
            "id": "billed_by_path_mismatch",
            "title": "SO lines where delivery→invoice path exists but BILLED_BY shortcut is missing",
            "label": "SalesOrderItem",
            "count_cypher": (
                "MATCH (soi:SalesOrderItem)-[:FULFILLED_BY]->(:DeliveryItem)-[:INVOICED_AS]->(ii:InvoiceItem) "
                "WHERE NOT (soi)-[:BILLED_BY]->(ii) RETURN count(DISTINCT soi) AS c"
            ),
            "sample_cypher": """
            MATCH (soi:SalesOrderItem)-[:FULFILLED_BY]->(:DeliveryItem)-[:INVOICED_AS]->(ii:InvoiceItem)
            WHERE NOT (soi)-[:BILLED_BY]->(ii)
            RETURN DISTINCT soi.salesOrderItemKey AS k
            LIMIT $sample_limit
            """,
        },
    ]

    integrity_checks: list[dict[str, Any]] = []
    for spec in integrity_specs:
        cnt = _check_count(spec["count_cypher"])
        samples = _sample_ids(spec["sample_cypher"], spec["label"], sample_limit=sl)
        integrity_checks.append(
            {
                "id": spec["id"],
                "title": spec["title"],
                "count": cnt,
                "sample_node_ids": samples,
            }
        )

    bucket_q = """
    MATCH (c:Customer)-[:PLACED]->(so:SalesOrder)
    WITH c, count(so) AS n
    WITH
      CASE
        WHEN n = 1 THEN '1'
        WHEN n <= 5 THEN '2-5'
        WHEN n <= 20 THEN '6-20'
        ELSE '21+'
      END AS bucket,
      c
    RETURN bucket, count(c) AS customers
    ORDER BY
      CASE bucket
        WHEN '1' THEN 1
        WHEN '2-5' THEN 2
        WHEN '6-20' THEN 3
        WHEN '21+' THEN 4
        ELSE 5
      END
    """
    bucket_rows = run_read_query(bucket_q, {})
    order_volume_buckets = [
        {"bucket": str(r.get("bucket")), "customers": int(r.get("customers") or 0)}
        for r in bucket_rows
    ]

    top_cust_q = """
    MATCH (c:Customer)-[:PLACED]->(so:SalesOrder)
    WITH c, count(so) AS orders
    ORDER BY orders DESC
    LIMIT 10
    RETURN c.businessPartner AS k, orders
    """
    top_rows = run_read_query(top_cust_q, {})
    top_customers_by_orders = [
        {"node_id": f"Customer:{r.get('k')}", "orders": int(r.get("orders") or 0)}
        for r in top_rows
        if r.get("k") is not None
    ]

    prod_plant_q = """
    MATCH (p:Product)-[:AVAILABLE_AT]->(pl:Plant)
    RETURN count(DISTINCT p) AS products, count(DISTINCT pl) AS plants, count(*) AS relationships
    """
    pp_rows = run_read_query(prod_plant_q, {})
    product_plant_connectivity = {
        "products_with_plant_link": _one_int(pp_rows, "products"),
        "distinct_plants": _one_int(pp_rows, "plants"),
        "available_at_relationships": _one_int(pp_rows, "relationships"),
    }

    return {
        "generated_at": _utc_now(),
        "note": (
            "Analytics use read-only Cypher only. "
            "Louvain/PageRank-style clustering requires Neo4j Graph Data Science (GDS); "
            "order-volume buckets and integrity checks work on Neo4j Community."
        ),
        "label_counts": label_counts,
        "integrity_checks": integrity_checks,
        "order_volume_buckets": order_volume_buckets,
        "top_customers_by_orders": top_customers_by_orders,
        "product_plant_connectivity": product_plant_connectivity,
    }
