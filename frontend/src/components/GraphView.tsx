import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ForceGraph3D, { ForceGraphMethods, type LinkObject } from "react-force-graph-3d";
import * as THREE from "three";
import type { GraphEdge, GraphNode } from "../api";
import { nodePaintColor } from "../graphColors";

/** Force layout mutates x/y/z on node objects at runtime. */
type SimNode = GraphNode & { x?: number; y?: number; z?: number; __size?: number };

export type GraphData = {
  nodes: SimNode[];
  links: { source: string; target: string; type: string; id?: string }[];
};

type Props = {
  data: GraphData | null;
  highlightIds: Set<string>;
  selectedId: string | null;
  onSelectNode: (node: GraphNode | null) => void;
  /** Click node: load neighbors from API (parent handles fetch + merge). */
  onNodeNavigate?: (node: GraphNode) => void;
  /** Click link: expand both endpoints. */
  onLinkNavigate?: (sourceId: string, targetId: string) => void;
  minimized: boolean;
  /** Re-run force simulation after parent merges new nodes. */
  reheatKey?: number;
  /** When false, node click only selects (for path-picking). Default true. */
  expandOnNodeClick?: boolean;
  /** Path tool: off | waiting first | waiting second click. */
  pathPickPhase?: "off" | "first" | "second";
  onPathPickNode?: (node: GraphNode, step: 1 | 2) => void;
  /** Highlight shortest-path edges returned from API. */
  pathHighlightEdgeIds?: Set<string>;
  /** Screen position for floating metadata (viewport px). */
  onSelectionScreenPos?: (pos: { x: number; y: number } | null) => void;
};

function buildGraphData(nodes: GraphNode[], edges: GraphEdge[]): GraphData {
  const links = edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    type: e.type,
  }));
  return {
    nodes: nodes.map((n) => ({ ...n })),
    links,
  };
}

export { buildGraphData };

function linkEndpoints(link: LinkObject<GraphNode, object>): { s: string; t: string } {
  const s = link.source;
  const t = link.target;
  return {
    s: typeof s === "object" && s && "id" in s ? String(s.id) : String(s),
    t: typeof t === "object" && t && "id" in t ? String(t.id) : String(t),
  };
}

function linkKey(link: LinkObject<GraphNode, object>): string {
  const { s, t } = linkEndpoints(link);
  return [s, t].sort().join("\0");
}

function linkId(link: LinkObject<GraphNode, object>): string | undefined {
  const lid = (link as { id?: string }).id;
  return lid != null ? String(lid) : undefined;
}

function useDegreeMap(links: GraphData["links"]): Map<string, number> {
  return useMemo(() => {
    const m = new Map<string, number>();
    for (const l of links) {
      m.set(l.source, (m.get(l.source) ?? 0) + 1);
      m.set(l.target, (m.get(l.target) ?? 0) + 1);
    }
    return m;
  }, [links]);
}

