# Canonical graph schema v1

Locked **labels** and **relationship types** for DodgeAI SAP O2C. Authoritative machine-readable definition: [`neo4j/o2c_data_model.json`](./neo4j/o2c_data_model.json).

## v1 change vs diagram-only model

- **`INVOICED_AS`**: `(DeliveryItem)-[:INVOICED_AS]->(InvoiceItem)` is **first-class** and matches JSONL (`referenceSdDocument` / item on billing lines point at delivery doc + line). Direction follows the physical flow: logistics line → billing line.
- **`BILLED_BY`**: `(SalesOrderItem)-[:BILLED_BY]->(InvoiceItem)` is **derived and materialized after load** from `(soi)-[:FULFILLED_BY]->(di)-[:INVOICED_AS]->(ii)` so implementers and the LLM see an explicit shortcut for “order line billing” and for broken-flow Cypher. Implementation: `cypher/02_derived_billed_by.cypher`.

## Labels

`Customer`, `Address`, `CompanyCode`, `SalesArea`, `SalesOrder`, `SalesOrderItem`, `ScheduleLine`, `Delivery`, `DeliveryItem`, `Invoice`, `InvoiceItem`, `JournalEntry`, `Payment`, `Product`, `Plant`, `StorageLocation`

## Relationship types

| Type | From → To |
|------|-----------|
| `PLACED` | Customer → SalesOrder |
| `HAS_ITEM` | SalesOrder → SalesOrderItem |
| `HAS_SCHEDULE` | SalesOrderItem → ScheduleLine |
| `FULFILLED_BY` | SalesOrderItem → DeliveryItem |
| `PART_OF` | DeliveryItem → Delivery |
| `INVOICED_AS` | DeliveryItem → InvoiceItem |
| `BILLED_BY` | SalesOrderItem → InvoiceItem *(derived; run after `INVOICED_AS` exists)* |
| `PART_OF` | InvoiceItem → Invoice |
| `POSTED_AS` | Invoice → JournalEntry |
| `CLEARED_BY` | JournalEntry → Payment |
| `MADE_BY` | Payment → Customer |
| `REFERENCES` | SalesOrderItem → Product; InvoiceItem → Product |
| `PRODUCED_AT` | SalesOrderItem → Plant |
| `SHIPPED_FROM` | DeliveryItem → Plant |
| `AVAILABLE_AT` | Product → Plant |
| `STORED_AT` | Product → StorageLocation |
| `HAS_ADDRESS` | Customer → Address |
| `ASSIGNED_TO` | Customer → CompanyCode |
| `IN_SALES_AREA` | Customer → SalesArea |
| `CANCELLED_BY` | Invoice → Invoice |

## Keys

See composite formulas in [SOURCE_OF_TRUTH_MAPPING.md](./SOURCE_OF_TRUTH_MAPPING.md). **JournalEntry** is one node per **FI line** (`journalLineKey`). **Payment** is one node per **clearing document** (`paymentKey`).

## Neo4j artifacts

| File | Purpose |
|------|---------|
| `cypher/01_constraints.cypher` | `UNIQUE` constraints (Neo4j 5.18) |
| `cypher/01_constraints_mcp_raw.cypher` | MCP-suggested `NODE KEY` form |
| `cypher/validation.cypher` | Post-load QA |
| `resources/neo4j/o2c_arrows_spine.json` | Arrows.app backbone (subset) |
| `cypher/02_derived_billed_by.cypher` | Materialize `BILLED_BY` after `INVOICED_AS` |

## MCP (data modeling server)

`validate_data_model` was run successfully on the full 16-label / 21-relationship model. `get_constraints_cypher_queries` produced the raw constraint script saved above.
