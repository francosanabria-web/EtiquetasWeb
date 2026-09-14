/**
 * PersonalFormModal — Modal de creación/edición de personal.
 */

import { useState, type FormEvent } from "react";
import { createPersonal, updatePersonal, type Personal } from "../../api/personalClient";
import type { Area } from "../../api/personalClient";

type Props = {
  areas: Area[];
  editing: Personal | null;
  onGuardado: (p: Personal) => void;
  onCancelar: () => void;
  token: string;
  cargando: boolean;
};

export default function PersonalFormModal({ areas, editing, onGuardado, onCancelar, token, cargando }: Props) {
  const [nombre, setNombre] = useState(editing?.nombre ?? "");
  const [legajo, setLegajo] = useState(editing?.legajo ?? "");
  const [email, setEmail] = useState(editing?.email ?? "");
  const [areaId, setAreaId] = useState<number | "">((editing?.area_id as number) ?? "");
  const [tipo, setTipo] = useState(editing?.tipo ?? "tecnico");
  const [activo, setActivo] = useState(editing?.activo ?? true);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!nombre.trim()) {
      setError("El nombre es obligatorio.");
      return;
    }
    try {
      const data: Record<string, unknown> = { nombre: nombre.trim(), tipo, activo };
      if (legajo.trim()) data.legajo = legajo.trim();
      if (email.trim()) data.email = email.trim();
      if (areaId !== "") data.area_id = areaId;

      if (editing) {
        const updated = await updatePersonal(token, editing.id, data);
        onGuardado(updated);
      } else {
        const created = await createPersonal(token, {
          nombre: nombre.trim(),
          legajo: legajo.trim() || null,
          email: email.trim() || null,
          area_id: areaId !== "" ? areaId : null,
          tipo: tipo as Personal["tipo"],
          activo,
        });
        onGuardado(created);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al guardar.");
    }
  };

  return (
    <form className="sol-form" onSubmit={handleSubmit}>
      <h2>{editing ? "Editar Personal" : "Nuevo Personal"}</h2>
      {error && <p className="error" role="status">{error}</p>}
      <div className="sol-grid-2">
        <label>
          Nombre *
          <input value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Nombre completo" required />
        </label>
        <label>
          Tipo *
          <select value={tipo} onChange={(e) => setTipo(e.target.value as typeof tipo)}>
            <option value="tecnico">Técnico</option>
            <option value="supervisor">Supervisor</option>
            <option value="produccion">Producción</option>
            <option value="generico">Genérico</option>
            <option value="panol">Pañol</option>
          </select>
        </label>
      </div>
      <div className="sol-grid-2">
        <label>
          Legajo
          <input value={legajo} onChange={(e) => setLegajo(e.target.value)} placeholder="Número de legajo" />
        </label>
        <label>
          Email
          <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" />
        </label>
      </div>
      <label>
        Área
        <select value={areaId} onChange={(e) => setAreaId(Number(e.target.value))}>
          <option value="">— Sin área —</option>
          {areas.map((a) => (
            <option key={a.id} value={a.id}>{a.nombre}</option>
          ))}
        </select>
      </label>
      <label className="sol-check">
        <input type="checkbox" checked={activo} onChange={(e) => setActivo(e.target.checked)} />
        <span>Activo</span>
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
