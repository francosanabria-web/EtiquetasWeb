/**
 * IdealCard — Preview of Caja Ideal (Card A of hub).
 * Shows count herramientas, vigente_desde, activa badge, preview list (first 5) and edit CTA.
 */

import type { Ideal } from "../../api/cajasClient";
import KpiSkeletonCard from "../../components/kpis/KpiSkeletonCard";

type Props = {
  ideal: Ideal | null;
  loading: boolean;
  error: string | null;
  onEdit: () => void;
  puedeEscribir: boolean;
};

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleDateString("es-AR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

export default function IdealCard({ ideal, loading, error, onEdit, puedeEscribir }: Props) {
  if (loading) {
    return (
      <div className="sol-table-wrap cajas-card cajas-fade-in" style={{ padding: "1rem", display: "flex", flexDirection: "column", gap: "0.75rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3 style={{ margin: 0, fontSize: "1rem" }}>Caja Ideal</h3>
          <span className="sol-hint" style={{ fontSize: "0.8rem" }}>Cargando…</span>
        </div>
        <KpiSkeletonCard lines={4} height={140} />
        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          <div className="kpi-skeleton-line" style={{ width: "60%", height: 14 }} />
          <div className="kpi-skeleton-line" style={{ width: "85%", height: 12 }} />
          <div className="kpi-skeleton-line" style={{ width: "70%", height: 12 }} />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="sol-table-wrap" style={{ padding: "1rem" }}>
        <h3 style={{ margin: 0, fontSize: "1rem" }}>Caja Ideal</h3>
        <p className="error" role="status">{error}</p>
        <button type="button" className="btn-ghost btn-sm" onClick={onEdit} disabled={!puedeEscribir}>
          Reintentar
        </button>
      </div>
    );
  }

  const isEmpty = !ideal || ideal.id === null || ideal.id === undefined;

  if (isEmpty) {
    return (
      <div className="sol-table-wrap cajas-card cajas-fade-in" style={{ padding: "1.25rem", display: "flex", flexDirection: "column", gap: "0.75rem", alignItems: "center", textAlign: "center" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%" }}>
          <h3 style={{ margin: 0, fontSize: "1rem" }}>Caja Ideal</h3>
          <span className="sol-estado sol-estado-cancelado">Sin definir</span>
        </div>
        <div style={{ fontSize: "2.5rem", lineHeight: 1 }} role="img" aria-label="caja herramientas">🧰</div>
        <p style={{ margin: 0, fontWeight: 700, fontSize: "0.95rem" }}>Aún no definiste la caja ideal</p>
        <p className="sol-hint" style={{ margin: 0, maxWidth: 320 }}>
          Definí el set mínimo de herramientas esperado por técnico para calcular % faltantes y KPIs.
        </p>
        <p className="sol-hint" style={{ margin: 0, fontSize: "0.8rem" }}>
          {ideal?.mensaje ?? ideal?.hint ?? "Define la referencia para empezar."}
        </p>
        {puedeEscribir ? (
          <button type="button" className="btn-primary btn-sm" onClick={onEdit} style={{ marginTop: "0.25rem" }}>
            Definir caja ideal
          </button>
        ) : (
          <p className="sol-hint" style={{ margin: 0, fontStyle: "italic" }}>
            Solo usuarios con permiso de escritura pueden definir la caja ideal.
          </p>
        )}
      </div>
    );
  }

  const herramientas = ideal.herramientas ?? [];
  const preview = herramientas.slice(0, 5);

  return (
    <div className="sol-table-wrap cajas-card cajas-fade-in" style={{ padding: "1rem", display: "flex", flexDirection: "column", gap: "0.75rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
        <h3 style={{ margin: 0, fontSize: "1rem" }}>{ideal.nombre ?? "Caja Ideal"}</h3>
        <span className={`sol-estado sol-estado-${ideal.activa ? "cumplido" : "cancelado"}`}>
          {ideal.activa ? "Activa" : "Inactiva"}
        </span>
      </div>

      {ideal.descripcion && (
        <p className="sol-hint" style={{ margin: 0 }}>{ideal.descripcion}</p>
      )}

      <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap", fontSize: "0.9rem" }}>
        <span>
          <strong>{herramientas.length}</strong> herramientas
        </span>
        <span>
          Vigente desde: <strong>{formatDate(ideal.vigente_desde)}</strong>
        </span>
      </div>

      {preview.length > 0 ? (
        <ul style={{ margin: 0, paddingLeft: "1.1rem", display: "flex", flexDirection: "column", gap: "0.25rem" }}>
          {preview.map((h) => (
            <li key={h.id} style={{ fontSize: "0.9rem" }}>
              <strong>{h.codigo}</strong> — cant. mín. {h.cantidad_minima}
              {h.articulo_codigo ? <span className="sol-hint"> ({h.articulo_codigo})</span> : null}
            </li>
          ))}
          {herramientas.length > 5 && (
            <li className="sol-hint" style={{ fontSize: "0.85rem" }}>
              +{herramientas.length - 5} más…
            </li>
          )}
        </ul>
      ) : (
        <p className="sol-hint" style={{ margin: 0 }}>Sin herramientas asignadas.</p>
      )}

      {puedeEscribir ? (
        <button type="button" className="btn-primary btn-sm" onClick={onEdit}>
          Editar Caja Ideal
        </button>
      ) : (
        <p className="sol-hint" style={{ margin: 0, fontStyle: "italic" }}>Solo lectura — no podés editar.</p>
      )}
    </div>
  );
}
