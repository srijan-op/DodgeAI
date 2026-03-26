// Neo4j 5.x uniqueness constraints for O2C v1 model.
// Generated from mcp-data-modeling get_constraints_cypher_queries; adapted to
// REQUIRE ... IS UNIQUE (single-property) for Neo4j 5.18 Community.

CREATE CONSTRAINT customer_bp IF NOT EXISTS
FOR (c:Customer) REQUIRE c.businessPartner IS UNIQUE;

CREATE CONSTRAINT address_key IF NOT EXISTS
FOR (a:Address) REQUIRE a.addressKey IS UNIQUE;

CREATE CONSTRAINT company_code IF NOT EXISTS
FOR (cc:CompanyCode) REQUIRE cc.companyCode IS UNIQUE;

CREATE CONSTRAINT sales_area_key IF NOT EXISTS
FOR (sa:SalesArea) REQUIRE sa.salesAreaKey IS UNIQUE;

CREATE CONSTRAINT sales_order IF NOT EXISTS
FOR (so:SalesOrder) REQUIRE so.salesOrder IS UNIQUE;

CREATE CONSTRAINT sales_order_item_key IF NOT EXISTS
FOR (soi:SalesOrderItem) REQUIRE soi.salesOrderItemKey IS UNIQUE;

CREATE CONSTRAINT schedule_line_key IF NOT EXISTS
FOR (sl:ScheduleLine) REQUIRE sl.scheduleLineKey IS UNIQUE;

CREATE CONSTRAINT delivery_doc IF NOT EXISTS
FOR (d:Delivery) REQUIRE d.deliveryDocument IS UNIQUE;

CREATE CONSTRAINT delivery_item_key IF NOT EXISTS
FOR (di:DeliveryItem) REQUIRE di.deliveryItemKey IS UNIQUE;

CREATE CONSTRAINT billing_doc IF NOT EXISTS
FOR (inv:Invoice) REQUIRE inv.billingDocument IS UNIQUE;

CREATE CONSTRAINT invoice_item_key IF NOT EXISTS
FOR (ii:InvoiceItem) REQUIRE ii.invoiceItemKey IS UNIQUE;

CREATE CONSTRAINT journal_line_key IF NOT EXISTS
FOR (je:JournalEntry) REQUIRE je.journalLineKey IS UNIQUE;

CREATE CONSTRAINT payment_key IF NOT EXISTS
FOR (p:Payment) REQUIRE p.paymentKey IS UNIQUE;

CREATE CONSTRAINT product_id IF NOT EXISTS
FOR (pr:Product) REQUIRE pr.product IS UNIQUE;

CREATE CONSTRAINT plant_id IF NOT EXISTS
FOR (pl:Plant) REQUIRE pl.plant IS UNIQUE;

CREATE CONSTRAINT storage_location_key IF NOT EXISTS
FOR (sloc:StorageLocation) REQUIRE sloc.storageLocationKey IS UNIQUE;
