# Backend: query layer & security (Neo4j Community)

This doc covers the **free** stack: **Neo4j Community** (e.g. Docker), **FastAPI**, **LangGraph**, **Redis**. Further API/agent details will live in separate docs.

---

## 1. Architecture (this slice)

```
React  →  FastAPI (/api/chat, /api/graph, /api/nodes/.../expand)
              →  LangGraph (guardrail → agent → tools → SSE: tokens, highlights, errors)
              →  Tools: graph_query | analyze_flow | expand_node | get_schema | highlight_nodes
              →  Neo4j (Bolt)     — chat path uses validated read-only execution
              →  Redis            — session / conversation memory
```

- **Cypher runs only on the server**, inside tool implementations (Python + official `neo4j` driver). Never in the browser.
- **Ingestion** (`scripts/ingest_o2c.py`) uses **separate** credentials from the chat API when configured (recommended).
- **Neo4j: username vs database name** — The default superuser is often literally named `neo4j` (`NEO4J_USER`). The default **logical graph database** is also often named `neo4j` (`NEO4J_DATABASE`). Same string, **two different things**: who is logging in vs which named database file to query. Sessions use `database=NEO4J_DATABASE` explicitly so the API matches Browser’s “default” DB.

---

## 2. Why Community changes the security model

- **Neo4j Enterprise** can grant a DB user **true read-only** graph privileges (RBAC).
- **Neo4j Community** does **not** expose the same fine-grained read-only role for the same database.

So for **free / Community**, **enforcement is primarily application-side**: validate queries, limit scope, timeout, separate admin user for loads.

---

## 3. Security approach (concise checklist)

| Layer | Action |
|--------|--------|
| **Tool contract** | `graph_query` only invokes a **read path** (no `MERGE`/`DELETE`/writes in chat). Writes stay in ingestion/admin only. |
| **Cypher validation** | Before `session.run`: reject or strip destructive / admin patterns (`DELETE`, `DETACH`, `CREATE`, `MERGE`, `DROP`, `LOAD`, `CALL` unless explicitly allowlisted, etc.). Enforce **max row** via `LIMIT` cap. |
| **Execution** | **Parameterized** queries where values come from user text (never concatenate raw user strings into Cypher). |
| **Timeouts** | Driver / transaction timeout so pathological queries cannot hang workers. |
| **Credentials** | Optional second Neo4j user for the API (password separation); does not replace validation on Community. |
| **API** | Rate limits (per IP / `session_id`), max JSON body size; optional API key in production. |

**Defense in depth:** validation catches mistakes and many abuse patterns; DB privileges on Community are weaker, so validation + limits are **required**, not optional.

---

## 4. Relation to other tools

- **`analyze_flow` / `expand_node`**: fixed or templated Cypher — lowest risk; still use same executor with timeout + `LIMIT` where applicable.
- **`get_schema`**: static string or cached `CALL db.labels()` / `db.relationshipTypes()` — no arbitrary user Cypher.

---

## 5. Graph API contract & initial load (viewport model)

**Full graph in Neo4j vs “what the UI shows”**  
All nodes and relationships live in the database. **Filtered / paged loading does not delete anything** — the API returns only a **subset** for the current view. Anything not yet returned is still queryable via **search**, **chat tools**, or **expand**.

**Why not return everything on `GET /api/graph`**  
At ~1.7k nodes and ~22k relationships (with dense types like `STORED_AT`), a single JSON payload can stress the API, browser, and layout. Use a **viewport**: cap `maxNodes` / `maxEdges`, and optionally **exclude** or **sample** very dense rel types on first paint.

**First paint (recommended)**  
Prefer **business spine** nodes for O2C storytelling, not the whole hierarchy:

- **Good default:** `Customer`, `SalesOrder`, `Delivery`, `Invoice`, `Payment` (and optionally `Product`) — **header-level** entities, **limited count** (e.g. `LIMIT 50` or `LIMIT` per label), **no** bulk `STORED_AT` / `AVAILABLE_AT` on first load unless you need supply-chain view.
- **Avoid** loading the full `Product`–`StorageLocation` mesh first — it dominates edge count and obscures the O2C flow.

**Node identity in URLs**  
`GET /api/nodes/:id/expand` should use **stable business keys** (e.g. `billingDocument`, `salesOrderItemKey`) or a dedicated `publicId` you store on nodes — **not** Neo4j internal `elementId` (can change across store maintenance). Document the `:id` format in the OpenAPI spec.

**Expand on click**  
When the user selects a node, call **expand** with that node’s **key** + label. The backend runs a **bounded** neighborhood query (e.g. `LIMIT` edges per type, optional rel-type filter). The frontend **merges** new nodes/edges into the graph state — **additive**, so exploration continues as the user drills in without needing the full graph upfront.

---

## 6. Out of scope here (later docs)

- LangGraph node graph (guardrail, retries, memory format).
- SSE event types and frontend contract.
- LLM provider keys and fallbacks.
- Exact OpenAPI schemas for `/api/graph` query params (`limit`, `includeLabels`, `excludeRelTypes`).
