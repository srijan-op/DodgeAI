import { useCallback, useEffect, useState, type MouseEvent } from "react";
import { fetchO2cAnalytics, type O2cAnalyticsPayload } from "../api";

type Props = {
  open: boolean;
  onClose: () => void;
  /** Load sample nodes into the graph (expand) then apply highlights — can be async. */
  onHighlight: (nodeIds: string[]) => void | Promise<void>;
};

export function AnalyticsPanel({ open, onClose, onHighlight }: Props) {
  const [data, setData] = useState<O2cAnalyticsPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [highlightBusy, setHighlightBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    void (async () => {
      try {
        const payload = await fetchO2cAnalytics(20);
        if (!cancelled) {
          setData(payload);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : String(e));
          setData(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open]);

  const onBackdrop = useCallback(
    (ev: MouseEvent) => {
      if (ev.target === ev.currentTarget) onClose();
    },
    [onClose]
  );

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="analytics-backdrop" role="presentation" onMouseDown={onBackdrop}>
      <div
        className="analytics-panel"
        role="dialog"
        aria-labelledby="analytics-title"
        aria-modal="true"
      >
        <div className="analytics-panel-header">
          <h2 id="analytics-title">Graph analytics</h2>
          <button type="button" className="analytics-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        <p className="analytics-note">O2C integrity checks and structural summaries.</p>
        {loading && <p className="analytics-muted">Loading…</p>}
        {error && (
          <p className="analytics-error" role="alert">
            {error}
          </p>
        )}
        {data && !loading && (
          <div className="analytics-body">
            <p className="analytics-muted">
              Generated {new Date(data.generated_at).toLocaleString()}
            </p>

            <section className="analytics-section">
              <h3>Nodes by label</h3>
              <ul className="analytics-kv">
                {Object.entries(data.label_counts)
                  .filter(([, n]) => n > 0)
                  .sort((a, b) => b[1] - a[1])
                  .map(([k, v]) => (
                    <li key={k}>
                      <span>{k}</span>
                      <span>{v}</span>
                    </li>
                  ))}
              </ul>
            </section>

            <section className="analytics-section">
              <h3>Integrity checks</h3>
              <ul className="analytics-checks">
                {data.integrity_checks.map((ch) => (
                  <li key={ch.id}>
                    <div className="analytics-check-head">
                      <strong>{ch.title}</strong>
                      <span className="analytics-count">{ch.count}</span>
                    </div>
                    {ch.sample_node_ids.length > 0 && (
                      <button
                        type="button"
                        className="toolbar-btn toolbar-btn-ghost analytics-highlight-btn"
                        disabled={highlightBusy}
                        onClick={() => {
                          setHighlightBusy(true);
                          void Promise.resolve(onHighlight(ch.sample_node_ids)).finally(() =>
                            setHighlightBusy(false)
                          );
                        }}
                      >
                        {highlightBusy ? "Loading…" : "Highlight samples on graph"}
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            </section>

            <section className="analytics-section">
              <h3>Customers by order volume (buckets)</h3>
              <ul className="analytics-kv">
                {data.order_volume_buckets.map((b) => (
                  <li key={b.bucket}>
                    <span>{b.bucket} orders</span>
                    <span>{b.customers} customers</span>
                  </li>
                ))}
              </ul>
            </section>

            <section className="analytics-section">
              <h3>Top customers by order count</h3>
              <ol className="analytics-top">
                {data.top_customers_by_orders.map((row) => (
                  <li key={row.node_id}>
                    <code>{row.node_id}</code>
                    <span>{row.orders} orders</span>
                  </li>
                ))}
              </ol>
              {data.top_customers_by_orders.length > 0 && (
                <button
                  type="button"
                  className="toolbar-btn toolbar-btn-ghost analytics-highlight-btn"
                  disabled={highlightBusy}
                  onClick={() => {
                    setHighlightBusy(true);
                    void Promise.resolve(
                      onHighlight(data.top_customers_by_orders.map((r) => r.node_id))
                    ).finally(() => setHighlightBusy(false));
                  }}
                >
                  {highlightBusy ? "Loading…" : "Highlight top customers"}
                </button>
              )}
            </section>

            <section className="analytics-section">
              <h3>Product ↔ plant</h3>
              <ul className="analytics-kv">
                <li>
                  <span>Products with AVAILABLE_AT</span>
                  <span>{data.product_plant_connectivity.products_with_plant_link}</span>
                </li>
                <li>
                  <span>Distinct plants</span>
                  <span>{data.product_plant_connectivity.distinct_plants}</span>
                </li>
                <li>
                  <span>AVAILABLE_AT relationships</span>
                  <span>{data.product_plant_connectivity.available_at_relationships}</span>
                </li>
              </ul>
            </section>
          </div>
        )}
      </div>
    </div>
  );
}
