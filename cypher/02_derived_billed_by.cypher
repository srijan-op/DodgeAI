// Derived relationship: materialize (SalesOrderItem)-[:BILLED_BY]->(InvoiceItem)
//
// Prerequisite: transactional load has already created:
//   - (SalesOrderItem)-[:FULFILLED_BY]->(DeliveryItem)  from outbound_delivery_items
//   - (DeliveryItem)-[:INVOICED_AS]->(InvoiceItem)      from billing_document_items
//
// Semantics: There is no direct FK in JSONL from order line to invoice line. This edge is the
// transitive closure of FULFILLED_BY ∘ INVOICED_AS. Keeping it explicit:
//   - Makes "broken flow" queries one hop from SalesOrderItem
//   - Gives the LLM a single relationship name grounded in a documented derivation
//
// Safe to run multiple times (MERGE is idempotent).

MATCH (soi:SalesOrderItem)-[:FULFILLED_BY]->(di:DeliveryItem)-[:INVOICED_AS]->(ii:InvoiceItem)
MERGE (soi)-[:BILLED_BY]->(ii);

// Optional: report how many edges exist after run
// MATCH (:SalesOrderItem)-[r:BILLED_BY]->(:InvoiceItem) RETURN count(r) AS billedByEdgeCount;
