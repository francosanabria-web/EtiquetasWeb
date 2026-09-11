/**
 * CajaFormModal — Modal de creación/edición de caja.
 */

import { useState, type FormEvent } from "react";
import { createCaja, updateCaja, type Caja } from "../../api/cajasClient";

type Props = {
  editing: Caja | null;
  onGuardado: (c: Caja) => void;
  onCancelar: () => void;
  token: string;
  cargando: boolean;
};

export default function CajaFormModal({ editing, onGuardado, onCancelar, token, cargando }: Props) {
  const [codigo, setCodigo] = useState(editing?.codigo ?? "");
  const [descripcion, setDescripcion] = useState(editing?.descripcion ?? "");
  const [ubicacion, setUbicacion] = useState(editing?.ubicacion ?? "");
  const [activa, setActiva] = useState(editing?.activa ?? true);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!codigo.trim()) {
      setError("El código es obligatorio.");
      return;
    }
    try {
      const data: Record<string, unknown> = { codigo: codigo.trim(), activa };
      if (descripcion.trim()) data.descripcion = descripcion.trim();
      else data.descripcion = null;
      if (ubicacion.trim()) data.ubicacion = ubicacion.trim();
      else data.ubicacion = null;

      if (editing) {
        const updated = await updateCaja(token, editing.id, data as Partial<Caja>);
        onGuardado(updated);
      } else {
        const created = await createCaja(token, data as Omit<Caja, "id">);
        onGuardado(created);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al guardar.");
    }
  };

  return (
    <form className="sol-form" onSubmit={handleSubmit}>
      <h2>{editing ? "Editar Caja" : "Nueva Caja"}</h2>
      {error && <p className="error" role="status">{error}</p>}
      <div className="sol-grid-2">
        <label>
          Código *
          <input value={codigo} onChange={(e) => setCodigo(e.target.value)} placeholder="Ej: HERR001" required />
        </label>
        <label>
          Activa
          <input type="checkbox" checked={activa} onChange={(e) => setActiva(e.target.checked)} />
        </label>
      </div>
      <label>
        Descripción
        <input value={descripcion} onChange={(e) => setDescripcion(e.target.value)} placeholder="Descripción (opcional)" />
      </label>
      <label>
        Ubicación
        <input value={ubicacion} onChange={(e) => setUbicacion(e.target.value)} placeholder="Ubicación (opcional)" />
      </label>
      <div className="sol-form-actions">
        <button type="button" className="btn-ghost" onClick={onCancelar} disabled={cargando}>Cancelar</button>
        <button type="submit" className="btn-primary" disabled={cargando}>
          {cargando ? "Guardando…" : editing ? "Actualizar" : "Crear"}
        </button>
      </div>
    </form>
  );
}
