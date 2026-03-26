# Source of truth: JSONL → Neo4j (v1)

Base path: `sap-o2c-data/<folder>/part-*.jsonl`.

**SD item normalization** (use everywhere items are joined across SD objects):

- `normItem(x)` = strip leading zeros from numeric item strings, e.g. `000010` → `10`, keep non-digits as-is if any.

**Composite key helpers** (store on nodes as listed):

| Helper | Formula |
|--------|---------|
| `salesOrderItemKey` | `salesOrder + '\|' + normItem(salesOrderItem)` |
| `deliveryItemKey` | `deliveryDocument + '\|' + normItem(deliveryDocumentItem)` |
| `invoiceItemKey` | `billingDocument + '\|' + normItem(billingDocumentItem)` |
| `scheduleLineKey` | `salesOrder + '\|' + normItem(salesOrderItem) + '\|' + scheduleLine` |
| `journalLineKey` | `companyCode + '\|' + fiscalYear + '\|' + accountingDocument + '\|' + accountingDocumentItem` |
| `paymentKey` | `companyCode + '\|' + clearingDocFiscalYear + '\|' + clearingAccountingDocument` |
| `addressKey` | `businessPartner + '\|' + addressId` |
| `salesAreaKey` | `salesOrganization + '\|' + distributionChannel + '\|' + division` |
| `storageLocationKey` | `plant + '\|' + storageLocation` |

---

## Mapping table

| JSONL folder | Neo4j label(s) | Properties on node (subset; load full JSON as needed) | Edges created (match rule) |
|--------------|----------------|------------------------------------------------------|----------------------------|
| `business_partners` | **Customer** | `businessPartner`, `businessPartnerName`, `businessPartnerIsBlocked`, … | — |
| `business_partner_addresses` | **Address** | `addressKey`, `businessPartner`, `addressId`, `cityName`, `country`, `region`, `streetName`, `postalCode`, … | **HAS_ADDRESS**: `Customer.businessPartner = row.businessPartner` |
| `customer_company_assignments` | **CompanyCode** (distinct `companyCode`) | `companyCode` | **ASSIGNED_TO**: `Customer.customer` = `row.customer` → `CompanyCode` |
| `customer_sales_area_assignments` | **SalesArea** | `salesAreaKey`, `salesOrganization`, `distributionChannel`, `division`, … | **IN_SALES_AREA**: `Customer.customer` = `row.customer` |
| `sales_order_headers` | **SalesOrder** | `salesOrder`, `soldToParty`, `totalNetAmount`, `transactionCurrency`, `salesOrganization`, `distributionChannel`, `organizationDivision`, … | **PLACED**: `SalesOrder.soldToParty` = `Customer.businessPartner`; optional link header to **SalesArea** if you add `(:SalesOrder)-[:IN_AREA]->(:SalesArea)` (same triple as header) |
| `sales_order_items` | **SalesOrderItem** | `salesOrderItemKey`, `salesOrder`, `salesOrderItem`, `material`, `requestedQuantity`, `netAmount`, `productionPlant`, `storageLocation`, … | **HAS_ITEM**: same `salesOrder`; **REFERENCES**: `material` = `Product.product`; **PRODUCED_AT**: `productionPlant` = `Plant.plant` |
| `sales_order_schedule_lines` | **ScheduleLine** | `scheduleLineKey`, `salesOrder`, `salesOrderItem`, `scheduleLine`, `confirmedDeliveryDate`, … | **HAS_SCHEDULE**: parent **SalesOrderItem** by `salesOrder` + `normItem(salesOrderItem)` |
| `outbound_delivery_headers` | **Delivery** | `deliveryDocument`, `shippingPoint`, `creationDate`, … | — |
| `outbound_delivery_items` | **DeliveryItem** | `deliveryItemKey`, `deliveryDocument`, `deliveryDocumentItem`, `referenceSdDocument`, `referenceSdDocumentItem`, `plant`, `storageLocation`, `actualDeliveryQuantity`, … | **PART_OF**: same `deliveryDocument`; **FULFILLED_BY**: **SalesOrderItem** where `referenceSdDocument` = `salesOrder` and `normItem(referenceSdDocumentItem)` = `normItem(salesOrderItem)`; **SHIPPED_FROM**: `plant` = `Plant.plant` |
| `billing_document_headers` (+ cancellations file) | **Invoice** | `billingDocument`, `soldToParty`, `companyCode`, `fiscalYear`, `accountingDocument`, `totalNetAmount`, `billingDocumentIsCancelled`, `cancelledBillingDocument`, … | **POSTED_AS** targets **JournalEntry** lines: `companyCode`, `fiscalYear`, `accountingDocument`; optional **SOLD_TO** → Customer via `soldToParty` if you extend schema |
| `billing_document_items` | **InvoiceItem** | `invoiceItemKey`, `billingDocument`, `billingDocumentItem`, `material`, `referenceSdDocument`, `referenceSdDocumentItem`, … | **PART_OF**: same `billingDocument`; **INVOICED_AS**: `(DeliveryItem)-[:INVOICED_AS]->(InvoiceItem)` where `InvoiceItem.referenceSdDocument` = `DeliveryItem.deliveryDocument` and `normItem(referenceSdDocumentItem)` = `normItem(deliveryDocumentItem)` (create edge from delivery side when both nodes exist); **REFERENCES**: `material` = `Product.product` |
| `journal_entry_items_accounts_receivable` | **JournalEntry** | `journalLineKey`, `referenceDocument`, `glAccount`, amounts, dates, `clearingAccountingDocument`, `clearingDocFiscalYear`, `customer`, … | **POSTED_AS** inverse from **Invoice** (header `accountingDocument`); link to **Invoice** via `referenceDocument` = `billingDocument` when typing RV billing (optional rel **SUPPORTS_INVOICE**); **CLEARED_BY** → **Payment** when clearing fields present |
| `payments_accounts_receivable` | **JournalEntry** (same label) or merge duplicate lines | Same shape as AR items; use same `journalLineKey` merge | Same as above; ensures lines only in payments file are still nodes |
| *(derived from AR lines)* | **Payment** | `paymentKey` only or + posting metadata | **CLEARED_BY**: from each **JournalEntry** with non-null `clearingAccountingDocument`; **MADE_BY**: `JournalEntry.customer` = `Customer.businessPartner` (collapse one **MADE_BY** per payment from representative line) |
| `products` | **Product** | `product`, `productType`, `productGroup`, … | — |
| `product_plants` | **AVAILABLE_AT** edges | — | **Product** → **Plant** on `(product, plant)` |
| `product_storage_locations` | **StorageLocation** nodes | `storageLocationKey`, `plant`, `storageLocation` | **STORED_AT**: **Product** → **StorageLocation** |
| `plants` | **Plant** | `plant`, `plantName`, … | — |
| `product_descriptions` | *(optional)* **Product** extra props or **ProductDescription** node | language, text | Link by `product` id (watch ID mismatches across files) |

