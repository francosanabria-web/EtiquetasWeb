/**
 * HerramientaFormModal — Modal de creación/edición de herramienta.
 */

import { useState, type FormEvent } from "react";
import { createHerramienta, updateHerramienta, type Herramienta } from "../../api/cajasClient";

type Props = {
  editing: Herramienta | null;
  onGuardado: (h: Herramienta) => void;
  onCancelar: () => void;
  token: string;
  cargando: boolean;
};

export default function HerramientaFormModal({ editing, onGuardado, onCancelar, token, cargando }: Props) {
  const [codigo, setCodigo] = useState(editing?.codigo ?? "");
  const [descripcion, setDescripcion] = useState(editing?.descripcion ?? "");
  const [categoria, setCategoria] = useState(editing?.categoria ?? "HERRAMIENTA");
  const [unidad, setUnidad] = useState(editing?.unidad ?? "UND");
  const [articuloCodigo, setArticuloCodigo] = useState(editing?.articulo_codigo ?? "");
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!codigo.trim()) {
      setError("El código es obligatorio.");
      return;
    }
    try {
      const data: Record<string, unknown> = {
        codigo: codigo.trim(),
        categoria,
        unidad,
        articulo_codigo: articuloCodigo.trim() || null,
      };
      if (descripcion.trim()) data.descripcion = descripcion.trim();
      else data.descripcion = null;

      if (editing) {
        const updated = await updateHerramienta(token, editing.id, data as Partial<Herramienta>);
        onGuardado(updated);
      } else {
        const created = await createHerramienta(token, data as Omit<Herramienta, "id">);
        onGuardado(created);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al guardar.");
    }
  };

  return (
    <form className="sol-form" onSubmit={handleSubmit}>
      <h2>{editing ? "Editar Herramienta" : "Nueva Herramienta"}</h2>
      {error && <p className="error" role="status">{error}</p>}
      <div className="sol-grid-2">
        <label>
          Código *
          <input value={codigo} onChange={(e) => setCodigo(e.target.value)} placeholder="Ej: ALIC001" required />
        </label>
        <label>
          Categoría
          <select value={categoria} onChange={(e) => setCategoria(e.target.value)}>
            <option value="HERRAMIENTA">Herramienta</option>
            <option value="REPUESTO">Repuesto</option>
            <option value="ACCESORIO">Accesorio</option>
            <option value="MEDIDA">Medida</option>
            <option value="OTRO">Otro</option>
          </select>
        </label>
      </div>
      <div className="sol-grid-2">
        <label>
          Unidad
          <select value={unidad} onChange={(e) => setUnidad(e.target.value)}>
            <option value="UND">UND</option>
            <option value="MT">MT</option>
            <option value="KG">KG</option>
            <option value="LT">LT</option>
            <option value="PS">PS</option>
          </select>
        </label>
        <label>
          Código Artículo
          <input value={articuloCodigo} onChange={(e) => setArticuloCodigo(e.target.value)} placeholder="Código artículo (opcional)" />
        </label>
      </div>
      <label>
        Descripción
        <input value={descripcion} onChange={(e) => setDescripcion(e.target.value)} placeholder="Descripción (opcional)" />
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
