import { useEffect, useId, useRef, useState } from "react";

export function GraphImportantNote() {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);
  const btnId = useId();
  const panelId = useId();

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
        aria-haspopup="dialog"
        aria-controls={panelId}
        onClick={() => setOpen((o) => !o)}
      >
        Important note
        <span className="graph-legend-chevron" aria-hidden>
          {open ? "▴" : "▾"}
        </span>
      </button>
      {open && (
        <div
          id={panelId}
          className="graph-legend-panel graph-note-panel"
          role="dialog"
          aria-labelledby={`${btnId}-title`}
        >
          <p id={`${btnId}-title`} className="graph-legend-heading">
            Important notes
          </p>
          <ol className="graph-note-list">
            <li>
              For a quicker, cleaner redraw, click <strong>Minimize</strong>, then{" "}
              <strong>Expand graph</strong> again.
            </li>
            <li>
              It looks bunched at first because the **first load is capped at 200** matches
              so the page stays fast—click <strong>nodes</strong> or <strong>edges</strong> to
              pull in more of the graph and spread the layout.
            </li>
          </ol>
        </div>
      )}
    </div>
  );
}
