/** Types aligned with FastAPI /api/graph and chat SSE. */

export type GraphNode = {
  id: string;
  labels: string[];
  properties: Record<string, unknown>;
};

export type GraphEdge = {
  id: string;
  type: string;
  source: string;
  target: string;
  properties: Record<string, unknown>;
};

export type GraphPayload = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  stats: { nodes: number; edges: number };
};

export type ChatPlan = {
  run_analyze_flow: boolean;
  run_graph_query: boolean;
  analyze_flow_prompt: string | null;
  graph_query_prompt: string | null;
};

export type SseEvent =
  | { type: "meta"; session_id: string }
  | { type: "plan"; plan: ChatPlan }
  | { type: "graph_highlight"; node_ids: string[] }
  | { type: "token"; delta: string }
  | { type: "done" }
  | { type: "error"; detail: string };

const defaultBase = "";

export function apiUrl(path: string): string {
  const base = (import.meta.env.VITE_API_BASE || defaultBase).replace(/\/$/, "");
  return `${base}${path.startsWith("/") ? path : `/${path}`}`;
}

export async function fetchGraph(limitRows = 500): Promise<GraphPayload> {
  const r = await fetch(apiUrl(`/api/graph?limit_rows=${limitRows}`));
  if (!r.ok) throw new Error(`Graph load failed: ${r.status}`);
  return r.json();
}

/** API node ids are `Label:businessKey` (see backend serializers). */
export function parseNodeId(id: string): { label: string; key: string } | null {
  const i = id.indexOf(":");
  if (i <= 0 || i === id.length - 1) return null;
  return { label: id.slice(0, i), key: id.slice(i + 1) };
}

export async function expandNode(
  label: string,
  key: string,
  limit = 80
): Promise<GraphPayload> {
  const path = `/api/nodes/${encodeURIComponent(label)}/${encodeURIComponent(key)}/expand?limit=${limit}`;
  const r = await fetch(apiUrl(path));
  if (!r.ok) {
    const text = await r.text();
    throw new Error(text || `Expand failed: ${r.status}`);
  }
  return r.json();
}

export type ShortestPathResponse = GraphPayload & {
  path_edge_ids: string[];
  path_node_ids: string[];
};

export type O2cAnalyticsPayload = {
  generated_at: string;
  note: string;
  label_counts: Record<string, number>;
  integrity_checks: Array<{
    id: string;
    title: string;
    count: number;
    sample_node_ids: string[];
  }>;
  order_volume_buckets: Array<{ bucket: string; customers: number }>;
  top_customers_by_orders: Array<{ node_id: string; orders: number }>;
  product_plant_connectivity: {
    products_with_plant_link: number;
    distinct_plants: number;
    available_at_relationships: number;
  };
};

export async function fetchO2cAnalytics(sampleLimit = 20): Promise<O2cAnalyticsPayload> {
  const r = await fetch(apiUrl(`/api/analytics/o2c?sample_limit=${sampleLimit}`));
  if (!r.ok) {
    const text = await r.text();
    let msg = text;
    try {
      const j = JSON.parse(text) as { detail?: unknown };
      const d = j.detail;
      msg = typeof d === "string" ? d : JSON.stringify(d);
    } catch {
      /* keep */
    }
    throw new Error(msg || `Analytics failed: ${r.status}`);
  }
  return r.json();
}

export async function fetchShortestPath(
  fromId: string,
  toId: string,
  maxHops = 8
): Promise<ShortestPathResponse> {
  const r = await fetch(apiUrl("/api/path/shortest"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ from_id: fromId, to_id: toId, max_hops: maxHops }),
  });
  if (!r.ok) {
    const text = await r.text();
    let msg = text;
    try {
      const j = JSON.parse(text) as { detail?: string };
      if (j.detail) msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {
      /* keep */
    }
    throw new Error(msg || `Path failed: ${r.status}`);
  }
  return r.json();
}

/** Merge two graph payloads (dedupe nodes by id, edges by id). */
export function mergeGraphPayload(a: GraphPayload, b: GraphPayload): GraphPayload {
  const nodeMap = new Map(a.nodes.map((n) => [n.id, n]));
  for (const n of b.nodes) nodeMap.set(n.id, n);
  const edgeMap = new Map<string, GraphEdge>();
  for (const e of a.edges) edgeMap.set(e.id, e);
  for (const e of b.edges) edgeMap.set(e.id, e);
  const nodes = [...nodeMap.values()];
  const edges = [...edgeMap.values()];
  return {
    nodes,
    edges,
    stats: { nodes: nodes.length, edges: edges.length },
  };
}

function parseSseBlock(block: string): SseEvent | null {
  const line = block.split("\n").find((l) => l.startsWith("data: "));
  if (!line) return null;
  try {
    return JSON.parse(line.slice(6).trim()) as SseEvent;
  } catch {
    return null;
  }
}

export async function streamChat(
  message: string,
  sessionId: string,
  onEvent: (ev: SseEvent) => void
): Promise<void> {
  const r = await fetch(apiUrl("/api/chat"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId }),
  });
  if (!r.ok) {
    const text = await r.text();
    let detail = text;
    try {
      const j = JSON.parse(text) as { detail?: string };
      if (j.detail) detail = j.detail;
    } catch {
      /* keep text */
    }
    throw new Error(detail || `Chat failed: ${r.status}`);
  }
  if (!r.body) throw new Error("No response body");
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const parts = buf.split("\n\n");
    buf = parts.pop() ?? "";
    for (const part of parts) {
      const ev = parseSseBlock(part.trim());
      if (ev) onEvent(ev);
    }
  }
  const tail = buf.trim();
  if (tail) {
    const ev = parseSseBlock(tail);
    if (ev) onEvent(ev);
  }
}
