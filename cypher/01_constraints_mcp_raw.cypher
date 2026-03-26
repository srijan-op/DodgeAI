// Raw output from mcp-data-modeling tool get_constraints_cypher_queries (single-line).
// If your Neo4j edition accepts NODE KEY syntax for single properties, you may use this variant.

CREATE CONSTRAINT Customer_constraint IF NOT EXISTS FOR (n:Customer) REQUIRE (n.businessPartner) IS NODE KEY;
CREATE CONSTRAINT Address_constraint IF NOT EXISTS FOR (n:Address) REQUIRE (n.addressKey) IS NODE KEY;
CREATE CONSTRAINT CompanyCode_constraint IF NOT EXISTS FOR (n:CompanyCode) REQUIRE (n.companyCode) IS NODE KEY;
CREATE CONSTRAINT SalesArea_constraint IF NOT EXISTS FOR (n:SalesArea) REQUIRE (n.salesAreaKey) IS NODE KEY;
CREATE CONSTRAINT SalesOrder_constraint IF NOT EXISTS FOR (n:SalesOrder) REQUIRE (n.salesOrder) IS NODE KEY;
CREATE CONSTRAINT SalesOrderItem_constraint IF NOT EXISTS FOR (n:SalesOrderItem) REQUIRE (n.salesOrderItemKey) IS NODE KEY;
CREATE CONSTRAINT ScheduleLine_constraint IF NOT EXISTS FOR (n:ScheduleLine) REQUIRE (n.scheduleLineKey) IS NODE KEY;
CREATE CONSTRAINT Delivery_constraint IF NOT EXISTS FOR (n:Delivery) REQUIRE (n.deliveryDocument) IS NODE KEY;
CREATE CONSTRAINT DeliveryItem_constraint IF NOT EXISTS FOR (n:DeliveryItem) REQUIRE (n.deliveryItemKey) IS NODE KEY;
CREATE CONSTRAINT Invoice_constraint IF NOT EXISTS FOR (n:Invoice) REQUIRE (n.billingDocument) IS NODE KEY;
CREATE CONSTRAINT InvoiceItem_constraint IF NOT EXISTS FOR (n:InvoiceItem) REQUIRE (n.invoiceItemKey) IS NODE KEY;
CREATE CONSTRAINT JournalEntry_constraint IF NOT EXISTS FOR (n:JournalEntry) REQUIRE (n.journalLineKey) IS NODE KEY;
CREATE CONSTRAINT Payment_constraint IF NOT EXISTS FOR (n:Payment) REQUIRE (n.paymentKey) IS NODE KEY;
CREATE CONSTRAINT Product_constraint IF NOT EXISTS FOR (n:Product) REQUIRE (n.product) IS NODE KEY;
CREATE CONSTRAINT Plant_constraint IF NOT EXISTS FOR (n:Plant) REQUIRE (n.plant) IS NODE KEY;
CREATE CONSTRAINT StorageLocation_constraint IF NOT EXISTS FOR (n:StorageLocation) REQUIRE (n.storageLocationKey) IS NODE KEY;
