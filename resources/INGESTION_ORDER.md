# Ingestion order (Neo4j v1)

Run **constraints first** (see `cypher/01_constraints.cypher`), then batches below. Use `MERGE` on each node’s **key** property from [SOURCE_OF_TRUTH_MAPPING.md](./SOURCE_OF_TRUTH_MAPPING.md).

## Phase A — Reference / master data

1. **CompanyCode** — distinct `companyCode` from `customer_company_assignments`, `billing_document_headers`, `journal_entry_items_accounts_receivable`, etc.
2. **SalesArea** — distinct triples from `customer_sales_area_assignments` (and optionally `sales_order_headers`).
3. **Plant** — `plants`
4. **Product** — `products`
5. **StorageLocation** — distinct `(plant, storageLocation)` from `product_storage_locations` (and optionally delivery / order items if you want slocs not in product file)
6. **Customer** — `business_partners`
7. **Address** — `business_partner_addresses` + **HAS_ADDRESS**

## Phase B — Customer context edges

8. **ASSIGNED_TO** — `customer_company_assignments`
9. **IN_SALES_AREA** — `customer_sales_area_assignments`

## Phase C — Product / supply structure

10. **AVAILABLE_AT** — `product_plants`
11. **STORED_AT** — `product_storage_locations` → **StorageLocation** nodes

## Phase D — Operational documents (headers before items)

12. **SalesOrder** — `sales_order_headers` + **PLACED**
13. **SalesOrderItem** — `sales_order_items` + **HAS_ITEM**, **REFERENCES**, **PRODUCED_AT** (skip missing Product/Plant)
14. **ScheduleLine** — `sales_order_schedule_lines` + **HAS_SCHEDULE**
15. **Delivery** — `outbound_delivery_headers`
16. **DeliveryItem** — `outbound_delivery_items` + **PART_OF**, **FULFILLED_BY**, **SHIPPED_FROM**
17. **Invoice** — merge `billing_document_headers` + `billing_document_cancellations` (same `billingDocument` → one node; last write wins or explicit merge rules for cancellation flags)
18. **InvoiceItem** — `billing_document_items` + **PART_OF**, **INVOICED_AS** (from matching `DeliveryItem` → `InvoiceItem`), **REFERENCES**

## Phase E — Accounting

19. **JournalEntry** — `journal_entry_items_accounts_receivable` and `payments_accounts_receivable` (MERGE on `journalLineKey` to dedupe)
20. **POSTED_AS** — **Invoice** → **JournalEntry** on `(companyCode, fiscalYear, accountingDocument)`
21. **Payment** — distinct `(companyCode, clearingDocFiscalYear, clearingAccountingDocument)` from lines where `clearingAccountingDocument` is set
22. **CLEARED_BY** — **JournalEntry** → **Payment** using `paymentKey`
23. **MADE_BY** — **Payment** → **Customer** (from `customer` on any linked journal line; one edge per payment)

## Phase F — Optional enrichments

24. **BILLED_BY** — run `cypher/02_derived_billed_by.cypher` (requires `FULFILLED_BY` + `INVOICED_AS` complete)
25. **CANCELLED_BY** — between **Invoice** nodes when cancellation mapping is known
26. Optional: **Invoice** → **Customer** via `soldToParty` if you want billing-side customer without traversing **Payment**

## Notes

- **Item normalization** must be applied consistently in loaders before `MERGE`.
- Load in a single transaction per phase for small datasets; for large JSONL use batched `UNWIND` + `MERGE` in Cypher or a streaming driver.
- `import/` volume in Docker is `./import` — place CSVs there if you switch from JSONL to `LOAD CSV`.