export function GraphView({
  data,
  highlightIds,
  selectedId,
  onSelectNode,
  onNodeNavigate,
  onLinkNavigate,
  minimized,
  reheatKey = 0,
  expandOnNodeClick = true,
  pathPickPhase = "off",
  onPathPickNode,
  pathHighlightEdgeIds,
  onSelectionScreenPos,
}: Props) {
  const fgRef = useRef<ForceGraphMethods<GraphNode, object> | undefined>(undefined);
  const mountRef = useRef<HTMLDivElement>(null);
  const [dim, setDim] = useState({ w: 800, h: 600 });
  const [hoverNodeId, setHoverNodeId] = useState<string | null>(null);
  const [hoverLinkKey, setHoverLinkKey] = useState<string | null>(null);

  const pathEdgeSet = pathHighlightEdgeIds ?? new Set<string>();
  const pathDimOthers = pathEdgeSet.size > 0;

  useEffect(() => {
    if (minimized) return;
    const ro = new ResizeObserver((entries) => {
      for (const e of entries) {
        const { width, height } = e.contentRect;
        if (width > 0 && height > 0) setDim({ w: width, h: height });
      }
    });
    const el = mountRef.current;
    if (el) ro.observe(el);
    return () => ro.disconnect();
  }, [minimized]);

  const memoData = useMemo(() => data ?? { nodes: [], links: [] }, [data]);
  const degreeMap = useDegreeMap(memoData.links);

  const highlightSig = useMemo(
    () => [...highlightIds].sort().join("\0"),
    [highlightIds]
  );

  const pathEdgeSig = useMemo(() => [...pathEdgeSet].sort().join("\0"), [pathEdgeSet]);

  /** Delay reheat so merges settle without a violent immediate kick. */
  useEffect(() => {
    const fg = fgRef.current;
    if (!fg) return;
    const h = window.setTimeout(() => {
      fg.d3ReheatSimulation();
    }, 140);
    return () => window.clearTimeout(h);
  }, [reheatKey, memoData.nodes.length, memoData.links.length]);

  useEffect(() => {
    fgRef.current?.refresh();
  }, [highlightSig, selectedId, pathEdgeSig]);

  const updateSelectionAnchor = useCallback(() => {
    if (!selectedId || !onSelectionScreenPos) return;
    const fg = fgRef.current;
    const el = mountRef.current;
    if (!fg || !el) return;
    const n = memoData.nodes.find((x) => x.id === selectedId) as SimNode | undefined;
    if (n == null || n.x == null || n.y == null || n.z == null) return;
    const p = fg.graph2ScreenCoords(n.x, n.y, n.z);
    const r = el.getBoundingClientRect();
    onSelectionScreenPos({ x: r.left + p.x, y: r.top + p.y });
  }, [selectedId, memoData.nodes, onSelectionScreenPos]);

  useEffect(() => {
    if (!selectedId || !onSelectionScreenPos) {
      onSelectionScreenPos?.(null);
      return;
    }
    let tries = 0;
    const id = window.setInterval(() => {
      tries++;
      updateSelectionAnchor();
      const n = memoData.nodes.find((x) => x.id === selectedId) as SimNode | undefined;
      if ((n && n.x != null) || tries > 50) {
        window.clearInterval(id);
      }
    }, 100);
    return () => window.clearInterval(id);
  }, [selectedId, memoData.nodes, onSelectionScreenPos, updateSelectionAnchor]);

  /** Gentle camera nudge toward selected node (after coords exist). */
  useEffect(() => {
    if (!selectedId || minimized) return;
    const fg = fgRef.current;
    if (!fg) return;
    const t = window.setTimeout(() => {
      const n = memoData.nodes.find((x) => x.id === selectedId) as SimNode | undefined;
      if (!n || n.x == null || n.y == null || n.z == null) return;
      const { x, y, z } = n;
      const dist = 160;
      fg.cameraPosition({ x: x + dist * 0.55, y: y + dist * 0.35, z: z + dist * 0.55 }, { x, y, z }, 550);
    }, 200);
    return () => window.clearTimeout(t);
  }, [selectedId, minimized, memoData.nodes]);

  const nodeColor = useCallback(
    (n: GraphNode) => nodePaintColor(n, highlightIds, selectedId),
    [highlightIds, selectedId]
  );

  const nodeLabel = useCallback((n: GraphNode) => {
    const label = n.labels[0] ?? "Node";
    const pk =
      n.properties.salesOrder ??
      n.properties.businessPartner ??
      n.properties.billingDocument ??
      n.id.split(":")[1] ??
      "";
    return `${label}${pk ? ` · ${pk}` : ""}`;
  }, []);

  const nodeVal = useCallback(
    (n: GraphNode) => {
      const deg = degreeMap.get(n.id) ?? 1;
      let v = 1.2 + Math.min(5, deg * 0.35);
      if (hoverNodeId === n.id) v *= 1.45;
      if (selectedId === n.id) v *= 1.2;
      return v;
    },
    [degreeMap, hoverNodeId, selectedId]
  );

  const nodeThreeGlow = useCallback(
    (n: GraphNode) => {
      const g = new THREE.Group();
      if (!selectedId || n.id !== selectedId) {
        g.visible = false;
        return g;
      }
      const glow = new THREE.Mesh(
        new THREE.SphereGeometry(7, 20, 20),
        new THREE.MeshBasicMaterial({
          color: 0x38bdf8,
          transparent: true,
          opacity: 0.22,
          depthWrite: false,
        })
      );
      const ring = new THREE.Mesh(
        new THREE.SphereGeometry(8.5, 16, 16),
        new THREE.MeshBasicMaterial({
          color: 0x7dd3fc,
          transparent: true,
          opacity: 0.12,
          depthWrite: false,
          wireframe: true,
        })
      );
      g.add(glow);
      g.add(ring);
      return g;
    },
    [selectedId]
  );

  const linkColor = useCallback(
    (link: LinkObject<GraphNode, object>) => {
      const lid = linkId(link);
      if (lid && pathEdgeSet.has(lid)) return "rgba(244, 114, 182, 0.98)";
      const { s, t } = linkEndpoints(link);
      if (hoverLinkKey && hoverLinkKey === linkKey(link)) return "rgba(125, 211, 252, 0.98)";
      if (highlightIds.has(s) && highlightIds.has(t)) return "rgba(96, 165, 250, 0.92)";
      if (pathDimOthers) return "rgba(160, 175, 200, 0.35)";
      return "rgba(175, 195, 220, 0.78)";
    },
    [highlightIds, hoverLinkKey, pathEdgeSet, pathDimOthers]
  );

  const linkWidth = useCallback(
    (link: LinkObject<GraphNode, object>) => {
      const lid = linkId(link);
      if (lid && pathEdgeSet.has(lid)) return 1.65;
      const { s, t } = linkEndpoints(link);
      if (hoverLinkKey && hoverLinkKey === linkKey(link)) return 1.35;
      if (highlightIds.has(s) && highlightIds.has(t)) return 1.05;
      return pathDimOthers ? 0.45 : 0.72;
    },
    [highlightIds, hoverLinkKey, pathEdgeSet, pathDimOthers]
  );

  const onNodeClick = useCallback(
    (n: GraphNode) => {
      if (pathPickPhase === "first") {
        onPathPickNode?.(n, 1);
        return;
      }
      if (pathPickPhase === "second") {
        onPathPickNode?.(n, 2);
        return;
      }
      onSelectNode(n);
      if (expandOnNodeClick) onNodeNavigate?.(n);
      window.requestAnimationFrame(() => updateSelectionAnchor());
    },
    [pathPickPhase, onPathPickNode, onSelectNode, expandOnNodeClick, onNodeNavigate, updateSelectionAnchor]
  );

  const onLinkClick = useCallback(
    (link: LinkObject<GraphNode, object>) => {
      if (pathPickPhase !== "off") return;
      const { s, t } = linkEndpoints(link);
      onLinkNavigate?.(s, t);
    },
    [pathPickPhase, onLinkNavigate]
  );

  const onEngineStop = useCallback(() => {
    updateSelectionAnchor();
  }, [updateSelectionAnchor]);

  if (minimized) {
    return (
      <div className="graph-minimized">
        <p>Graph minimized — expand to explore.</p>
      </div>
    );
  }

  return (
    <div
      ref={mountRef}
      id="graph-mount"
      className="graph-mount graph-mount-3d"
      data-graph-surface
    >
      <ForceGraph3D<GraphNode, object>
        ref={fgRef}
        width={dim.w}
        height={dim.h}
        graphData={memoData}
        nodeId="id"
        nodeLabel={nodeLabel}
        nodeColor={nodeColor}
        nodeVal={nodeVal}
        nodeOpacity={0.92}
        {...(selectedId
          ? { nodeThreeObject: nodeThreeGlow, nodeThreeObjectExtend: true as const }
          : {})}
        linkColor={linkColor}
        linkOpacity={0.92}
        linkWidth={linkWidth}
        onNodeClick={onNodeClick}
        onNodeHover={(node) => setHoverNodeId(node?.id != null ? String(node.id) : null)}
        onLinkHover={(l) => setHoverLinkKey(l ? linkKey(l) : null)}
        onLinkClick={onLinkClick}
        onBackgroundClick={() => {
          onSelectNode(null);
          setHoverLinkKey(null);
          onSelectionScreenPos?.(null);
        }}
        onEngineStop={onEngineStop}
        cooldownTicks={72}
        d3AlphaDecay={0.035}
        d3VelocityDecay={0.52}
        warmupTicks={48}
        enableNodeDrag
        showNavInfo={false}
        backgroundColor="#070b14"
        linkDirectionalParticles={3}
        linkDirectionalParticleWidth={1.65}
        linkDirectionalParticleSpeed={0.006}
        linkDirectionalParticleColor={() => "rgba(186, 230, 253, 0.9)"}
        showPointerCursor
      />
      <div className="graph-3d-hint" aria-hidden>
        {pathPickPhase === "first" && "Path mode: click the first node."}
        {pathPickPhase === "second" && "Path mode: click the second node."}
        {pathPickPhase === "off" &&
          "Click a node or edge to load more of the graph · drag to rotate · scroll to zoom"}
      </div>
    </div>
  );
}
