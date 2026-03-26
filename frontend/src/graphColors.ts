import type { GraphNode } from "./api";

/** 3D graph node colors — single source for GraphView + legend. */
export const GRAPH_VIEW_COLORS = {
  selected: "#38bdf8",
  highlight: "#ef4444",
  customer: "#60a5fa",
  salesOrder: "#a78bfa",
  salesOrderItem: "#94a3b8",
  invoice: "#fbbf24",
  delivery: "#34d399",
  product: "#f97316",
  default: "#7dd3fc",
} as const;

/** Toolbar legend rows (order matches user-facing list). */
export const GRAPH_COLOR_LEGEND = [
  { swatch: GRAPH_VIEW_COLORS.customer, colorName: "Blue", description: "Customer" },
  { swatch: GRAPH_VIEW_COLORS.salesOrder, colorName: "Purple", description: "Order" },
  { swatch: GRAPH_VIEW_COLORS.delivery, colorName: "Green", description: "Delivery" },
  { swatch: GRAPH_VIEW_COLORS.invoice, colorName: "Yellow", description: "Invoice" },
  { swatch: GRAPH_VIEW_COLORS.product, colorName: "Orange", description: "Product" },
  { swatch: GRAPH_VIEW_COLORS.highlight, colorName: "Red", description: "Highlight" },
  { swatch: GRAPH_VIEW_COLORS.selected, colorName: "Cyan", description: "Selected" },
  { swatch: "#f472b6", colorName: "Pink", description: "Path" },
] as const;

export function nodePaintColor(
  n: GraphNode,
  highlightIds: Set<string>,
  selectedId: string | null
): string {
  const id = n.id;
  if (selectedId === id) return GRAPH_VIEW_COLORS.selected;
  if (highlightIds.has(id)) return GRAPH_VIEW_COLORS.highlight;
  const label = n.labels[0] ?? "";
  if (label === "Customer") return GRAPH_VIEW_COLORS.customer;
  if (label === "SalesOrder") return GRAPH_VIEW_COLORS.salesOrder;
  if (label === "SalesOrderItem") return GRAPH_VIEW_COLORS.salesOrderItem;
  if (label === "Invoice" || label === "InvoiceItem") return GRAPH_VIEW_COLORS.invoice;
  if (label === "Delivery" || label === "DeliveryItem") return GRAPH_VIEW_COLORS.delivery;
  if (label === "Product") return GRAPH_VIEW_COLORS.product;
  return GRAPH_VIEW_COLORS.default;
}
