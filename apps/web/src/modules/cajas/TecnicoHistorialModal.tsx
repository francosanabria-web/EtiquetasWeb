/**
 * TecnicoHistorialModal — Timeline stepper of inventarios for a técnico ordered periodo DESC,
 * each row expandable to detalle tabla. Vertical stepper: <ol class="cajas-stepper"> with dot + line.
 */

import { useCallback, useEffect, useState } from "react";
import { getTecnicoHistorial, type TecnicoInventario } from "../../api/cajasClient";
import KpiSkeletonCard from "../../components/kpis/KpiSkeletonCard";

type Props = {
  tecnicoId: number;
  tecnicoNombre: string;
  token: string;
  onClose: () => void;
};

const PAGE_SIZE = 25;

function estadoColor(estado: string): string {
  if (estado === "malo") return "#fee2e2";
  if (estado === "regular") return "#fef9c3";
  return "#dcfce7";
}

function estadoBadgeClass(estado: string): string {
  if (estado === "cerrado") return "sol-estado-cancelado";
  return "sol-estado-cumplido";
}

function dotColor(estado: string): string {
  if (estado === "cerrado") return "#16a34a";
  if (estado === "borrador") return "#eab308";
  if (estado === "vencida") return "#ef4444";
  return "#9ca3af";
}

