// Post-load data quality checks (O2C v1). Run after ingestion.

// --- Counts by label ---
MATCH (n)
RETURN labels(n)[0] AS label, count(*) AS cnt
ORDER BY label;

// --- Delivery items with no link back to any sales order line ---
MATCH (di:DeliveryItem)
WHERE NOT EXISTS { MATCH (:SalesOrderItem)-[:FULFILLED_BY]->(di) }
RETURN count(di) AS deliveryItemsWithoutFulfillmentLink;

// --- Invoice items with no delivery line (unexpected if billing always references delivery) ---
MATCH (ii:InvoiceItem)
WHERE NOT EXISTS { MATCH (:DeliveryItem)-[:INVOICED_AS]->(ii) }
RETURN count(ii) AS invoiceItemsWithoutDeliveryLine;

// --- Sales order lines delivered but never invoiced on any invoice line (via delivery) ---
MATCH (soi:SalesOrderItem)-[:FULFILLED_BY]->(di:DeliveryItem)
WHERE NOT EXISTS { MATCH (di)-[:INVOICED_AS]->(:InvoiceItem) }
RETURN count(DISTINCT soi) AS orderLinesDeliveredNotInvoicedViaGraph;

// --- After 02_derived_billed_by.cypher: SO lines fulfilled but no materialized BILLED_BY ---
MATCH (soi:SalesOrderItem)-[:FULFILLED_BY]->(:DeliveryItem)-[:INVOICED_AS]->(:InvoiceItem)
WHERE NOT EXISTS { MATCH (soi)-[:BILLED_BY]->(:InvoiceItem) }
RETURN count(DISTINCT soi) AS orderLinesMissingDerivedBilledBy;

// --- BILLED_BY must always mirror the two-hop path (should be 0 when derivation is correct) ---
MATCH (soi:SalesOrderItem)-[:BILLED_BY]->(ii:InvoiceItem)
WHERE NOT EXISTS {
  MATCH (soi)-[:FULFILLED_BY]->(:DeliveryItem)-[:INVOICED_AS]->(ii)
}
RETURN count(*) AS invalidBilledByEdges;

// --- Invoices with no journal lines via POSTED_AS ---
MATCH (inv:Invoice)
WHERE NOT EXISTS { MATCH (inv)-[:POSTED_AS]->(:JournalEntry) }
RETURN count(inv) AS invoicesWithoutPostedJournal;

// --- Journal lines that reference a billing doc but invoice header missing ---
MATCH (je:JournalEntry)
WHERE je.referenceDocument IS NOT NULL AND je.referenceDocument <> ''
AND NOT EXISTS {
  MATCH (inv:Invoice)
  WHERE inv.billingDocument = je.referenceDocument
}
RETURN count(je) AS journalLinesWithOrphanBillingRef;

// --- Cleared AR expectation: open items (no payment) ---
MATCH (je:JournalEntry)
WHERE je.clearingAccountingDocument IS NULL OR je.clearingAccountingDocument = ''
RETURN count(je) AS journalLinesNotCleared;

// --- Payments with no customer ---
MATCH (p:Payment)
WHERE NOT EXISTS { MATCH (p)-[:MADE_BY]->(:Customer) }
RETURN count(p) AS paymentsWithoutCustomer;

// --- Duplicate risk: same journal line key from two sources (should be 0 after MERGE) ---
MATCH (je:JournalEntry)
WITH je.journalLineKey AS k, count(*) AS c
WHERE c > 1
RETURN k, c AS duplicates;
