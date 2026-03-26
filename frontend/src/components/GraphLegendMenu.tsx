import { useEffect, useId, useRef, useState } from "react";
import { GRAPH_COLOR_LEGEND } from "../graphColors";

export function GraphLegendMenu() {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);
  const btnId = useId();
  const menuId = useId();

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className="graph-legend-wrap" ref={wrapRef}>
      <button
        id={btnId}
        type="button"
        className="toolbar-btn toolbar-btn-ghost graph-legend-trigger"
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-controls={menuId}
        onClick={() => setOpen((o) => !o)}
      >
        Colors
        <span className="graph-legend-chevron" aria-hidden>
          {open ? "▴" : "▾"}
        </span>
      </button>
      {open && (
        <div
          id={menuId}
          className="graph-legend-panel"
          role="listbox"
          aria-labelledby={btnId}
        >
          <p className="graph-legend-heading">Node colors</p>
          <ul className="graph-legend-list">
            {GRAPH_COLOR_LEGEND.map((row) => (
              <li key={row.colorName} className="graph-legend-row" role="option">
                <span
                  className="graph-legend-swatch"
                  style={{ backgroundColor: row.swatch }}
                  aria-hidden
                />
                <span className="graph-legend-text">
                  <span className="graph-legend-name">{row.colorName}:</span>{" "}
                  <span className="graph-legend-desc">{row.description}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
