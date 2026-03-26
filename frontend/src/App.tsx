import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
} from "react";
import {
  apiUrl,
  expandNode,
  fetchGraph,
  fetchShortestPath,
  mergeGraphPayload,
  parseNodeId,
  type GraphEdge,
  type GraphNode,
  type ShortestPathResponse,
} from "./api";
import { AnalyticsPanel } from "./components/AnalyticsPanel";
import { GraphImportantNote } from "./components/GraphImportantNote";
import { GraphLegendMenu } from "./components/GraphLegendMenu";
import { GraphNodePopover } from "./components/GraphNodePopover";
import { buildGraphData, GraphView, type GraphData } from "./components/GraphView";
import { ChatPanel } from "./components/ChatPanel";
import "./App.css";

const CHAT_WIDTH_KEY = "dodgeai-chat-width";
const CHAT_WIDTH_MIN = 280;
const CHAT_WIDTH_MAX = 720;

function randomSessionId(): string {
  return `web-${Math.random().toString(36).slice(2, 11)}`;
}

function readStoredChatWidth(): number {
  try {
    const raw = localStorage.getItem(CHAT_WIDTH_KEY);
    if (!raw) return 380;
    const n = parseInt(raw, 10);
    if (Number.isNaN(n)) return 380;
    return Math.min(CHAT_WIDTH_MAX, Math.max(CHAT_WIDTH_MIN, n));
  } catch {
    return 380;
  }
}

function countLinksForNode(id: string, edges: GraphEdge[]): number {
  return edges.filter((e) => e.source === id || e.target === id).length;
}

function stripPathMeta(r: ShortestPathResponse): Parameters<typeof mergeGraphPayload>[1] {
  const { path_edge_ids: _e, path_node_ids: _n, ...g } = r;
  return g;
}

