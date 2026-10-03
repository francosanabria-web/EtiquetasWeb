/**
 * TecnicosCards — Grid paginado de cards por técnico con métricas vs Caja Ideal.
 * Includes search q and pagination Anterior/Siguiente, and historial drill-down.
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getTecnicosCards, type TecnicoCard } from "../../api/cajasClient";
import TecnicoHistorialModal from "./TecnicoHistorialModal";
import KpiSkeletonCard from "../../components/kpis/KpiSkeletonCard";

type Props = {
  token: string | null;
  refreshKey?: number;
};

const PAGE_SIZE = 25;

function faltantesColor(pct: number | null): { bg: string; color: string; label: string } {
  if (pct === null || pct === undefined) return { bg: "#e5e7eb", color: "#374151", label: "Sin ideal" };
  if (pct <= 10) return { bg: "#dcfce7", color: "#166534", label: `${pct.toFixed(1)}% faltante` };
  if (pct <= 50) return { bg: "#fef9c3", color: "#854d0e", label: `${pct.toFixed(1)}% faltante` };
  return { bg: "#fee2e2", color: "#991b1b", label: `${pct.toFixed(1)}% faltante` };
}

function estadoBadge(estado: string | null): { cls: string; text: string } {
  if (estado === "cerrado") return { cls: "sol-estado-cancelado", text: "cerrado" };
  if (estado === "borrador") return { cls: "sol-estado-cumplido", text: "borrador" };
  return { cls: "sol-estado-cancelado", text: "sin inventario" };
}

export default function TecnicosCards({ token, refreshKey }: Props) {
  const navigate = useNavigate();
  const [items, setItems] = useState<TecnicoCard[]>([]);
  const [total, setTotal] = useState(0);
  const [q, setQ] = useState("");
  const [qInput, setQInput] = useState("");
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<TecnicoCard | null>(null);
  const [soloConInventario, setSoloConInventario] = useState(true);

  const cargar = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getTecnicosCards(token, { limit: PAGE_SIZE, offset, q: q || undefined, con_inventario: soloConInventario });
      setItems(data.items);
      setTotal(data.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudieron cargar los técnicos.");
    } finally {
      setLoading(false);
    }
  }, [token, offset, q, soloConInventario]);

  useEffect(() => {
    void cargar();
  }, [cargar, refreshKey]);

  // Debounce qInput -> q
  useEffect(() => {
    const t = setTimeout(() => {
      setQ(qInput.trim());
      setOffset(0);
    }, 350);
    return () => clearTimeout(t);
  }, [qInput]);

  const totalPages = Math.ceil(total / PAGE_SIZE);
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;

  if (!token) {
    return (
      <div className="sol-table-wrap" style={{ padding: "1rem" }}>
        <h3 style={{ margin: 0, fontSize: "1rem" }}>Inventario por Técnico</h3>
        <p className="sol-hint">Sin token — iniciá sesión para ver los técnicos.</p>
      </div>
    );
  }

  return (
    <div className="sol-table-wrap cajas-card cajas-fade-in" style={{ padding: "1rem", display: "flex", flexDirection: "column", gap: "0.75rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
        <h3 style={{ margin: 0, fontSize: "1rem" }}>Inventario por Técnico</h3>
        <span className="sol-hint" style={{ fontSize: "0.85rem" }}>{total} técnicos</span>
      </div>

      <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
        <span style={{ fontSize: "0.85rem", fontWeight: 600 }}>Buscar técnico</span>
        <input
          value={qInput}
          onChange={(e) => setQInput(e.target.value)}
          placeholder="Buscar por nombre o legajo…"
        />
      </label>

      <label style={{ display: "flex", alignItems: "center", gap: "0.4rem", fontSize: "0.85rem", cursor: "pointer" }}>
        <input
          type="checkbox"
          checked={soloConInventario}
          onChange={(e) => { setSoloConInventario(e.target.checked); setOffset(0); }}
        />
        Solo técnicos con inventario
      </label>

      {loading && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: "0.75rem" }}>
          {Array.from({ length: 6 }).map((_, i) => (
            <KpiSkeletonCard key={i} lines={4} height={140} />
          ))}
        </div>
      )}
      {error && <p className="error" role="status">{error}</p>}
      {!loading && !error && items.length === 0 && (
        <div className="cajas-empty cajas-fade-in" style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "0.5rem", padding: "1.25rem 0.5rem", textAlign: "center" }}>
          <div style={{ fontSize: "2.2rem", lineHeight: 1 }} role="img" aria-label="tecnicos">👷</div>
          <p style={{ margin: 0, fontWeight: 700 }}>No hay técnicos con caja</p>
          <p className="sol-hint" style={{ margin: 0, maxWidth: 320 }}>
            {q ? `Sin resultados para "${q}".` : "Aún no hay técnicos asignados. Cargalos desde Personal o asigná una caja."}
          </p>
          <button type="button" className="btn-primary btn-sm" onClick={() => navigate("/admin/personal")} style={{ marginTop: "0.25rem" }}>
            Cargar técnicos
          </button>
        </div>
      )}

      {!loading && !error && items.length > 0 && (
        <div
          className="cajas-fade-in"
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))",
            gap: "0.75rem",
          }}
        >
          {items.map((t) => {
            const fc = faltantesColor(t.faltantes_pct);
            const eb = estadoBadge(t.ultimo_estado);
            return (
              <div
                key={t.tecnico_id}
                style={{
                  border: "1px solid #e5e7eb",
                  borderRadius: 10,
                  padding: "0.75rem",
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.5rem",
                  background: "#fff",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "0.5rem" }}>
                  <strong style={{ fontSize: "0.95rem", lineHeight: 1.2 }}>{t.tecnico_nombre}</strong>
                  <span
                    style={{
                      fontSize: "0.7rem",
                      padding: "0.15rem 0.4rem",
                      borderRadius: 999,
                      background: "#f3f4f6",
                      color: "#374151",
                      textTransform: "uppercase",
                      fontWeight: 600,
                    }}
                  >
                    {t.tecnico_tipo}
                  </span>
                </div>

                <div style={{ fontSize: "0.85rem", display: "flex", flexDirection: "column", gap: "0.15rem" }}>
                  <span>
                    Caja: <strong>{t.caja_codigo ?? "—"}</strong>
                  </span>
                  <span>
                    Último período: <strong>{t.ultimo_periodo ?? "—"}</strong>{" "}
                    <span className={`sol-estado ${eb.cls}`} style={{ fontSize: "0.75rem", padding: "0.1rem 0.35rem" }}>
                      {eb.text}
                    </span>
                  </span>
                </div>

                <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem", alignItems: "center" }}>
                  <span
                    style={{
                      background: fc.bg,
                      color: fc.color,
                      padding: "0.2rem 0.5rem",
                      borderRadius: 999,
                      fontSize: "0.8rem",
                      fontWeight: 700,
                    }}
                  >
                    {fc.label}
                  </span>
                  {t.faltantes_pct !== null && (
                    <span className="sol-hint" style={{ fontSize: "0.8rem" }}>
                      Completitud {t.completitud_pct.toFixed(1)}%
                    </span>
                  )}
                </div>

                <div style={{ fontSize: "0.8rem", color: "#6b7280" }}>
                  Limpieza score: <strong>{t.limpieza_score.toFixed(1)}%</strong>
                  {t.ideal_count ? <span> — ideal {t.ideal_count} / presente {t.presente_count}</span> : null}
                </div>

                <button
                  type="button"
                  className="btn-ghost btn-sm"
                  onClick={() => setSelected(t)}
                  style={{ marginTop: "auto", alignSelf: "flex-start" }}
                >
                  Ver historial
                </button>
              </div>
            );
          })}
        </div>
      )}

      {totalPages > 1 && (
        <div className="sol-pagination" style={{ marginTop: "0.25rem" }}>
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

      {selected && token && (
        <div className="sol-modal-backdrop" role="dialog" aria-modal="true">
          <div className="sol-modal sol-modal-wide" style={{ maxWidth: 860 }}>
            <TecnicoHistorialModal
              tecnicoId={selected.tecnico_id}
              tecnicoNombre={selected.tecnico_nombre}
              token={token}
              onClose={() => setSelected(null)}
            />
          </div>
        </div>
      )}
    </div>
  );
}
