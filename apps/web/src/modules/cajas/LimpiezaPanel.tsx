/**
 * LimpiezaPanel — Minimal list of last 5 limpieza events with create modal.
 * Uses getLimpieza / createLimpieza from cajasClient, plus getCajas + getPersonal for selects.
 */
import { useCallback, useEffect, useState } from "react";
import { getLimpieza, createLimpieza, type LimpiezaEvento } from "../../api/cajasClient";
import { getCajas, type Caja } from "../../api/cajasClient";
import { getPersonal, type Personal } from "../../api/personalClient";
import KpiSkeletonCard from "../../components/kpis/KpiSkeletonCard";

type Props = {
  token: string | null;
  refreshKey?: number;
};

function estadoBadge(estado: string): string {
  if (estado === "realizada") return "sol-estado-cumplido";
  if (estado === "vencida") return "sol-estado-cancelado";
  return "sol-estado-cancelado";
}

export default function LimpiezaPanel({ token, refreshKey }: Props) {
  const [items, setItems] = useState<LimpiezaEvento[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  // form state
  const [cajas, setCajas] = useState<Caja[]>([]);
  const [personas, setPersonas] = useState<Personal[]>([]);
  const [cajaId, setCajaId] = useState<number | "">("");
  const [tecnicoId, setTecnicoId] = useState<number | "">("");
  const [estado, setEstado] = useState("pendiente");
  const [observaciones, setObservaciones] = useState("");
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getLimpieza(token, { limit: 5, offset: 0 });
      setItems(data.items);
      setTotal(data.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo cargar limpieza.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  const cargarAux = useCallback(async () => {
    if (!token) return;
    try {
      const [cData, pData] = await Promise.all([getCajas(token, { limit: 50, offset: 0 }), getPersonal(token, { limit: 50, offset: 0 })]);
      setCajas(cData.items);
      setPersonas(pData.items.filter((p) => ["tecnico", "supervisor", "generico", "panol"].includes(p.tipo)));
    } catch {
      // silent
    }
  }, [token]);

  useEffect(() => {
    void cargar();
  }, [cargar, refreshKey]);

  useEffect(() => {
    if (showForm) void cargarAux();
  }, [showForm, cargarAux]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (cajaId === "" || tecnicoId === "") {
      setFormError("Caja y técnico son obligatorios.");
      return;
    }
    setSaving(true);
    setFormError(null);
    try {
      await createLimpieza(token!, {
        caja_id: Number(cajaId),
        tecnico_id: Number(tecnicoId),
        estado,
        observaciones: observaciones.trim() ? observaciones.trim() : null,
      });
      setShowForm(false);
      setCajaId("");
      setTecnicoId("");
      setObservaciones("");
      setEstado("pendiente");
      await cargar();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Error al crear.");
    } finally {
      setSaving(false);
    }
  };

  if (!token) {
    return (
      <div className="sol-table-wrap cajas-card" style={{ padding: "1rem" }}>
        <h3 style={{ margin: 0, fontSize: "0.95rem" }}>Limpieza</h3>
        <p className="sol-hint">Sin token.</p>
      </div>
    );
  }

  return (
    <div className="sol-table-wrap cajas-card cajas-fade-in" style={{ padding: "1rem", display: "flex", flexDirection: "column", gap: "0.75rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
        <h3 style={{ margin: 0, fontSize: "0.95rem" }}>Limpieza — últimos 5</h3>
        <span className="sol-hint" style={{ fontSize: "0.8rem" }}>{total} eventos</span>
      </div>

      {loading && <KpiSkeletonCard lines={3} height={120} />}

      {!loading && error && <p className="error" role="status">{error}</p>}

      {!loading && !error && items.length === 0 && (
        <div className="cajas-empty cajas-fade-in" style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "0.5rem", padding: "0.75rem", textAlign: "center" }}>
          <div style={{ fontSize: "1.8rem" }} role="img" aria-label="limpieza">🧹</div>
          <p className="sol-hint" style={{ margin: 0 }}>Sin eventos de limpieza aún.</p>
          <p className="sol-hint" style={{ margin: 0, fontSize: "0.8rem" }}>Registrá la primera limpieza para auditar estado de cajas.</p>
        </div>
      )}

      {!loading && !error && items.length > 0 && (
        <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: "0.4rem" }}>
          {items.map((ev) => (
            <li key={ev.id} style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: "0.5rem 0.6rem", display: "flex", flexDirection: "column", gap: "0.2rem", background: "#fff" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.4rem", flexWrap: "wrap" }}>
                <strong style={{ fontSize: "0.85rem" }}>{ev.caja_codigo ?? `Caja #${ev.caja_id}`} — {ev.tecnico_nombre ?? `Téc #${ev.tecnico_id}`}</strong>
                <span className={`sol-estado ${estadoBadge(ev.estado)}`} style={{ fontSize: "0.7rem" }}>{ev.estado}</span>
              </div>
              <span className="sol-hint" style={{ fontSize: "0.78rem" }}>
                {ev.fecha ? new Date(ev.fecha).toLocaleDateString("es-AR") : "—"} {ev.observaciones ? `— ${ev.observaciones}` : ""}
              </span>
            </li>
          ))}
        </ul>
      )}

      <button type="button" className="btn-primary btn-sm" onClick={() => setShowForm(true)} style={{ alignSelf: "flex-start" }}>
        + Registrar limpieza
      </button>

      {showForm && (
        <div className="sol-modal-backdrop" role="dialog" aria-modal="true">
          <div className="sol-modal">
            <form className="sol-form" onSubmit={handleCreate}>
              <h2>Registrar limpieza</h2>
              {formError && <p className="error" role="status">{formError}</p>}
              <label>
                Caja *
                <select value={cajaId} onChange={(e) => setCajaId(e.target.value ? Number(e.target.value) : "")} required>
                  <option value="">Seleccionar caja</option>
                  {cajas.map((c) => (
                    <option key={c.id} value={c.id}>{c.codigo}</option>
                  ))}
                </select>
              </label>
              <label>
                Técnico *
                <select value={tecnicoId} onChange={(e) => setTecnicoId(e.target.value ? Number(e.target.value) : "")} required>
                  <option value="">Seleccionar técnico</option>
                  {personas.map((p) => (
                    <option key={p.id} value={p.id}>{p.nombre} ({p.tipo})</option>
                  ))}
                </select>
              </label>
              <label>
                Estado
                <select value={estado} onChange={(e) => setEstado(e.target.value)}>
                  <option value="pendiente">pendiente</option>
                  <option value="realizada">realizada</option>
                  <option value="vencida">vencida</option>
                </select>
              </label>
              <label>
                Observaciones
                <textarea value={observaciones} onChange={(e) => setObservaciones(e.target.value)} placeholder="Opcional" rows={2} />
              </label>
              <div className="sol-form-actions">
                <button type="button" className="btn-ghost" onClick={() => setShowForm(false)} disabled={saving}>Cancelar</button>
                <button type="submit" className="btn-primary" disabled={saving}>{saving ? "Guardando…" : "Crear"}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