export default function App() {
  const [sessionId] = useState(randomSessionId);
  const [graphPayload, setGraphPayload] = useState<Awaited<ReturnType<typeof fetchGraph>> | null>(
    null
  );
  const [graphError, setGraphError] = useState<string | null>(null);
  const [loadingGraph, setLoadingGraph] = useState(true);
  const [highlightIds, setHighlightIds] = useState<Set<string>>(() => new Set());
  /** Path tool: red node highlights (separate from chat SSE highlights). */
  const [pathNodeHighlightIds, setPathNodeHighlightIds] = useState<Set<string>>(() => new Set());
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [metadataAnchor, setMetadataAnchor] = useState<{ x: number; y: number } | null>(null);
  const [minimized, setMinimized] = useState(false);
  const [hideOverlay, setHideOverlay] = useState(false);
  const [chatWidth, setChatWidth] = useState(readStoredChatWidth);
  const [expandBusy, setExpandBusy] = useState(false);
  const [expandError, setExpandError] = useState<string | null>(null);
  const [reheatKey, setReheatKey] = useState(0);
  const [pathPickPhase, setPathPickPhase] = useState<"off" | "first" | "second">("off");
  const [pathFirstNode, setPathFirstNode] = useState<GraphNode | null>(null);
  const [pathEdgeHighlightIds, setPathEdgeHighlightIds] = useState<Set<string>>(() => new Set());
  const [pathBusy, setPathBusy] = useState(false);
  const [pathError, setPathError] = useState<string | null>(null);
  const [analyticsOpen, setAnalyticsOpen] = useState(false);
  const dragRef = useRef<{ startX: number; startW: number } | null>(null);
  const chatWidthRef = useRef(chatWidth);
  chatWidthRef.current = chatWidth;
  const graphPayloadRef = useRef(graphPayload);
  graphPayloadRef.current = graphPayload;

  const graphData: GraphData | null = useMemo(() => {
    if (!graphPayload) return null;
    return buildGraphData(graphPayload.nodes, graphPayload.edges);
  }, [graphPayload]);

  const mergedHighlightIds = useMemo(() => {
    const m = new Set<string>();
    for (const id of highlightIds) m.add(id);
    for (const id of pathNodeHighlightIds) m.add(id);
    return m;
  }, [highlightIds, pathNodeHighlightIds]);

  const pathVisualActive = pathEdgeHighlightIds.size > 0 || pathNodeHighlightIds.size > 0;

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await fetchGraph(500);
        if (!cancelled) {
          setGraphPayload(data);
          setGraphError(null);
        }
      } catch (e) {
        if (!cancelled) {
          setGraphError(e instanceof Error ? e.message : "Failed to load graph");
        }
      } finally {
        if (!cancelled) setLoadingGraph(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const onGraphHighlight = useCallback((ids: string[]) => {
    setHighlightIds(new Set(ids));
  }, []);

  /** Expand analytics sample nodes into the viewport so force-graph can paint highlights. */
  const onAnalyticsHighlightSamples = useCallback(async (ids: string[]) => {
    const unique = [...new Set(ids)].filter(Boolean).slice(0, 40);
    let acc = graphPayloadRef.current;
    setExpandError(null);
    for (const id of unique) {
      const p = parseNodeId(id);
      if (!p) continue;
      try {
        const chunk = await expandNode(p.label, p.key, 90);
        acc = acc ? mergeGraphPayload(acc, chunk) : chunk;
      } catch {
        /* skip missing nodes / network errors */
      }
    }
    if (acc) {
      setGraphPayload(acc);
      graphPayloadRef.current = acc;
      setReheatKey((k) => k + 1);
    }
    setHighlightIds(new Set(ids));
  }, []);

  const mergeExpand = useCallback(async (nodeId: string) => {
    const parsed = parseNodeId(nodeId);
    if (!parsed) return;
    setExpandError(null);
    setExpandBusy(true);
    try {
      const chunk = await expandNode(parsed.label, parsed.key, 90);
      setGraphPayload((prev) => (prev ? mergeGraphPayload(prev, chunk) : chunk));
      setReheatKey((k) => k + 1);
    } catch (e) {
      setExpandError(e instanceof Error ? e.message : String(e));
    } finally {
      setExpandBusy(false);
    }
  }, []);

  const onNodeNavigate = useCallback(
    (node: GraphNode) => {
      void mergeExpand(node.id);
    },
    [mergeExpand]
  );

  const onLinkNavigate = useCallback(
    (sourceId: string, targetId: string) => {
      void (async () => {
        await mergeExpand(sourceId);
        await mergeExpand(targetId);
      })();
    },
    [mergeExpand]
  );

  const clearPathVisual = useCallback(() => {
    setPathEdgeHighlightIds(new Set());
    setPathNodeHighlightIds(new Set());
  }, []);

  const togglePathMode = useCallback(() => {
    if (pathPickPhase !== "off") {
      setPathPickPhase("off");
      setPathFirstNode(null);
      clearPathVisual();
      setPathError(null);
    } else {
      setPathPickPhase("first");
      setPathFirstNode(null);
      clearPathVisual();
      setPathError(null);
    }
  }, [pathPickPhase, clearPathVisual]);

  const onPathPickNode = useCallback(
    (node: GraphNode, step: 1 | 2) => {
      if (step === 1) {
        setPathFirstNode(node);
        setSelectedNode(node);
        setPathPickPhase("second");
        return;
      }
      const first = pathFirstNode;
      if (!first || first.id === node.id) {
        setPathError("Pick two different nodes.");
        return;
      }
      setPathBusy(true);
      setPathError(null);
      void (async () => {
        try {
          const res = await fetchShortestPath(first.id, node.id, 10);
          setGraphPayload((prev) => (prev ? mergeGraphPayload(prev, stripPathMeta(res)) : stripPathMeta(res)));
          setPathEdgeHighlightIds(new Set(res.path_edge_ids));
          setPathNodeHighlightIds(new Set(res.path_node_ids));
          setReheatKey((k) => k + 1);
          setSelectedNode(node);
          setPathPickPhase("off");
          setPathFirstNode(null);
        } catch (e) {
          setPathError(e instanceof Error ? e.message : String(e));
          setPathPickPhase("off");
          setPathFirstNode(null);
        } finally {
          setPathBusy(false);
        }
      })();
    },
    [pathFirstNode]
  );

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      const d = dragRef.current;
      if (!d) return;
      const dx = d.startX - e.clientX;
      const next = Math.min(CHAT_WIDTH_MAX, Math.max(CHAT_WIDTH_MIN, d.startW + dx));
      setChatWidth(next);
    };
    const onUp = () => {
      if (dragRef.current) {
        try {
          localStorage.setItem(CHAT_WIDTH_KEY, String(chatWidthRef.current));
        } catch {
          /* ignore */
        }
      }
      dragRef.current = null;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, []);

  const onResizePointerDown = useCallback((e: ReactMouseEvent<HTMLButtonElement>) => {
    e.preventDefault();
    dragRef.current = { startX: e.clientX, startW: chatWidth };
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }, [chatWidth]);

  const selectedLinks = graphPayload?.edges ?? [];

  const closePopover = useCallback(() => {
    setSelectedNode(null);
    setMetadataAnchor(null);
  }, []);

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-header-brand">
          <span className="app-header-title">Order to Cash</span>
          <span className="app-header-tag">Dodge AI</span>
        </div>
      </header>

      <main className="app-main">
        <section className="graph-column">
          <div className="graph-toolbar">
            <button
              type="button"
              className="toolbar-btn toolbar-btn-ghost"
              onClick={() => setMinimized((m) => !m)}
            >
              {minimized ? "Expand graph" : "Minimize"}
            </button>
            <button
              type="button"
              className={`toolbar-btn ${hideOverlay ? "toolbar-btn-ghost" : "toolbar-btn-accent"}`}
              onClick={() => setHideOverlay((h) => !h)}
            >
              {hideOverlay ? "Show granular overlay" : "Hide granular overlay"}
            </button>
            <GraphLegendMenu />
            <GraphImportantNote />
            <button
              type="button"
              className={`toolbar-btn ${analyticsOpen ? "toolbar-btn-accent" : "toolbar-btn-ghost"}`}
              onClick={() => setAnalyticsOpen(true)}
            >
              Analytics
            </button>
            <button
              type="button"
              className={`toolbar-btn ${pathPickPhase !== "off" ? "toolbar-btn-accent" : "toolbar-btn-ghost"}`}
              onClick={togglePathMode}
            >
              {pathPickPhase !== "off" ? "Cancel path" : "Find path"}
            </button>
            <button
              type="button"
              className="toolbar-btn toolbar-btn-ghost"
              disabled={!pathVisualActive}
              title={pathVisualActive ? "Remove path highlighting from the graph" : "No active path"}
              onClick={clearPathVisual}
            >
              Clear path
            </button>
            {pathPickPhase === "first" && (
              <span className="toolbar-status">Click first node…</span>
            )}
            {pathPickPhase === "second" && (
              <span className="toolbar-status">Click second node…</span>
            )}
            {pathBusy && <span className="toolbar-status">Finding path…</span>}
            {pathError && (
              <span className="toolbar-status toolbar-status-error" title={pathError}>
                Path failed
              </span>
            )}
            {expandBusy && <span className="toolbar-status">Loading neighbors…</span>}
            {expandError && (
              <span className="toolbar-status toolbar-status-error" title={expandError}>
                Expand failed — see tooltip
              </span>
            )}
          </div>

          <div className={`graph-shell ${minimized ? "graph-shell-minimized" : ""}`}>
            {loadingGraph && <div className="graph-overlay">Loading graph…</div>}
            {graphError && (
              <div className="graph-overlay graph-overlay-error">
                <p>{graphError}</p>
                <p className="hint">
                  Start the API: <code>uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000</code>
                </p>
                <p className="hint">
                  Running dev server with proxy: <code>npm run dev</code> (this shell loads{" "}
                  <code>{apiUrl("/api/graph")}</code>)
                </p>
              </div>
            )}
            {!loadingGraph && !graphError && graphData && (
              <>
                <GraphView
                  data={hideOverlay ? filterSalesOrderSpine(graphData) : graphData}
                  highlightIds={mergedHighlightIds}
                  selectedId={selectedNode?.id ?? null}
                  onSelectNode={setSelectedNode}
                  onNodeNavigate={onNodeNavigate}
                  onLinkNavigate={onLinkNavigate}
                  minimized={minimized}
                  reheatKey={reheatKey}
                  expandOnNodeClick={pathPickPhase === "off"}
                  pathPickPhase={pathPickPhase === "off" ? "off" : pathPickPhase === "first" ? "first" : "second"}
                  onPathPickNode={onPathPickNode}
                  pathHighlightEdgeIds={pathEdgeHighlightIds}
                  onSelectionScreenPos={setMetadataAnchor}
                />
                {selectedNode && graphPayload && (
                  <GraphNodePopover
                    node={selectedNode}
                    anchor={metadataAnchor}
                    linkCount={countLinksForNode(selectedNode.id, selectedLinks)}
                    onClose={closePopover}
                  />
                )}
              </>
            )}
          </div>
        </section>

        <button
          type="button"
          className="chat-resizer"
          aria-label="Resize chat panel"
          onMouseDown={onResizePointerDown}
        />
        <ChatPanel
          sessionId={sessionId}
          onGraphHighlight={onGraphHighlight}
          disabled={!!graphError}
          widthPx={chatWidth}
        />
        <AnalyticsPanel
          open={analyticsOpen}
          onClose={() => setAnalyticsOpen(false)}
          onHighlight={onAnalyticsHighlightSamples}
        />
      </main>
    </div>
  );
}

/** Optional: hide SalesOrderItem nodes for a cleaner “header” view when overlay is off. */
function filterSalesOrderSpine(data: GraphData): GraphData {
  const nodes = data.nodes.filter((n) => {
    const lab = n.labels[0];
    return lab !== "SalesOrderItem";
  });
  const allowed = new Set(nodes.map((n) => n.id));
  const links = data.links.filter((l) => allowed.has(l.source) && allowed.has(l.target));
  return { nodes, links };
}
