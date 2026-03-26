import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

from neo4j import GraphDatabase


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "sap-o2c-data"


def parse_env(path: Path) -> Dict[str, str]:
    env: Dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        env[key.strip()] = val.strip()
    return env


def norm_item(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    if not s:
        return ""
    if s.isdigit():
        s = s.lstrip("0")
        return s if s else "0"
    return s


def sanitize_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        if all(isinstance(x, (str, int, float, bool)) or x is None for x in value):
            return value
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def sanitize_props(props: Dict[str, Any]) -> Dict[str, Any]:
    return {k: sanitize_value(v) for k, v in props.items()}


def jsonl_rows(folder: str) -> Iterable[Dict[str, Any]]:
    target = DATA_DIR / folder
    for file in sorted(target.glob("*.jsonl")):
        with file.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    yield json.loads(line)


def chunked(rows: List[Dict[str, Any]], size: int) -> Iterable[List[Dict[str, Any]]]:
    for i in range(0, len(rows), size):
        yield rows[i : i + size]


def execute_batches(driver, query: str, rows: List[Dict[str, Any]], batch_size: int = 1000) -> int:
    total = 0
    for batch in chunked(rows, batch_size):
        with driver.session() as session:
            session.run(query, rows=batch).consume()
        total += len(batch)
    return total


Q_CREATE_COMPANY_CODE = """
UNWIND $rows AS row
MERGE (cc:CompanyCode {companyCode: row.companyCode})
"""

Q_CREATE_SALES_AREA = """
UNWIND $rows AS row
MERGE (sa:SalesArea {salesAreaKey: row.salesAreaKey})
SET sa.salesOrganization = row.salesOrganization,
    sa.distributionChannel = row.distributionChannel,
    sa.division = row.division
"""

Q_CREATE_PLANT = """
UNWIND $rows AS row
MERGE (p:Plant {plant: row.plant})
SET p += row.props
"""

Q_CREATE_PRODUCT = """
UNWIND $rows AS row
MERGE (p:Product {product: row.product})
SET p += row.props
"""

Q_CREATE_STORAGE = """
UNWIND $rows AS row
MERGE (sl:StorageLocation {storageLocationKey: row.storageLocationKey})
SET sl.plant = row.plant, sl.storageLocation = row.storageLocation
"""

Q_CREATE_CUSTOMER = """
UNWIND $rows AS row
MERGE (c:Customer {businessPartner: row.businessPartner})
SET c += row.props
"""

Q_CREATE_ADDRESS_AND_REL = """
UNWIND $rows AS row
MERGE (a:Address {addressKey: row.addressKey})
SET a += row.props
WITH row, a
MATCH (c:Customer {businessPartner: row.businessPartner})
MERGE (c)-[:HAS_ADDRESS]->(a)
"""

Q_ASSIGN_COMPANY = """
UNWIND $rows AS row
MATCH (c:Customer {businessPartner: row.customer})
MATCH (cc:CompanyCode {companyCode: row.companyCode})
MERGE (c)-[:ASSIGNED_TO]->(cc)
"""

Q_ASSIGN_SALES_AREA = """
UNWIND $rows AS row
MATCH (c:Customer {businessPartner: row.customer})
MATCH (sa:SalesArea {salesAreaKey: row.salesAreaKey})
MERGE (c)-[:IN_SALES_AREA]->(sa)
"""

Q_AVAILABLE_AT = """
UNWIND $rows AS row
MATCH (p:Product {product: row.product})
MATCH (pl:Plant {plant: row.plant})
MERGE (p)-[:AVAILABLE_AT]->(pl)
"""

Q_STORED_AT = """
UNWIND $rows AS row
MATCH (p:Product {product: row.product})
MATCH (sl:StorageLocation {storageLocationKey: row.storageLocationKey})
MERGE (p)-[:STORED_AT]->(sl)
"""

Q_CREATE_SALES_ORDER = """
UNWIND $rows AS row
MERGE (so:SalesOrder {salesOrder: row.salesOrder})
SET so += row.props
WITH row, so
OPTIONAL MATCH (c:Customer {businessPartner: row.soldToParty})
FOREACH (_ IN CASE WHEN c IS NULL THEN [] ELSE [1] END |
  MERGE (c)-[:PLACED]->(so)
)
"""

Q_CREATE_SALES_ORDER_ITEM = """
UNWIND $rows AS row
MERGE (soi:SalesOrderItem {salesOrderItemKey: row.salesOrderItemKey})
SET soi += row.props
WITH row, soi
MATCH (so:SalesOrder {salesOrder: row.salesOrder})
MERGE (so)-[:HAS_ITEM]->(soi)
WITH row, soi
OPTIONAL MATCH (p:Product {product: row.material})
FOREACH (_ IN CASE WHEN p IS NULL THEN [] ELSE [1] END |
  MERGE (soi)-[:REFERENCES]->(p)
)
WITH row, soi
OPTIONAL MATCH (pl:Plant {plant: row.productionPlant})
FOREACH (_ IN CASE WHEN pl IS NULL THEN [] ELSE [1] END |
  MERGE (soi)-[:PRODUCED_AT]->(pl)
)
"""

Q_CREATE_SCHEDULE = """
UNWIND $rows AS row
MERGE (sl:ScheduleLine {scheduleLineKey: row.scheduleLineKey})
SET sl += row.props
WITH row, sl
MATCH (soi:SalesOrderItem {salesOrderItemKey: row.salesOrderItemKey})
MERGE (soi)-[:HAS_SCHEDULE]->(sl)
"""

Q_CREATE_DELIVERY = """
UNWIND $rows AS row
MERGE (d:Delivery {deliveryDocument: row.deliveryDocument})
SET d += row.props
"""

Q_CREATE_DELIVERY_ITEM = """
UNWIND $rows AS row
MERGE (di:DeliveryItem {deliveryItemKey: row.deliveryItemKey})
SET di += row.props
WITH row, di
MATCH (d:Delivery {deliveryDocument: row.deliveryDocument})
MERGE (di)-[:PART_OF]->(d)
WITH row, di
OPTIONAL MATCH (soi:SalesOrderItem {salesOrderItemKey: row.salesOrderItemRefKey})
FOREACH (_ IN CASE WHEN soi IS NULL THEN [] ELSE [1] END |
  MERGE (soi)-[:FULFILLED_BY]->(di)
)
WITH row, di
OPTIONAL MATCH (pl:Plant {plant: row.plant})
FOREACH (_ IN CASE WHEN pl IS NULL THEN [] ELSE [1] END |
  MERGE (di)-[:SHIPPED_FROM]->(pl)
)
"""

Q_CREATE_INVOICE = """
UNWIND $rows AS row
MERGE (i:Invoice {billingDocument: row.billingDocument})
SET i += row.props
"""

Q_CREATE_INVOICE_ITEM = """
UNWIND $rows AS row
MERGE (ii:InvoiceItem {invoiceItemKey: row.invoiceItemKey})
SET ii += row.props
WITH row, ii
MATCH (i:Invoice {billingDocument: row.billingDocument})
MERGE (ii)-[:PART_OF]->(i)
WITH row, ii
OPTIONAL MATCH (di:DeliveryItem {deliveryItemKey: row.deliveryItemRefKey})
FOREACH (_ IN CASE WHEN di IS NULL THEN [] ELSE [1] END |
  MERGE (di)-[:INVOICED_AS]->(ii)
)
WITH row, ii
OPTIONAL MATCH (p:Product {product: row.material})
FOREACH (_ IN CASE WHEN p IS NULL THEN [] ELSE [1] END |
  MERGE (ii)-[:REFERENCES]->(p)
)
"""

Q_CREATE_JOURNAL = """
UNWIND $rows AS row
MERGE (je:JournalEntry {journalLineKey: row.journalLineKey})
SET je += row.props
"""

Q_CREATE_POSTED_AS = """
UNWIND $rows AS row
MATCH (i:Invoice {billingDocument: row.billingDocument})
MATCH (je:JournalEntry {journalLineKey: row.journalLineKey})
MERGE (i)-[:POSTED_AS]->(je)
"""

Q_CREATE_PAYMENT = """
UNWIND $rows AS row
MERGE (p:Payment {paymentKey: row.paymentKey})
"""

Q_CREATE_CLEARED = """
UNWIND $rows AS row
MATCH (je:JournalEntry {journalLineKey: row.journalLineKey})
MATCH (p:Payment {paymentKey: row.paymentKey})
MERGE (je)-[:CLEARED_BY]->(p)
"""

Q_CREATE_MADE_BY = """
UNWIND $rows AS row
MATCH (p:Payment {paymentKey: row.paymentKey})
MATCH (c:Customer {businessPartner: row.customer})
MERGE (p)-[:MADE_BY]->(c)
"""

Q_CREATE_CANCELLED_BY = """
UNWIND $rows AS row
MATCH (orig:Invoice {billingDocument: row.cancelledBillingDocument})
MATCH (cn:Invoice {billingDocument: row.billingDocument})
MERGE (orig)-[:CANCELLED_BY]->(cn)
"""


def prepare_rows() -> Dict[str, List[Dict[str, Any]]]:
    rows: Dict[str, List[Dict[str, Any]]] = {}

    company_codes = set()
    for folder, field in [
        ("customer_company_assignments", "companyCode"),
        ("billing_document_headers", "companyCode"),
        ("billing_document_cancellations", "companyCode"),
        ("journal_entry_items_accounts_receivable", "companyCode"),
        ("payments_accounts_receivable", "companyCode"),
    ]:
        for r in jsonl_rows(folder):
            val = r.get(field)
            if val:
                company_codes.add(val)
    rows["company_codes"] = [{"companyCode": x} for x in sorted(company_codes)]

    sales_areas = {}
    for r in jsonl_rows("customer_sales_area_assignments"):
        so = r.get("salesOrganization", "")
        dc = r.get("distributionChannel", "")
        dv = r.get("division", "")
        key = f"{so}|{dc}|{dv}"
        sales_areas[key] = {
            "salesAreaKey": key,
            "salesOrganization": so,
            "distributionChannel": dc,
            "division": dv,
        }
    rows["sales_areas"] = list(sales_areas.values())

    rows["plants"] = [{"plant": r["plant"], "props": sanitize_props(r)} for r in jsonl_rows("plants")]
    rows["products"] = [{"product": r["product"], "props": sanitize_props(r)} for r in jsonl_rows("products")]

    storage_map = {}
    for r in jsonl_rows("product_storage_locations"):
        key = f"{r.get('plant', '')}|{r.get('storageLocation', '')}"
        storage_map[key] = {
            "storageLocationKey": key,
            "plant": r.get("plant", ""),
            "storageLocation": r.get("storageLocation", ""),
        }
    rows["storage"] = list(storage_map.values())

    rows["customers"] = []
    for r in jsonl_rows("business_partners"):
        bp = r.get("businessPartner") or r.get("customer")
        if not bp:
            continue
        props = sanitize_props(dict(r))
        props["businessPartner"] = bp
        rows["customers"].append({"businessPartner": bp, "props": props})

    rows["addresses"] = []
    for r in jsonl_rows("business_partner_addresses"):
        bp = r.get("businessPartner", "")
        aid = r.get("addressId", "")
        key = f"{bp}|{aid}"
        props = sanitize_props(dict(r))
        props["addressKey"] = key
        rows["addresses"].append({"businessPartner": bp, "addressKey": key, "props": props})

    rows["assigned_company"] = [dict(r) for r in jsonl_rows("customer_company_assignments")]
    rows["in_sales_area"] = []
    for r in jsonl_rows("customer_sales_area_assignments"):
        r2 = dict(r)
        r2["salesAreaKey"] = f"{r.get('salesOrganization', '')}|{r.get('distributionChannel', '')}|{r.get('division', '')}"
        rows["in_sales_area"].append(r2)

    rows["available_at"] = [dict(r) for r in jsonl_rows("product_plants")]
    rows["stored_at"] = []
    for r in jsonl_rows("product_storage_locations"):
        rows["stored_at"].append(
            {
                "product": r.get("product", ""),
                "storageLocationKey": f"{r.get('plant', '')}|{r.get('storageLocation', '')}",
            }
        )

    rows["sales_orders"] = []
    for r in jsonl_rows("sales_order_headers"):
        rows["sales_orders"].append(
            {
                "salesOrder": r.get("salesOrder", ""),
                "soldToParty": r.get("soldToParty", ""),
                "props": sanitize_props(r),
            }
        )

    rows["sales_order_items"] = []
    for r in jsonl_rows("sales_order_items"):
        key = f"{r.get('salesOrder', '')}|{norm_item(r.get('salesOrderItem', ''))}"
        props = sanitize_props(dict(r))
        props["salesOrderItemKey"] = key
        rows["sales_order_items"].append(
            {
                "salesOrderItemKey": key,
                "salesOrder": r.get("salesOrder", ""),
                "material": r.get("material", ""),
                "productionPlant": r.get("productionPlant", ""),
                "props": props,
            }
        )

    rows["schedule_lines"] = []
    for r in jsonl_rows("sales_order_schedule_lines"):
        soi_key = f"{r.get('salesOrder', '')}|{norm_item(r.get('salesOrderItem', ''))}"
        key = f"{soi_key}|{r.get('scheduleLine', '')}"
        props = sanitize_props(dict(r))
        props["scheduleLineKey"] = key
        rows["schedule_lines"].append(
            {
                "scheduleLineKey": key,
                "salesOrderItemKey": soi_key,
                "props": props,
            }
        )

    rows["deliveries"] = [
        {"deliveryDocument": r.get("deliveryDocument", ""), "props": sanitize_props(r)}
        for r in jsonl_rows("outbound_delivery_headers")
    ]

    rows["delivery_items"] = []
    for r in jsonl_rows("outbound_delivery_items"):
        did_key = f"{r.get('deliveryDocument', '')}|{norm_item(r.get('deliveryDocumentItem', ''))}"
        soi_ref = f"{r.get('referenceSdDocument', '')}|{norm_item(r.get('referenceSdDocumentItem', ''))}"
        props = sanitize_props(dict(r))
        props["deliveryItemKey"] = did_key
        rows["delivery_items"].append(
            {
                "deliveryItemKey": did_key,
                "deliveryDocument": r.get("deliveryDocument", ""),
                "salesOrderItemRefKey": soi_ref,
                "plant": r.get("plant", ""),
                "props": props,
            }
        )

    rows["invoices"] = []
    for folder in ["billing_document_headers", "billing_document_cancellations"]:
        for r in jsonl_rows(folder):
            rows["invoices"].append(
                {"billingDocument": r.get("billingDocument", ""), "props": sanitize_props(r)}
            )

    rows["invoice_items"] = []
    for r in jsonl_rows("billing_document_items"):
        ii_key = f"{r.get('billingDocument', '')}|{norm_item(r.get('billingDocumentItem', ''))}"
        di_key = f"{r.get('referenceSdDocument', '')}|{norm_item(r.get('referenceSdDocumentItem', ''))}"
        props = sanitize_props(dict(r))
        props["invoiceItemKey"] = ii_key
        rows["invoice_items"].append(
            {
                "invoiceItemKey": ii_key,
                "billingDocument": r.get("billingDocument", ""),
                "deliveryItemRefKey": di_key,
                "material": r.get("material", ""),
                "props": props,
            }
        )

    rows["journal_entries"] = []
    for folder in ["journal_entry_items_accounts_receivable", "payments_accounts_receivable"]:
        for r in jsonl_rows(folder):
            k = f"{r.get('companyCode', '')}|{r.get('fiscalYear', '')}|{r.get('accountingDocument', '')}|{r.get('accountingDocumentItem', '')}"
            props = sanitize_props(dict(r))
            props["journalLineKey"] = k
            rows["journal_entries"].append({"journalLineKey": k, "props": props})

    rows["posted_as"] = []
    for r in jsonl_rows("billing_document_headers"):
        cc = r.get("companyCode", "")
        fy = r.get("fiscalYear", "")
        ad = r.get("accountingDocument", "")
        if cc and fy and ad:
            for jr in rows["journal_entries"]:
                jkey = jr["journalLineKey"]
                if jkey.startswith(f"{cc}|{fy}|{ad}|"):
                    rows["posted_as"].append(
                        {"billingDocument": r.get("billingDocument", ""), "journalLineKey": jkey}
                    )

    rows["payments"] = []
    rows["cleared_by"] = []
    rows["made_by"] = []
    payment_seen = set()
    made_seen = set()
    for jr in rows["journal_entries"]:
        p = jr["props"]
        cc = p.get("companyCode", "")
        cfy = p.get("clearingDocFiscalYear", "")
        cad = p.get("clearingAccountingDocument", "")
        customer = p.get("customer", "")
        if cad:
            pkey = f"{cc}|{cfy}|{cad}"
            if pkey not in payment_seen:
                payment_seen.add(pkey)
                rows["payments"].append({"paymentKey": pkey})
            rows["cleared_by"].append({"journalLineKey": jr["journalLineKey"], "paymentKey": pkey})
            if customer:
                mk = f"{pkey}|{customer}"
                if mk not in made_seen:
                    made_seen.add(mk)
                    rows["made_by"].append({"paymentKey": pkey, "customer": customer})

    rows["cancelled_by"] = []
    for r in rows["invoices"]:
        props = r["props"]
        if props.get("cancelledBillingDocument"):
            rows["cancelled_by"].append(
                {
                    "billingDocument": props.get("billingDocument", ""),
                    "cancelledBillingDocument": props.get("cancelledBillingDocument", ""),
                }
            )
    return rows


def run_all(driver, rows: Dict[str, List[Dict[str, Any]]]) -> None:
    def do(name: str, query: str, key: str) -> None:
        count = execute_batches(driver, query, rows[key])
        print(f"{name}: {count}")

    print("Phase A - masters")
    do("CompanyCode", Q_CREATE_COMPANY_CODE, "company_codes")
    do("SalesArea", Q_CREATE_SALES_AREA, "sales_areas")
    do("Plant", Q_CREATE_PLANT, "plants")
    do("Product", Q_CREATE_PRODUCT, "products")
    do("StorageLocation", Q_CREATE_STORAGE, "storage")
    do("Customer", Q_CREATE_CUSTOMER, "customers")
    do("Address + HAS_ADDRESS", Q_CREATE_ADDRESS_AND_REL, "addresses")

    print("Phase B - customer context")
    do("ASSIGNED_TO", Q_ASSIGN_COMPANY, "assigned_company")
    do("IN_SALES_AREA", Q_ASSIGN_SALES_AREA, "in_sales_area")

    print("Phase C - supply")
    do("AVAILABLE_AT", Q_AVAILABLE_AT, "available_at")
    do("STORED_AT", Q_STORED_AT, "stored_at")

    print("Phase D - operations")
    do("SalesOrder + PLACED", Q_CREATE_SALES_ORDER, "sales_orders")
    do("SalesOrderItem + rels", Q_CREATE_SALES_ORDER_ITEM, "sales_order_items")
    do("ScheduleLine + HAS_SCHEDULE", Q_CREATE_SCHEDULE, "schedule_lines")
    do("Delivery", Q_CREATE_DELIVERY, "deliveries")
    do("DeliveryItem + rels", Q_CREATE_DELIVERY_ITEM, "delivery_items")
    do("Invoice", Q_CREATE_INVOICE, "invoices")
    do("InvoiceItem + rels + INVOICED_AS", Q_CREATE_INVOICE_ITEM, "invoice_items")

    print("Phase E - accounting")
    do("JournalEntry", Q_CREATE_JOURNAL, "journal_entries")
    do("POSTED_AS", Q_CREATE_POSTED_AS, "posted_as")
    do("Payment", Q_CREATE_PAYMENT, "payments")
    do("CLEARED_BY", Q_CREATE_CLEARED, "cleared_by")
    do("MADE_BY", Q_CREATE_MADE_BY, "made_by")

    if rows["cancelled_by"]:
        do("CANCELLED_BY", Q_CREATE_CANCELLED_BY, "cancelled_by")
    else:
        print("CANCELLED_BY: 0 (no cancelledBillingDocument references)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest SAP O2C JSONL into Neo4j")
    parser.add_argument("--uri", default="bolt://localhost:7687")
    parser.add_argument("--user", default=None)
    parser.add_argument("--password", default=None)
    args = parser.parse_args()

    env = parse_env(BASE_DIR / ".env")
    user = args.user or env.get("NEO4J_USER", "neo4j")
    password = args.password or env.get("NEO4J_PASSWORD", "")

    if not password:
        raise ValueError("NEO4J_PASSWORD is empty")

    rows = prepare_rows()
    driver = GraphDatabase.driver(args.uri, auth=(user, password))
    try:
        run_all(driver, rows)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
