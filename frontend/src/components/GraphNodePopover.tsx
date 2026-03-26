import { useEffect, useRef } from "react";
import type { GraphNode } from "../api";

type Props = {
  node: GraphNode;
  /** Viewport coordinates (fixed positioning). */
  anchor: { x: number; y: number } | null;
  linkCount: number;
  onClose: () => void;
};

export function GraphNodePopover({ node, anchor, linkCount, onClose }: Props) {
  const cardRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      const t = e.target as HTMLElement;
      if (cardRef.current?.contains(t)) return;
      if (t.closest("[data-graph-surface]")) return;
      onClose();
    };
    const id = window.setTimeout(() => document.addEventListener("mousedown", onDoc), 180);
    return () => {
      window.clearTimeout(id);
      document.removeEventListener("mousedown", onDoc);
    };
  }, [onClose]);

  if (!anchor) return null;

  const title = node.labels[0] ?? "Node";
  const entries = Object.entries(node.properties)
    .filter(([, v]) => v !== "" && v != null)
    .slice(0, 10);

  const maxX = typeof window !== "undefined" ? window.innerWidth - 260 : anchor.x;
  const maxY = typeof window !== "undefined" ? window.innerHeight - 320 : anchor.y;
  const left = Math.max(12, Math.min(anchor.x + 8, maxX));
  const top = Math.max(12, Math.min(anchor.y + 8, maxY));

  return (
    <div
      ref={cardRef}
      className="graph-node-popover"
      style={{ left, top }}
      role="dialog"
      aria-label="Node details"
    >
      <div className="graph-node-popover-header">
        <strong>{title}</strong>
        <button type="button" className="graph-node-popover-close" onClick={onClose} aria-label="Close">
          ×
        </button>
      </div>
      <p className="graph-node-popover-id">{node.id}</p>
      <dl className="graph-node-popover-dl">
        {entries.map(([k, v]) => (
          <div key={k}>
            <dt>{k}</dt>
            <dd>{String(v)}</dd>
          </div>
        ))}
        <div>
          <dt>Connections</dt>
          <dd>{linkCount}</dd>
        </div>
      </dl>
    </div>
  );
}
