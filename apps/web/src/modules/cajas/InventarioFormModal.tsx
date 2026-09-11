/**
 * InventarioFormModal — Modal de creación de inventario con dropdowns de personal.
 */

import { useState, type FormEvent } from "react";
import { createInventario, type InventarioDetalle, type Personal } from "../../api/cajasClient";

type Props = {
  tecnicos: Personal[];
  supervisores: Personal[];
  onGuardado: (inv: any) => void;
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
  const [detalle, setDetalle] = useState<Array<{ herramienta_codigo: string; cantidad: number; presente: boolean; observaciones: string }>>([
    { herramienta_codigo: "", cantidad: 1, presente: true, observaciones: "" },
  ]);

  const handleAddDetalle = () => {
    setDetalle([...detalle, { herramienta_codigo: "", cantidad: 1, presente: true, observaciones: "" }]);
  };

  const handleRemoveDetalle = (idx: number) => {
    if (detalle.length <= 1) return;
    setDetalle(detalle.filter((_, i) => i !== idx));
  };

  const handleDetalleChange = (idx: number, field: string, value: string | number | boolean) => {
    const newDetalle = [...detalle];
    (newDetalle[idx] as any)[field] = value;
    setDetalle(newDetalle);
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!cajaId || !periodo || !tecnicoId || !supervisorId) {
      setError("Todos los campos obligatorios son requeridos.");
      return;
    }
    if (detalle.some((d) => !d.herramienta_codigo || d.cantidad <= 0 || typeof d.presente !== "boolean")) {
      setError("Cada detalle requiere herramienta_codigo, cantidad > 0 y presente booleano.");
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
          herramienta_codigo: d.herramienta_codigo,
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

      {/* Detalle */}
      <label>
        Detalle de herramientas
        {detalle.map((d, idx) => (
          <div key={idx} className="sol-grid-3" style={{ marginTop: 8 }}>
            <label>
              Herramienta *
              <input value={d.herramienta_codigo} onChange={(e) => handleDetalleChange(idx, "herramienta_codigo", e.target.value)} placeholder="Código" />
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
        ))}
        <button type="button" className="btn-ghost btn-sm" onClick={handleAddDetalle} style={{ marginTop: 4 }}>
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
