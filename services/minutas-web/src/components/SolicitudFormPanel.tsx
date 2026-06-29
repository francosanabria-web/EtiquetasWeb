import { useState } from "react";
import type { SolicitudForm } from "../types/minuta";
import { URGENCIA_OPCIONES } from "../types/minuta";
import { validarSolicitud } from "../lib/validation";

type Props = {
  onSubmit: (data: SolicitudForm) => Promise<void>;
  disabled?: boolean;
};

const INITIAL: SolicitudForm = {
  numero_referencia: "",
  solicitante: "",
  urgencia: "media",
  cantidad_items: "1",
  descripcion: "",
};

export default function SolicitudFormPanel({ onSubmit, disabled }: Props) {
  const [form, setForm] = useState<SolicitudForm>(INITIAL);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [enviando, setEnviando] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const errs = validarSolicitud(form);
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setEnviando(true);
    try {
      await onSubmit(form);
      setForm(INITIAL);
      setErrors({});
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form className="form-panel" onSubmit={(e) => void handleSubmit(e)}>
      <h3>Nueva solicitud a compras</h3>
      <div className="form-grid">
        <label>
          Nº referencia *
          <input
            value={form.numero_referencia}
            disabled={disabled || enviando}
            onChange={(e) => setForm({ ...form, numero_referencia: e.target.value })}
            placeholder="PED-2026-001"
          />
          {errors.numero_referencia && (
            <span className="field-error">{errors.numero_referencia}</span>
          )}
        </label>
        <label>
          Solicitante *
          <input
            value={form.solicitante}
            disabled={disabled || enviando}
            onChange={(e) => setForm({ ...form, solicitante: e.target.value })}
          />
          {errors.solicitante && <span className="field-error">{errors.solicitante}</span>}
        </label>
        <label>
          Urgencia
          <select
            value={form.urgencia}
            disabled={disabled || enviando}
            onChange={(e) =>
              setForm({ ...form, urgencia: e.target.value as SolicitudForm["urgencia"] })
            }
          >
            {URGENCIA_OPCIONES.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Cant. ítems *
          <input
            type="number"
            min={1}
            value={form.cantidad_items}
            disabled={disabled || enviando}
            onChange={(e) => setForm({ ...form, cantidad_items: e.target.value })}
          />
          {errors.cantidad_items && (
            <span className="field-error">{errors.cantidad_items}</span>
          )}
        </label>
        <label className="span-2">
          Descripción
          <input
            value={form.descripcion}
            disabled={disabled || enviando}
            onChange={(e) => setForm({ ...form, descripcion: e.target.value })}
          />
        </label>
      </div>
      <button type="submit" className="btn-primary" disabled={disabled || enviando}>
        {enviando ? "Guardando…" : "Agregar solicitud"}
      </button>
    </form>
  );
}
