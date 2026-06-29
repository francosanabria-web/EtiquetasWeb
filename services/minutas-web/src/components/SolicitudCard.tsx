import { useState } from "react";
import type { Solicitud } from "../types/minuta";
import {
  ESTADO_ENTREGA_LABEL,
  URGENCIA_LABEL,
} from "../types/minuta";
import type { EntregaForm } from "../types/minuta";
import {
  cantidadPendiente,
  sumEntregas,
  validarEntrega,
  hoyIso,
} from "../lib/validation";

type Props = {
  solicitud: Solicitud;
  sesionId: number;
  autorDefault?: string;
  onEntrega: (
    solicitudId: number,
    data: { fecha: string; cantidad: number; observacion?: string }
  ) => Promise<void>;
  onActualizacion: (
    solicitudId: number,
    data: { texto: string; autor?: string }
  ) => Promise<void>;
  onCerrar: (solicitudId: number) => Promise<void>;
  readOnly?: boolean;
};

export default function SolicitudCard({
  solicitud: s,
  autorDefault = "",
  onEntrega,
  onActualizacion,
  onCerrar,
  readOnly,
}: Props) {
  const [expandido, setExpandido] = useState(false);
  const [nota, setNota] = useState("");
  const [entrega, setEntrega] = useState<EntregaForm>({
    fecha: hoyIso(),
    cantidad: "1",
    observacion: "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  const entregado = sumEntregas(s.entregas);
  const pendiente = cantidadPendiente(s.cantidad_items, entregado);

  async function submitEntrega(e: React.FormEvent) {
    e.preventDefault();
    const errs = validarEntrega(entrega, pendiente);
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setBusy(true);
    try {
      await onEntrega(s.id, {
        fecha: entrega.fecha,
        cantidad: parseInt(entrega.cantidad, 10),
        observacion: entrega.observacion.trim() || undefined,
      });
      setEntrega({ fecha: hoyIso(), cantidad: "1", observacion: "" });
      setExpandido(true);
    } finally {
      setBusy(false);
    }
  }

  async function submitNota(e: React.FormEvent) {
    e.preventDefault();
    if (!nota.trim()) return;
    setBusy(true);
    try {
      await onActualizacion(s.id, {
        texto: nota.trim(),
        autor: autorDefault.trim() || undefined,
      });
      setNota("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className={`sol-card urg-${s.urgencia}${s.cerrado ? " cerrada" : ""}`}>
      <header className="sol-head" onClick={() => setExpandido((v) => !v)}>
        <div>
          <strong className="ref">{s.numero_referencia}</strong>
          <span className="sol-meta">
            {s.solicitante} · {URGENCIA_LABEL[s.urgencia]}
          </span>
        </div>
        <div className="sol-badges">
          <span className={`badge estado-${s.estado_entrega}`}>
            {ESTADO_ENTREGA_LABEL[s.estado_entrega]}
          </span>
          <span className="badge qty">
            {entregado}/{s.cantidad_items} ítems
          </span>
        </div>
      </header>

      {s.descripcion && <p className="sol-desc">{s.descripcion}</p>}

      {expandido && (
        <div className="sol-body">
          <details open className="entregas-panel">
            <summary>Entregas parciales ({s.entregas.length})</summary>
            {s.entregas.length === 0 ? (
              <p className="muted">Sin entregas registradas.</p>
            ) : (
              <ul className="entrega-list">
                {s.entregas.map((e) => (
                  <li key={e.id}>
                    <strong>{e.fecha}</strong> — {e.cantidad} u.
                    {e.observacion ? ` · ${e.observacion}` : ""}
                  </li>
                ))}
              </ul>
            )}
            {!readOnly && !s.cerrado && pendiente > 0 && (
              <form className="inline-form" onSubmit={(e) => void submitEntrega(e)}>
                <label>
                  Fecha
                  <input
                    type="date"
                    value={entrega.fecha}
                    disabled={busy}
                    onChange={(ev) => setEntrega({ ...entrega, fecha: ev.target.value })}
                  />
                </label>
                <label>
                  Cantidad (máx {pendiente})
                  <input
                    type="number"
                    min={1}
                    max={pendiente}
                    value={entrega.cantidad}
                    disabled={busy}
                    onChange={(ev) => setEntrega({ ...entrega, cantidad: ev.target.value })}
                  />
                  {errors.cantidad && <span className="field-error">{errors.cantidad}</span>}
                </label>
                <label>
                  Observación
                  <input
                    value={entrega.observacion}
                    disabled={busy}
                    onChange={(ev) =>
                      setEntrega({ ...entrega, observacion: ev.target.value })
                    }
                  />
                </label>
                <button type="submit" className="btn-sm btn-primary" disabled={busy}>
                  Registrar entrega
                </button>
              </form>
            )}
          </details>

          {s.actualizaciones.length > 0 && (
            <div className="acts-block">
              <h4>Actualizaciones de esta reunión</h4>
              <ul>
                {s.actualizaciones.map((a) => (
                  <li key={a.id}>
                    {a.autor && <em>{a.autor}: </em>}
                    {a.texto}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {!readOnly && !s.cerrado && (
            <form className="nota-form" onSubmit={(e) => void submitNota(e)}>
              <textarea
                rows={2}
                placeholder="Actualización para compras / minuta…"
                value={nota}
                disabled={busy}
                onChange={(e) => setNota(e.target.value)}
              />
              <button type="submit" className="btn-sm btn-ghost" disabled={busy || !nota.trim()}>
                Agregar nota
              </button>
            </form>
          )}

          {!readOnly && !s.cerrado && (
            <button
              type="button"
              className="btn-sm btn-danger-link"
              disabled={busy}
              onClick={() => void onCerrar(s.id)}
            >
              Dar de baja seguimiento
            </button>
          )}
        </div>
      )}
    </article>
  );
}
