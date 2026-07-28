import { useCallback, useEffect, useState, type ReactNode } from "react";

export type KpiExpandCtx = {
  chartHeight: number;
  tableMaxHeight: number | "none";
};

type Props = {
  title: string;
  className?: string;
  children: (ctx: KpiExpandCtx) => ReactNode;
};

const COMPACT: KpiExpandCtx = { chartHeight: 260, tableMaxHeight: 360 };
const LARGE: KpiExpandCtx = { chartHeight: 520, tableMaxHeight: "none" };

export default function KpiExpandable({ title, className = "", children }: Props) {
  const [expanded, setExpanded] = useState(false);

  const close = useCallback(() => setExpanded(false), []);

  useEffect(() => {
    if (!expanded) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [expanded, close]);

  const head = (
    <div className="kpi-panel-head">
      <h3>{title}</h3>
      <button
        type="button"
        className="btn-ghost btn-sm kpi-expand-btn"
        onClick={() => setExpanded(true)}
        title="Ampliar panel"
      >
        Ampliar
      </button>
    </div>
  );

  return (
    <>
      <div className={`kpi-chart-card ${className}`.trim()}>
        {head}
        {children(COMPACT)}
      </div>

      {expanded && (
        <div className="kpi-expand-modal-backdrop" role="dialog" aria-modal="true">
          <div className="kpi-expand-modal">
            <div className="kpi-panel-head">
              <h3>{title}</h3>
              <button type="button" className="btn-ghost btn-sm" onClick={close}>
                Cerrar
              </button>
            </div>
            <div className="kpi-expand-modal-body">{children(LARGE)}</div>
          </div>
        </div>
      )}
    </>
  );
}
