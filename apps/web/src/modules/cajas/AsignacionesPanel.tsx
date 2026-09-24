/**
 * AsignacionesPanel — Minimal list of active asignaciones + assign modal.
 * Uses getAsignaciones / createAsignacion / cerrarAsignacion, plus getCajas + getPersonal for selects.
 */
import { useCallback, useEffect, useState } from "react";
import { getAsignaciones, createAsignacion, cerrarAsignacion, type Asignacion } from "../../api/cajasClient";
import { getCajas, type Caja } from "../../api/cajasClient";
import { getPersonal, type Personal } from "../../api/personalClient";
import KpiSkeletonCard from "../../components/kpis/KpiSkeletonCard";

type Props = {
  token: string | null;
  refreshKey?: number;
  onChanged?: () => void;
};

export default function AsignacionesPanel({ token, refreshKey, onChanged }: Props) {
  const [items, setItems] = useState<Asignacion[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  const [cajas, setCajas] = useState<Caja[]>([]);
  const [personas, setPersonas] = useState<Personal[]>([]);
  const [cajaId, setCajaId] = useState<number | "">("");
  const [tecnicoId, setTecnicoId] = useState<number | "">("");
  const [desde, setDesde] = useState(() => new Date().toISOString().slice(0, 10));
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [cerrandoId, setCerrandoId] = useState<number | null>(null);

  const cargar = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getAsignaciones(token, { activa: 1, limit: 5, offset: 0 });
      setItems(data.items);
      setTotal(data.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudieron cargar asignaciones.");
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
    if (cajaId === "" || tecnicoId === "" || !desde.trim()) {
      setFormError("Caja, técnico y desde son obligatorios.");
      return;
    }
    setSaving(true);
    setFormError(null);
    try {
      await createAsignacion(token!, { caja_id: Number(cajaId), tecnico_id: Number(tecnicoId), desde: desde.trim() });
      setShowForm(false);
      setCajaId("");
      setTecnicoId("");
      await cargar();
      onChanged?.();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Error al asignar.");
    } finally {
      setSaving(false);
    }
  };

  const handleCerrar = async (id: number) => {
    setCerrandoId(id);
    try {
      await cerrarAsignacion(token!, id);
      await cargar();
      onChanged?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo cerrar.");
    } finally {
      setCerrandoId(null);
    }
  };

  if (!token) {
    return (
      <div className="sol-table-wrap cajas-card" style={{ padding: "1rem" }}>
        <h3 style={{ margin: 0, fontSize: "0.95rem" }}>Asignaciones</h3>
        <p className="sol-hint">Sin token.</p>
      </div>
    );
  }

  return (
    <div className="sol-table-wrap cajas-card cajas-fade-in" style={{ padding: "1rem", display: "flex", flexDirection: "column", gap: "0.75rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
        <h3 style={{ margin: 0, fontSize: "0.95rem" }}>Asignaciones activas</h3>
        <span className="sol-hint" style={{ fontSize: "0.8rem" }}>{total} activas</span>
      </div>

      {loading && <KpiSkeletonCard lines={3} height={120} />}

      {!loading && error && <p className="error" role="status">{error}</p>}

      {!loading && !error && items.length === 0 && (
        <div className="cajas-empty cajas-fade-in" style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "0.5rem", padding: "0.75rem", textAlign: "center" }}>
          <div style={{ fontSize: "1.8rem" }} role="img" aria-label="asignaciones">🔗</div>
          <p className="sol-hint" style={{ margin: 0 }}>Sin asignaciones activas.</p>
          <p className="sol-hint" style={{ margin: 0, fontSize: "0.8rem" }}>Asigná una caja a un técnico para ver inventario por técnico.</p>
        </div>
      )}

      {!loading && !error && items.length > 0 && (
        <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: "0.4rem" }}>
          {items.map((a) => (
            <li key={a.id} style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: "0.5rem 0.6rem", display: "flex", flexDirection: "column", gap: "0.3rem", background: "#fff" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.4rem", flexWrap: "wrap" }}>
                <strong style={{ fontSize: "0.85rem" }}>{a.caja_codigo ?? `Caja #${a.caja_id}`} → {a.tecnico_nombre ?? `Téc #${a.tecnico_id}`}</strong>
                <span style={{ fontSize: "0.7rem", padding: "0.15rem 0.4rem", borderRadius: 999, background: "#dcfce7", color: "#166534", fontWeight: 700 }}>activa</span>
              </div>
              <span className="sol-hint" style={{ fontSize: "0.78rem" }}>Desde: {a.desde ?? "—"} {a.hasta ? `— Hasta: ${a.hasta}` : ""}</span>
              <button type="button" className="btn-ghost btn-sm" onClick={() => handleCerrar(a.id)} disabled={cerrandoId === a.id} style={{ alignSelf: "flex-start" }}>
                {cerrandoId === a.id ? "Cerrando…" : "Cerrar asignación"}
              </button>
            </li>
          ))}
        </ul>
      )}

      <button type="button" className="btn-primary btn-sm" onClick={() => setShowForm(true)} style={{ alignSelf: "flex-start" }}>
        + Asignar caja
      </button>

      {showForm && (
        <div className="sol-modal-backdrop" role="dialog" aria-modal="true">
          <div className="sol-modal">
            <form className="sol-form" onSubmit={handleCreate}>
              <h2>Asignar caja</h2>
              {formError && <p className="error" role="status">{formError}</p>}
              <label>
                Caja *
                <select value={cajaId} onChange={(e) => setCajaId(e.target.value ? Number(e.target.value) : "")} required>
                  <option value="">Seleccionar caja</option>
                  {cajas.map((c) => (
                    <option key={c.id} value={c.id}>{c.codigo} {c.activa ? "" : "(inactiva)"}</option>
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
                Desde *
                <input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} required />
              </label>
              <div className="sol-form-actions">
                <button type="button" className="btn-ghost" onClick={() => setShowForm(false)} disabled={saving}>Cancelar</button>
                <button type="submit" className="btn-primary" disabled={saving}>{saving ? "Asignando…" : "Asignar"}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