export default function TecnicoHistorialModal({ tecnicoId, tecnicoNombre, token, onClose }: Props) {
  const [items, setItems] = useState<TecnicoInventario[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const cargar = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getTecnicoHistorial(token, tecnicoId, { limit: PAGE_SIZE, offset });
      setItems(data.items);
      setTotal(data.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo cargar el historial.");
    } finally {
      setLoading(false);
    }
  }, [token, tecnicoId, offset]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  const totalPages = Math.ceil(total / PAGE_SIZE);
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", maxHeight: "85vh", overflow: "hidden" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.5rem" }}>
        <div>
          <h2 style={{ margin: 0, fontSize: "1.05rem" }}>Historial — {tecnicoNombre}</h2>
          <p className="sol-hint" style={{ margin: 0 }}>Técnico #{tecnicoId} — ordenado por período DESC. Total {total} inventarios.</p>
        </div>
        <button type="button" className="btn-ghost btn-sm" onClick={onClose}>
          ✕ Cerrar
        </button>
      </div>

      {loading && (
        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          <KpiSkeletonCard lines={3} height={80} />
          <KpiSkeletonCard lines={3} height={80} />
          <KpiSkeletonCard lines={2} height={60} />
        </div>
      )}
      {error && <p className="error" role="status">{error}</p>}
      {!loading && !error && items.length === 0 && (
        <div className="cajas-empty cajas-fade-in" style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "0.5rem", padding: "1.2rem", textAlign: "center" }}>
          <div style={{ fontSize: "2rem" }} role="img" aria-label="sin historial">📋</div>
          <p className="sol-hint" style={{ margin: 0 }}>Sin inventarios para este técnico.</p>
          <p className="sol-hint" style={{ margin: 0, fontSize: "0.8rem" }}>Cuando se carguen inventarios mensuales aparecerán aquí como línea de tiempo.</p>
        </div>
      )}

      {!loading && !error && items.length > 0 && (
        <div style={{ overflowY: "auto", paddingRight: "0.25rem", paddingLeft: "0.25rem" }}>
          <ol className="cajas-stepper" aria-label="Línea de tiempo de inventarios">
            {items.map((inv) => {
              const isExpanded = expandedId === inv.id;
              return (
                <li key={inv.id} className="cajas-step-item">
                  <span className="cajas-step-dot" style={{ background: dotColor(inv.estado), borderColor: "var(--surface, #fff)" }} aria-hidden="true" />
                  <div
                    style={{
                      border: "1px solid #e5e7eb",
                      borderRadius: 8,
                      overflow: "hidden",
                      background: "#fff",
                      transition: "box-shadow 0.2s ease, transform 0.2s ease",
                    }}
                    className="cajas-step-card"
                  >
                    <button
                      type="button"
                      onClick={() => setExpandedId(isExpanded ? null : inv.id)}
                      aria-expanded={isExpanded}
                      aria-controls={`detalle-${inv.id}`}
                      style={{
                        width: "100%",
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        padding: "0.65rem 0.75rem",
                        background: isExpanded ? "#f9fafb" : "#fff",
                        border: "none",
                        cursor: "pointer",
                        textAlign: "left",
                        gap: "0.5rem",
                        flexWrap: "wrap",
                      }}
                    >
                      <span style={{ display: "flex", flexDirection: "column", gap: "0.15rem" }}>
                        <span style={{ fontWeight: 700, fontSize: "0.95rem", display: "flex", alignItems: "center", gap: "0.4rem" }}>
                          <span style={{ background: "var(--primary, #0e7c66)", color: "#fff", padding: "0.1rem 0.4rem", borderRadius: 6, fontSize: "0.75rem" }}>{inv.periodo}</span>
                          {inv.caja_codigo ?? `Caja #${inv.caja_id}`}
                        </span>
                        <span className="sol-hint" style={{ fontSize: "0.8rem", margin: 0 }}>
                          Área: {inv.area ?? "—"} — Supervisor: {inv.supervisor_nombre ?? `#${inv.supervisor_id}`}
                          {inv.obs ? ` — Obs: ${inv.obs}` : ""}
                        </span>
                      </span>
                      <span style={{ display: "flex", gap: "0.4rem", alignItems: "center" }}>
                        <span className={`sol-estado ${estadoBadgeClass(inv.estado)}`} style={{ fontSize: "0.75rem" }}>
                          {inv.estado}
                        </span>
                        <span style={{ fontSize: "0.75rem", color: "#6b7280" }}>{inv.detalle.length} ítems</span>
                        <span aria-hidden="true" style={{ fontSize: "0.85rem", transition: "transform 0.2s", display: "inline-block", transform: isExpanded ? "rotate(180deg)" : "rotate(0deg)" }}>▾</span>
                      </span>
                    </button>

                    {isExpanded && (
                      <div id={`detalle-${inv.id}`} className="cajas-step-detail" style={{ borderTop: "1px solid #e5e7eb", padding: "0.5rem", overflowX: "auto", animation: "cajasFadeIn 0.2s ease" }}>
                        {inv.detalle.length === 0 ? (
                          <p className="sol-hint" style={{ margin: 0 }}>Sin detalle.</p>
                        ) : (
                          <table className="sol-table" style={{ minWidth: 520 }}>
                            <thead>
                              <tr>
                                <th>#</th>
                                <th>Código</th>
                                <th>Cantidad</th>
                                <th>Estado</th>
                                <th>Presente</th>
                                <th>Observaciones</th>
                              </tr>
                            </thead>
                            <tbody>
                              {inv.detalle.map((d) => (
                                <tr key={d.id}>
                                  <td>{d.nro_item}</td>
                                  <td>
                                    <strong>{d.herramienta_codigo}</strong>
                                  </td>
                                  <td>{d.cantidad}</td>
                                  <td>
                                    <span
                                      style={{
                                        padding: "0.15rem 0.4rem",
                                        borderRadius: 999,
                                        background: estadoColor(d.estado),
                                        fontSize: "0.8rem",
                                        fontWeight: 600,
                                        textTransform: "capitalize",
                                      }}
                                    >
                                      {d.estado}
                                    </span>
                                  </td>
                                  <td style={{ textAlign: "center" }}>
                                    {d.presente ? (
                                      <span style={{ color: "#166534", fontWeight: 700 }}>✓</span>
                                    ) : (
                                      <span style={{ color: "#991b1b", fontWeight: 700 }}>✗</span>
                                    )}
                                  </td>
                                  <td style={{ fontSize: "0.85rem", maxWidth: 220, wordBreak: "break-word" }}>
                                    {d.observaciones ?? "—"}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        )}
                      </div>
                    )}
                  </div>
                </li>
              );
            })}
          </ol>
        </div>
      )}

      {totalPages > 1 && (
        <div className="sol-pagination" style={{ marginTop: "0.25rem", flexShrink: 0 }}>
          <button
            type="button"
            className="btn-ghost btn-sm"
            disabled={offset === 0 || loading}
            onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
          >
            Anterior
          </button>
          <span>
            Página {currentPage} de {totalPages}
          </span>
          <button
            type="button"
            className="btn-ghost btn-sm"
            disabled={offset + PAGE_SIZE >= total || loading}
            onClick={() => setOffset((o) => o + PAGE_SIZE)}
          >
            Siguiente
          </button>
        </div>
      )}

      <div style={{ display: "flex", justifyContent: "flex-end", flexShrink: 0 }}>
        <button type="button" className="btn-ghost" onClick={onClose}>
          Cerrar
        </button>
      </div>
    </div>
  );
}
