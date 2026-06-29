import { useState } from "react";
import type { TemaForm } from "../types/minuta";
import type { Tema } from "../types/minuta";
import { validarTema } from "../lib/validation";

type Props = {
  temas: Tema[];
  onCrear: (data: TemaForm) => Promise<void>;
  onToggle: (temaId: number, resuelto: boolean) => Promise<void>;
  readOnly?: boolean;
};

export default function TemasPanel({ temas, onCrear, onToggle, readOnly }: Props) {
  const [form, setForm] = useState<TemaForm>({ titulo: "", descripcion: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const errs = validarTema(form);
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setBusy(true);
    try {
      await onCrear(form);
      setForm({ titulo: "", descripcion: "" });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel temas">
      <h3>Otros temas a tratar</h3>
      <ul className="tema-list">
        {temas.map((t) => (
          <li key={t.id} className={t.resuelto ? "resuelto" : ""}>
            <label className="tema-check">
              <input
                type="checkbox"
                checked={t.resuelto}
                disabled={readOnly || busy}
                onChange={(e) => void onToggle(t.id, e.target.checked)}
              />
              <span>
                <strong>{t.titulo}</strong>
                {t.descripcion && <span className="muted"> — {t.descripcion}</span>}
              </span>
            </label>
          </li>
        ))}
        {!temas.length && <li className="muted">Sin temas adicionales.</li>}
      </ul>
      {!readOnly && (
        <form className="form-grid" onSubmit={(e) => void submit(e)}>
          <label className="span-2">
            Nuevo tema
            <input
              value={form.titulo}
              disabled={busy}
              onChange={(e) => setForm({ ...form, titulo: e.target.value })}
            />
            {errors.titulo && <span className="field-error">{errors.titulo}</span>}
          </label>
          <label className="span-2">
            Detalle
            <input
              value={form.descripcion}
              disabled={busy}
              onChange={(e) => setForm({ ...form, descripcion: e.target.value })}
            />
          </label>
          <button type="submit" className="btn-sm btn-primary" disabled={busy}>
            Agregar tema
          </button>
        </form>
      )}
    </section>
  );
}
