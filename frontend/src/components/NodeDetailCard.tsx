import type { GraphNode } from "../api";

type Props = {
  node: GraphNode;
  linkCount: number;
  onClose: () => void;
};

export function NodeDetailCard({ node, linkCount, onClose }: Props) {
  const title = node.labels[0] ?? "Node";
  const props = node.properties;
  const entries = Object.entries(props)
    .filter(([, v]) => v !== "" && v != null)
    .slice(0, 12);

  return (
    <div className="node-card">
      <div className="node-card-header">
        <h3>{title}</h3>
        <button type="button" className="node-card-close" onClick={onClose} aria-label="Close">
          ×
        </button>
      </div>
      <dl className="node-card-dl">
        <div>
          <dt>Entity</dt>
          <dd>{title}</dd>
        </div>
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
