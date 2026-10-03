/**
 * InventarioFormModal — Modal de creación de inventario con dropdowns de personal.
 */

import { useState, type FormEvent } from "react";
import { createInventario, recomendarCodigo, type Inventario, type RecomendacionCodigo } from "../../api/cajasClient";
import { type Personal } from "../../api/personalClient";

type Props = {
  tecnicos: Personal[];
  supervisores: Personal[];
  onGuardado: (inv: Inventario) => void;
  onCancelar: () => void;
  token: string;
  cargando: boolean;
};

export default function InventarioFormModal({ tecnicos, supervisores, onGuardado, onCancelar, token, cargando }: Props) {
  const [cajaId, setCajaId] = useState("");
  const [periodo, setPeriodo] = useState("");
  const [tecnicoId, setTecnicoId] = useState("");
  const [supervisorId, setSupervisorId] = useState("");
  const [obs, setObs] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [detalle, setDetalle] = useState<Array<{ herramienta_codigo: string; descripcion: string; cantidad: number; presente: boolean; observaciones: string }>>([
    { herramienta_codigo: "", descripcion: "", cantidad: 1, presente: true, observaciones: "" },
  ]);
  const [sugerencias, setSugerencias] = useState<Record<number, RecomendacionCodigo[]>>({});
  const [cargandoSug, setCargandoSug] = useState<number | null>(null);

  const handleAddDetalle = () => {
    setDetalle([...detalle, { herramienta_codigo: "", descripcion: "", cantidad: 1, presente: true, observaciones: "" }]);
  };

  const handleDetalleChange = (idx: number, field: string, value: string | number | boolean) => {
    const newDetalle = [...detalle];
    (newDetalle[idx] as any)[field] = value;
    setDetalle(newDetalle);
  };

  const handleSugerir = async (idx: number) => {
    const desc = detalle[idx]?.descripcion?.trim();
    if (!desc) {
      setError("Ingresá una descripción para sugerir código.");
      return;
    }
    setCargandoSug(idx);
    setError(null);
    try {
      const res = await recomendarCodigo(token, desc, 5);
      setSugerencias((prev) => ({ ...prev, [idx]: res.items }));
      if (res.items.length === 0) setError(`Sin sugerencias en maestro_stock para "${desc}".`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al sugerir código.");
    } finally {
      setCargandoSug(null);
    }
  };

  const handleElegirSugerencia = (idx: number, codigo: string) => {
    handleDetalleChange(idx, "herramienta_codigo", codigo);
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!cajaId || !periodo || !tecnicoId || !supervisorId) {
      setError("Todos los campos obligatorios son requeridos.");
      return;
    }
    if (detalle.some((d) => (!d.herramienta_codigo.trim() && !d.descripcion.trim()) || d.cantidad <= 0 || typeof d.presente !== "boolean")) {
      setError("Cada detalle requiere código o descripción, cantidad > 0 y presente.");
      return;
    }
    try {
      const data = {
        caja_id: parseInt(cajaId),
        tecnico_id: parseInt(tecnicoId),
        supervisor_id: parseInt(supervisorId),
        periodo,
        obs: obs || null,
        detalle: detalle.map((d) => ({
          herramienta_codigo: d.herramienta_codigo.trim() || null,
          descripcion: d.descripcion.trim() || null,
          herramienta_descripcion: d.descripcion.trim() || null,
          cantidad: d.cantidad,
          presente: d.presente,
          observaciones: d.observaciones || null,
        })),
      };
      const result = await createInventario(token, data as any);
      onGuardado(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al crear inventario.");
    }
  };

  return (
    <form className="sol-form" onSubmit={handleSubmit}>
      <h2>Nuevo Inventario</h2>
      {error && <p className="error" role="status">{error}</p>}

      <div className="sol-grid-2">
        <label>
          Caja ID *
          <input type="number" value={cajaId} onChange={(e) => setCajaId(e.target.value)} required />
        </label>
        <label>
          Período *
          <input type="month" value={periodo} onChange={(e) => setPeriodo(e.target.value)} required />
        </label>
      </div>

      <div className="sol-grid-2">
        <label>
          Técnico *
          <select value={tecnicoId} onChange={(e) => setTecnicoId(e.target.value)} required>
            <option value="">Seleccionar técnico…</option>
            {tecnicos.map((t) => (
              <option key={t.id} value={t.id}>{t.nombre}</option>
            ))}
          </select>
        </label>
        <label>
          Supervisor *
          <select value={supervisorId} onChange={(e) => setSupervisorId(e.target.value)} required>
            <option value="">Seleccionar supervisor…</option>
            {supervisores.map((s) => (
              <option key={s.id} value={s.id}>{s.nombre}</option>
            ))}
          </select>
        </label>
      </div>

      {/* Detalle — permite sin código para base inicial */}
      <label>
        Detalle de herramientas
        <span className="sol-hint" style={{ display: "block", marginTop: 4, fontSize: "0.8rem" }}>
          Podés cargar solo la descripción si aún no tenés el código. El sistema creará la herramienta como “pendiente de codificar” y luego podrás recomendar el código desde maestro_stock.
        </span>
        {detalle.map((d, idx) => (
          <div key={idx} style={{ marginTop: 12, border: "1px solid #e5e7eb", borderRadius: 8, padding: 8, background: "#fafafa" }}>
            <div className="sol-grid-3" style={{ alignItems: "end" }}>
              <label>
                Código
                <input value={d.herramienta_codigo} onChange={(e) => handleDetalleChange(idx, "herramienta_codigo", e.target.value)} placeholder="Código (opcional)" />
              </label>
              <label>
                Descripción *
                <input value={d.descripcion} onChange={(e) => handleDetalleChange(idx, "descripcion", e.target.value)} placeholder="Ej: Llave francesa 10&quot;" />
              </label>
              <label>
                Cantidad *
                <input type="number" min={1} value={d.cantidad} onChange={(e) => handleDetalleChange(idx, "cantidad", parseInt(e.target.value) || 0)} />
              </label>
              <label>
                Presente
                <select value={String(d.presente)} onChange={(e) => handleDetalleChange(idx, "presente", e.target.value === "true")}>
                  <option value="true">Sí</option>
                  <option value="false">No</option>
                </select>
              </label>
            </div>
            <div style={{ display: "flex", gap: 8, marginTop: 6, alignItems: "center", flexWrap: "wrap" }}>
              <button type="button" className="btn-ghost btn-sm" onClick={() => handleSugerir(idx)} disabled={cargandoSug === idx || !d.descripcion.trim()}>
                {cargandoSug === idx ? "Buscando…" : "Sugerir código (maestro_stock)"}
              </button>
              {d.herramienta_codigo.trim() && <span className="sol-hint" style={{ fontSize: "0.8rem" }}>Código: <strong>{d.herramienta_codigo}</strong></span>}
              {!d.herramienta_codigo.trim() && d.descripcion.trim() && <span className="sol-hint" style={{ fontSize: "0.8rem", color: "#b45309" }}>Se guardará sin código (pendiente)</span>}
            </div>
            {sugerencias[idx]?.length > 0 && (
              <div style={{ marginTop: 6, display: "flex", flexDirection: "column", gap: 4 }}>
                <span className="sol-hint" style={{ fontSize: "0.8rem", fontWeight: 600 }}>Sugerencias maestro_stock:</span>
                {sugerencias[idx].map((s) => (
                  <button
                    key={s.codigo}
                    type="button"
                    className="btn-ghost btn-sm"
                    style={{ textAlign: "left", justifyContent: "flex-start", fontSize: "0.85rem" }}
                    onClick={() => handleElegirSugerencia(idx, s.codigo)}
                  >
                    <strong>{s.codigo}</strong> — {s.descripcion}{s.alias ? ` (alias: ${s.alias})` : ""} <span style={{ color: "#6b7280" }}>score {s.score}</span>
                  </button>
                ))}
              </div>
            )}
            {sugerencias[idx]?.length === 0 && sugerencias[idx] && (
              <span className="sol-hint" style={{ fontSize: "0.8rem" }}>Sin coincidencias.</span>
            )}
          </div>
        ))}
        <button type="button" className="btn-ghost btn-sm" onClick={handleAddDetalle} style={{ marginTop: 8 }}>
          + Agregar ítem
        </button>
      </label>

      <label>
        Observaciones
        <textarea value={obs} onChange={(e) => setObs(e.target.value)} placeholder="Observaciones (opcional)" />
      </label>

      <div className="sol-form-actions">
        <button type="button" className="btn-ghost" onClick={onCancelar} disabled={cargando}>Cancelar</button>
        <button type="submit" className="btn-primary" disabled={cargando}>
          {cargando ? "Guardando…" : "Crear Inventario"}
        </button>
      </div>
    </form>
  );
}
