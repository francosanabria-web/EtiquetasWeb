import { useEffect, useMemo, useRef, useState } from "react";
import { crearAtencion, hoyIsoLocal } from "../../api/salidasClient";

type Props = {
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
  usuarioActual?: string | null;
};

export default function AtencionModal({ open, onClose, onSaved, usuarioActual }: Props) {
  const [conRetiro, setConRetiro] = useState<boolean>(true);
  const [observaciones, setObservaciones] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fechaHoy = useMemo(() => hoyIsoLocal(), [open]);
  const obsRef = useRef<HTMLTextAreaElement>(null);
  const atendidoPor = (usuarioActual || "").trim().toUpperCase() || "—";

  useEffect(() => {
    if (!open) return;
    setConRetiro(true);
    setObservaciones("");
    setError(null);
    const t = window.setTimeout(() => obsRef.current?.focus(), 60);
    return () => window.clearTimeout(t);
  }, [open]);

  const canSave = useMemo(() => {
    if (observaciones.length > 500) return false;
    return true;
  }, [observaciones]);

  async function handleSubmit(e?: React.FormEvent) {
    e?.preventDefault();
    if (!canSave || saving) return;
    setError(null);
    setSaving(true);
    try {
      await crearAtencion({
        fecha: fechaHoy,
        con_retiro: conRetiro,
        observaciones: observaciones.trim() || null,
        atendido_por: atendidoPor !== "—" ? atendidoPor : undefined,
      });
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo guardar.");
    } finally {
      setSaving(false);
    }
  }

  useEffect(() => {
    if (!open) return;
    function onKey(ev: KeyboardEvent) {
      if (ev.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Registrar atención de ventanilla"
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(15,23,42,0.48)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 60,
        padding: 16,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "var(--surface, #fff)",
          border: "0.5px solid var(--border, #e2e8f0)",
          borderRadius: 12,
          width: "min(520px, 96vw)",
          maxHeight: "92vh",
          overflow: "auto",
          boxShadow: "0 20px 60px rgba(0,0,0,0.22)",
        }}
      >
        <div style={{ padding: "14px 16px 0", display: "flex", justifyContent: "space-between", gap: 12, alignItems: "start" }}>
          <div>
            <h2 style={{ margin: 0, fontFamily: "var(--font-display)", fontSize: "1.15rem" }}>Atención ventanilla</h2>
            <p className="sub" style={{ margin: "4px 0 0" }}>
              Minimal · 5–10 seg · Fecha + ¿retiró? + observaciones. Esc cierra, Enter guarda.
            </p>
          </div>
          <button type="button" className="btn-secondary" onClick={onClose} aria-label="Cerrar" style={{ minHeight: 36 }}>
            ✕
          </button>
        </div>

        <form onSubmit={(e) => void handleSubmit(e)} style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            <label className="sal-field" style={{ margin: 0 }}>
              <span className="sal-muted">Fecha</span>
              <input value={fechaHoy} readOnly aria-label="Fecha" style={{ background: "var(--bg)" }} />
            </label>
            <label className="sal-field" style={{ margin: 0 }}>
              <span className="sal-muted">Atendido por</span>
              <input value={atendidoPor} readOnly aria-label="Atendido por" style={{ background: "var(--bg)" }} />
            </label>
          </div>

          <div>
            <span className="sal-muted" style={{ display: "block", marginBottom: 6 }}>
              ¿Retiró material físico? *
            </span>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
              <button
                type="button"
                onClick={() => setConRetiro(true)}
                aria-pressed={conRetiro}
                style={{
                  minHeight: 48,
                  borderRadius: 10,
                  border: conRetiro ? "1.5px solid #16a34a" : "0.5px solid var(--border)",
                  background: conRetiro ? "#16a34a" : "var(--bg)",
                  color: conRetiro ? "#fff" : "var(--text)",
                  fontWeight: 700,
                  fontSize: "0.95rem",
                  cursor: "pointer",
                }}
              >
                ✓ SÍ — fuera sistema
              </button>
              <button
                type="button"
                onClick={() => setConRetiro(false)}
                aria-pressed={!conRetiro}
                style={{
                  minHeight: 48,
                  borderRadius: 10,
                  border: !conRetiro ? "1.5px solid #dc2626" : "0.5px solid var(--border)",
                  background: !conRetiro ? "#dc2626" : "var(--bg)",
                  color: !conRetiro ? "#fff" : "var(--text)",
                  fontWeight: 700,
                  fontSize: "0.95rem",
                  cursor: "pointer",
                }}
              >
                ✕ NO — sin stock
              </button>
            </div>
            <p className="sub" style={{ margin: "6px 0 0", fontSize: "0.78rem" }}>
              {conRetiro ? "Retiró stock FUERA DE SISTEMA (no del maestro)." : "No hubo stock de lo solicitado."}
            </p>
          </div>

          <label className="sal-field">
            <span className="sal-muted">Observaciones ({observaciones.length}/500) — opcional</span>
            <textarea
              ref={obsRef}
              value={observaciones}
              onChange={(e) => setObservaciones(e.target.value.slice(0, 500))}
              rows={3}
              placeholder={conRetiro ? "Ej: Retiró 2 tornillos M8 fuera de sistema para línea 3." : "Ej: Solicitaron grampas, sin stock, se avisó a compras."}
              aria-label="Observaciones"
              style={{
                font: "inherit",
                color: "var(--text)",
                background: "var(--bg)",
                border: "0.5px solid var(--border)",
                borderRadius: 8,
                padding: "10px 12px",
                resize: "vertical",
              }}
            />
          </label>

          {error && (
            <p className="error" role="alert" style={{ margin: 0 }}>
              {error}
            </p>
          )}

          <div style={{ display: "flex", gap: 8, marginTop: 4, flexWrap: "wrap" }}>
            <button type="submit" className="btn-primary" disabled={!canSave || saving} style={{ flex: 1, minHeight: 44 }}>
              {saving ? "Guardando…" : "Guardar atención (Enter)"}
            </button>
            <button type="button" className="btn-secondary" onClick={onClose} disabled={saving} style={{ minHeight: 44 }}>
              Cancelar (Esc)
            </button>
          </div>
          <p className="sub" style={{ margin: 0, fontSize: "0.78rem" }}>
            Tip: F2 abre este modal sin salir de Salidas. Solo guarda fecha, con_retiro y observaciones.
          </p>
        </form>
      </div>
    </div>
  );
}
