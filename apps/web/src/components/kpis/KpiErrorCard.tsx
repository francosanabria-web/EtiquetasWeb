import type { ReactNode } from "react";

type Props = {
  message: string;
  title?: string;
  onRetry?: () => void;
};

export default function KpiErrorCard({ message, title = "Error al cargar datos", onRetry }: Props) {
  return (
    <div className="kpi-error-card" role="alert">
      <strong>{title}</strong>
      <p>{message}</p>
      {onRetry ? (
        <button type="button" className="btn-secondary" onClick={onRetry}>
          Reintentar
        </button>
      ) : null}
    </div>
  );
}

export function KpiSectionShell({
  title,
  accent,
  children,
}: {
  title: string;
  accent: string;
  children: ReactNode;
}) {
  return (
    <section className="kpi-section">
      <h2 className="kpi-section-title" style={{ borderLeftColor: accent }}>
        {title}
      </h2>
      {children}
    </section>
  );
}
