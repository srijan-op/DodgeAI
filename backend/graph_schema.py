"""
Maps Neo4j labels to their unique business-key property (matches ingestion keys).
Used for stable node `id` in API responses and for expand lookups.
"""

from typing import Final

# Label -> property name holding the canonical id string
LABEL_KEY_PROPERTY: Final[dict[str, str]] = {
    "Customer": "businessPartner",
    "Address": "addressKey",
    "CompanyCode": "companyCode",
    "SalesArea": "salesAreaKey",
    "SalesOrder": "salesOrder",
    "SalesOrderItem": "salesOrderItemKey",
    "ScheduleLine": "scheduleLineKey",
    "Delivery": "deliveryDocument",
    "DeliveryItem": "deliveryItemKey",
    "Invoice": "billingDocument",
    "InvoiceItem": "invoiceItemKey",
    "JournalEntry": "journalLineKey",
    "Payment": "paymentKey",
    "Product": "product",
    "Plant": "plant",
    "StorageLocation": "storageLocationKey",
}

ALLOWED_EXPAND_LABELS: Final[frozenset[str]] = frozenset(LABEL_KEY_PROPERTY.keys())

# Relationship types excluded from default full graph (dense supply-chain mesh)
DENSE_REL_TYPES: Final[frozenset[str]] = frozenset({"STORED_AT", "AVAILABLE_AT"})
