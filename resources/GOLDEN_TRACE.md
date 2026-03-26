# Golden trace recipes (v1)

Use these paths to verify the graph and to answer assignment-style questions.

## 1) Billing document → full operational chain (SD)

**Goal:** `BillingDocument` → invoice lines → delivery lines → order lines → order → customer.

1. Start at **Invoice** `(:Invoice { billingDocument: $BILL })`.
2. **InvoiceItem**: `(i)<-[:PART_OF]-(ii:InvoiceItem)`
3. **DeliveryItem**: `(di:DeliveryItem)-[:INVOICED_AS]->(ii)`  
   - Join in data: `ii.referenceSdDocument` = `di.deliveryDocument` and normalized items match.
4. **SalesOrderItem**: `(soi:SalesOrderItem)-[:FULFILLED_BY]->(di)`  
   - Join in data: `di.referenceSdDocument` = `soi.salesOrder`, normalized items match.
5. **SalesOrder**: `(so)<-[:HAS_ITEM]-(soi)` … actually `(so)-[:HAS_ITEM]->(soi)`, so `(soi)<-[:HAS_ITEM]-(so)` or match `soi.salesOrder = so.salesOrder`.
6. **Customer**: `(c)-[:PLACED]->(so)` via `so.soldToParty = c.businessPartner`.

Cypher sketch:

```cypher
MATCH (inv:Invoice { billingDocument: $billingDoc })
MATCH (ii:InvoiceItem)-[:PART_OF]->(inv)
MATCH (di:DeliveryItem)-[:INVOICED_AS]->(ii)
MATCH (soi:SalesOrderItem)-[:FULFILLED_BY]->(di)
MATCH (so:SalesOrder)-[:HAS_ITEM]->(soi)
MATCH (cust:Customer)-[:PLACED]->(so)
RETURN cust, so, soi, di, ii, inv
```

## 2) Billing document → journal → clearing (FI)

**Goal:** Link posted FI document and lines to billing; then clearing payment.

**Header shortcut (one FI doc per invoice in this extract):**

- `Invoice.accountingDocument`, `Invoice.fiscalYear`, `Invoice.companyCode` match **JournalEntry** lines.

```cypher
MATCH (inv:Invoice { billingDocument: $billingDoc })
MATCH (inv)-[:POSTED_AS]->(je:JournalEntry)
RETURN inv, collect(je) AS lines
```

**Line-level link by billing number (matches UI “ReferenceDocument” style):**

```cypher
MATCH (je:JournalEntry)
WHERE je.referenceDocument = $billingDoc
RETURN je
```

**Payment:**

```cypher
MATCH (je:JournalEntry)
WHERE je.referenceDocument = $billingDoc
MATCH (je)-[:CLEARED_BY]->(p:Payment)
OPTIONAL MATCH (p)-[:MADE_BY]->(c:Customer)
RETURN je, p, c
```

## 3) End-to-end single query (SD + FI)

Combine sections 1 and 2 on the same `$billingDoc`:

```cypher
MATCH (inv:Invoice { billingDocument: $billingDoc })
OPTIONAL MATCH (ii:InvoiceItem)-[:PART_OF]->(inv)
OPTIONAL MATCH (di:DeliveryItem)-[:INVOICED_AS]->(ii)
OPTIONAL MATCH (soi:SalesOrderItem)-[:FULFILLED_BY]->(di)
OPTIONAL MATCH (so:SalesOrder)-[:HAS_ITEM]->(soi)
OPTIONAL MATCH (cust:Customer)-[:PLACED]->(so)
OPTIONAL MATCH (inv)-[:POSTED_AS]->(je:JournalEntry)
OPTIONAL MATCH (je)-[:CLEARED_BY]->(p:Payment)
RETURN inv, collect(DISTINCT ii) AS items, collect(DISTINCT di) AS delItems,
       collect(DISTINCT soi) AS orderItems, so, cust, collect(DISTINCT je) AS journalLines, p
```

Tune `collect` vs `DISTINCT` depending on whether you need one row or graph projection.

## 4) Broken flows (examples)

- **Delivered not billed**: `DeliveryItem` with no outgoing `INVOICED_AS` to any **InvoiceItem** — or equivalently **SalesOrderItem** with `FULFILLED_BY` to such a `DeliveryItem` and no `BILLED_BY` to any **InvoiceItem** (after derived edges are built).
- **Billed not delivered (data gap)**: **InvoiceItem** with no incoming `INVOICED_AS` from **DeliveryItem** (unexpected for F2 from delivery).
- **Shortcut for “order line never billed”**: `(soi:SalesOrderItem)` where `NOT (soi)-[:BILLED_BY]->(:InvoiceItem)` (only valid after `02_derived_billed_by.cypher`).
- **Posted not cleared**: **JournalEntry** with `clearingAccountingDocument` empty (open item).
- **Orphan journal**: `referenceDocument` set but no **Invoice** with that `billingDocument`.

Implement as `MATCH ... WHERE NOT EXISTS { ... }` patterns in `cypher/validation.cypher`.
