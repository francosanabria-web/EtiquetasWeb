import { useState } from "react";
import { fmtNum, fmtPesos, KPI_COLORS, type ReposicionResumen } from "../../api/kpisClient";
import KpiErrorCard, { KpiSectionShell } from "./KpiErrorCard";
import KpiExpandable from "./KpiExpandable";
import KpiSkeletonCard from "./KpiSkeletonCard";

type Props = {
  data: ReposicionResumen | null;
  loading: boolean;
  error: string | null;
};

export default function ReposicionSection({ data, loading, error }: Props) {
  const [modalOpen, setModalOpen] = useState(false);

  if (loading) {
    return (
      <KpiSectionShell title="Reposición" accent={KPI_COLORS.reposicion}>
        <KpiSkeletonCard lines={4} height={200} />
      </KpiSectionShell>
    );
  }
  if (error) {
    return (
      <KpiSectionShell title="Reposición" accent={KPI_COLORS.reposicion}>
        <KpiErrorCard message={error} />
      </KpiSectionShell>
    );
  }
  if (!data) return null;

  const criticos = data.lista.filter((a) => a.criticidad === "CRÍTICO").slice(0, 5);

  return (
    <KpiSectionShell title="Reposición" accent={KPI_COLORS.reposicion}>
      <div className="kpi-alert-row">
        {criticos.length === 0 ? (
          <p className="kpi-chart-caption">No hay artículos CRÍTICOS bajo mínimo.</p>
        ) : (
          criticos.map((a) => (
            <div key={a.codigo} className="kpi-alert-card">
              <span className="kpi-alert-tag">CRÍTICO</span>
              <strong>{a.codigo}</strong>
              <p className="kpi-td-desc">{a.desc}</p>
              <p>
                Stock {fmtNum(a.stock)} / mín. {fmtNum(a.stk_min)} · Faltan {fmtNum(a.faltante ?? 0)}
              </p>
              <p className="kpi-alert-monto">{fmtPesos(a.valor_faltante ?? 0)}</p>
            </div>
          ))
        )}
        {data.lista.length > 5 && (
          <button type="button" className="btn-ghost kpi-ver-todos" onClick={() => setModalOpen(true)}>
            Ver todos ({fmtNum(data.articulos_a_reponer)})
          </button>
        )}
      </div>

      <KpiExpandable
        title={`Artículos a reponer (${fmtNum(data.articulos_a_reponer)}) — ${fmtPesos(data.valor_total_reposicion)}`}
        className="kpi-full-width"
      >
        {({ tableMaxHeight }) => (
          <>
            <div
              className="kpi-table-wrap kpi-table-scroll"
              style={tableMaxHeight === "none" ? undefined : { maxHeight: tableMaxHeight }}
            >
              <table className="kpi-table">
            <thead>
              <tr>
                <th>Código</th>
                <th>Descripción</th>
                <th>Stock</th>
                <th>Mínimo</th>
                <th>Faltante</th>
                <th>Precio</th>
                <th>Total</th>
              </tr>
            </thead>
            <tbody>
              {data.lista.slice(0, 50).map((a) => (
                <tr key={a.codigo}>
                  <td>{a.codigo}</td>
                  <td className="kpi-td-desc">{a.desc}</td>
                  <td>{fmtNum(a.stock)}</td>
                  <td>{fmtNum(a.stk_min)}</td>
                  <td>{fmtNum(a.faltante ?? 0)}</td>
                  <td>{fmtPesos(a.precio_unitario)}</td>
                  <td>{fmtPesos(a.valor_faltante ?? 0)}</td>
                </tr>
              ))}
            </tbody>
            </table>
            </div>
            {data.lista.length > 50 && (
              <button type="button" className="btn-ghost kpi-ver-todos" onClick={() => setModalOpen(true)}>
                Ver lista completa
              </button>
            )}
          </>
        )}
      </KpiExpandable>

      {modalOpen && (
        <div className="kpi-modal-backdrop" onClick={() => setModalOpen(false)} role="presentation">
          <div className="kpi-modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
            <header className="kpi-modal-head">
              <h3>Todos los artículos a reponer</h3>
              <button type="button" className="btn-ghost btn-sm" onClick={() => setModalOpen(false)}>
                Cerrar
              </button>
            </header>
            <div className="kpi-table-wrap kpi-table-scroll kpi-modal-body">
              <table className="kpi-table">
                <thead>
                  <tr>
                    <th>Código</th>
                    <th>Descripción</th>
                    <th>Stock</th>
                    <th>Mínimo</th>
                    <th>Faltante</th>
                    <th>Precio</th>
                    <th>Total</th>
                    <th>Crit.</th>
                  </tr>
                </thead>
                <tbody>
                  {data.lista.map((a) => (
                    <tr key={a.codigo}>
                      <td>{a.codigo}</td>
                      <td className="kpi-td-desc">{a.desc}</td>
                      <td>{fmtNum(a.stock)}</td>
                      <td>{fmtNum(a.stk_min)}</td>
                      <td>{fmtNum(a.faltante ?? 0)}</td>
                      <td>{fmtPesos(a.precio_unitario)}</td>
                      <td>{fmtPesos(a.valor_faltante ?? 0)}</td>
                      <td>{a.criticidad}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </KpiSectionShell>
  );
}
