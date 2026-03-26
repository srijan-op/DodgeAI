# SAP O2C Context Graph — data model (Mermaid)

Generated from [`o2c_data_model.json`](o2c_data_model.json) using the Neo4j data modeling MCP tool `get_mermaid_config_str`. Node colours follow the project O2C reference ERD palette (customer purple, order green, logistics blue/yellow, finance pink/cyan, master data teal/orange).

```mermaid
graph TD
%% Nodes
Customer["Customer<br/>businessPartner: STRING | KEY<br/>businessPartnerName: STRING<br/>businessPartnerIsBlocked: BOOLEAN"]
Address["Address<br/>addressKey: STRING | KEY<br/>cityName: STRING<br/>country: STRING<br/>region: STRING<br/>streetName: STRING<br/>postalCode: STRING"]
CompanyCode["CompanyCode<br/>companyCode: STRING | KEY"]
SalesArea["SalesArea<br/>salesAreaKey: STRING | KEY<br/>salesOrganization: STRING<br/>distributionChannel: STRING<br/>division: STRING"]
SalesOrder["SalesOrder<br/>salesOrder: STRING | KEY<br/>totalNetAmount: STRING<br/>transactionCurrency: STRING<br/>salesOrganization: STRING<br/>distributionChannel: STRING<br/>organizationDivision: STRING"]
SalesOrderItem["SalesOrderItem<br/>salesOrderItemKey: STRING | KEY<br/>salesOrder: STRING<br/>salesOrderItem: STRING<br/>material: STRING<br/>requestedQuantity: STRING<br/>netAmount: STRING<br/>productionPlant: STRING<br/>storageLocation: STRING"]
ScheduleLine["ScheduleLine<br/>scheduleLineKey: STRING | KEY<br/>confirmedDeliveryDate: DATE<br/>confdOrderQtyByMatlAvailCheck: STRING"]
Delivery["Delivery<br/>deliveryDocument: STRING | KEY<br/>shippingPoint: STRING<br/>creationDate: DATE"]
DeliveryItem["DeliveryItem<br/>deliveryItemKey: STRING | KEY<br/>deliveryDocument: STRING<br/>deliveryDocumentItem: STRING<br/>actualDeliveryQuantity: STRING<br/>plant: STRING<br/>storageLocation: STRING<br/>referenceSdDocument: STRING<br/>referenceSdDocumentItem: STRING"]
Invoice["Invoice<br/>billingDocument: STRING | KEY<br/>totalNetAmount: STRING<br/>transactionCurrency: STRING<br/>companyCode: STRING<br/>fiscalYear: STRING<br/>accountingDocument: STRING<br/>soldToParty: STRING<br/>billingDocumentIsCancelled: BOOLEAN<br/>cancelledBillingDocument: STRING"]
InvoiceItem["InvoiceItem<br/>invoiceItemKey: STRING | KEY<br/>billingDocument: STRING<br/>billingDocumentItem: STRING<br/>material: STRING<br/>netAmount: STRING<br/>referenceSdDocument: STRING<br/>referenceSdDocumentItem: STRING"]
JournalEntry["JournalEntry<br/>journalLineKey: STRING | KEY<br/>referenceDocument: STRING<br/>glAccount: STRING<br/>amountInTransactionCurrency: STRING<br/>transactionCurrency: STRING<br/>clearingAccountingDocument: STRING<br/>clearingDocFiscalYear: STRING<br/>customer: STRING<br/>postingDate: DATE"]
Payment["Payment<br/>paymentKey: STRING | KEY"]
Product["Product<br/>product: STRING | KEY<br/>productType: STRING<br/>productGroup: STRING"]
Plant["Plant<br/>plant: STRING | KEY<br/>plantName: STRING"]
StorageLocation["StorageLocation<br/>storageLocationKey: STRING | KEY"]

%% Relationships
Customer -->|PLACED| SalesOrder
SalesOrder -->|HAS_ITEM| SalesOrderItem
SalesOrderItem -->|FULFILLED_BY| DeliveryItem
DeliveryItem -->|PART_OF| Delivery
DeliveryItem -->|INVOICED_AS| InvoiceItem
SalesOrderItem -->|BILLED_BY| InvoiceItem
InvoiceItem -->|PART_OF| Invoice
Invoice -->|POSTED_AS| JournalEntry
JournalEntry -->|CLEARED_BY| Payment
Payment -->|MADE_BY| Customer
SalesOrderItem -->|REFERENCES| Product
InvoiceItem -->|REFERENCES| Product
SalesOrderItem -->|PRODUCED_AT| Plant
DeliveryItem -->|SHIPPED_FROM| Plant
Product -->|AVAILABLE_AT| Plant
Product -->|STORED_AT| StorageLocation
Customer -->|HAS_ADDRESS| Address
Customer -->|ASSIGNED_TO| CompanyCode
Customer -->|IN_SALES_AREA| SalesArea
SalesOrderItem -->|HAS_SCHEDULE| ScheduleLine
Invoice -->|CANCELLED_BY| Invoice

%% Styling — palette aligned with O2C reference ERD (distinct fills + strong strokes)
classDef customerStyle fill:#E1BEE7,stroke:#4A148C,stroke-width:3px,color:#1a1a1a,font-size:12px
classDef addressStyle fill:#B2DFDB,stroke:#00695C,stroke-width:3px,color:#1a1a1a,font-size:12px
classDef companyStyle fill:#FFE0B2,stroke:#E65100,stroke-width:3px,color:#1a1a1a,font-size:12px
classDef salesAreaStyle fill:#B3E5FC,stroke:#0277BD,stroke-width:3px,color:#1a1a1a,font-size:12px
classDef salesOrderStyle fill:#A5D6A7,stroke:#1B5E20,stroke-width:3px,color:#1a1a1a,font-size:12px
classDef salesOrderItemStyle fill:#D1C4E9,stroke:#4527A0,stroke-width:3px,color:#1a1a1a,font-size:12px
classDef scheduleStyle fill:#F48FB1,stroke:#AD1457,stroke-width:3px,color:#1a1a1a,font-size:12px
classDef deliveryStyle fill:#FFF59D,stroke:#F57F17,stroke-width:3px,color:#1a1a1a,font-size:12px
classDef deliveryItemStyle fill:#90CAF9,stroke:#0D47A1,stroke-width:3px,color:#1a1a1a,font-size:12px
classDef invoiceStyle fill:#C5E1A5,stroke:#33691E,stroke-width:3px,color:#1a1a1a,font-size:12px
classDef invoiceItemStyle fill:#80DEEA,stroke:#006064,stroke-width:3px,color:#1a1a1a,font-size:12px
classDef journalStyle fill:#F8BBD0,stroke:#C2185B,stroke-width:3px,color:#1a1a1a,font-size:12px
classDef paymentStyle fill:#E6CEFF,stroke:#6A1B9A,stroke-width:3px,color:#1a1a1a,font-size:12px
classDef productStyle fill:#80CBC4,stroke:#004D40,stroke-width:3px,color:#1a1a1a,font-size:12px
classDef plantStyle fill:#FFCC80,stroke:#EF6C00,stroke-width:3px,color:#1a1a1a,font-size:12px
classDef storageStyle fill:#E3F2FD,stroke:#1565C0,stroke-width:3px,color:#1a1a1a,font-size:12px

class Customer customerStyle
class Address addressStyle
class CompanyCode companyStyle
class SalesArea salesAreaStyle
class SalesOrder salesOrderStyle
class SalesOrderItem salesOrderItemStyle
class ScheduleLine scheduleStyle
class Delivery deliveryStyle
class DeliveryItem deliveryItemStyle
class Invoice invoiceStyle
class InvoiceItem invoiceItemStyle
class JournalEntry journalStyle
class Payment paymentStyle
class Product productStyle
class Plant plantStyle
class StorageLocation storageStyle
```

To regenerate the **graph structure** after editing the JSON model, call MCP **`user-mcp-data-modeling`** → **`get_mermaid_config_str`** with `data_model` set to the contents of `o2c_data_model.json`, then re-apply the `%% Styling` block above (MCP output uses generic colours).