---

## Derived edge (materialized for broken-flow + LLM clarity)

| Relationship | Rule |
|--------------|------|
| **BILLED_BY** (`SalesOrderItem` → `InvoiceItem`) | **After** all `FULFILLED_BY` and `INVOICED_AS` edges exist: `MATCH (soi)-[:FULFILLED_BY]->(di)-[:INVOICED_AS]->(ii) MERGE (soi)-[:BILLED_BY]->(ii)`. One edge per reachable pair; idempotent. Scripted in `cypher/02_derived_billed_by.cypher`. |

**Reasoning:** JSONL does not expose a direct SO-item → invoice-item FK. The only faithful links are SO-item → delivery-item and delivery-item → invoice-item. Storing **BILLED_BY** explicitly encodes that derivation so queries like “order lines never billed” are a single `WHERE NOT (soi)-[:BILLED_BY]->()` instead of a variable-length pattern, and prompts can name a real relationship type.

---

## Finance: cancellation

| Source | Relationship |
|--------|----------------|
| `cancelledBillingDocument` on header or rows in `billing_document_cancellations` | **CANCELLED_BY**: `(original:Invoice)-[:CANCELLED_BY]->(cancelling:Invoice)` when both billing numbers exist; else store only flags on **Invoice**. |

---

## MCP data model artifact

Machine-readable schema (same v1): `resources/neo4j/o2c_data_model.json`  
Validated with **mcp-data-modeling** `validate_data_model` (returns valid for this graph).
