import { useEffect, useState } from "react";
import { previewEmail, enviarMinuta, ApiError } from "../api/client";
import { validarEmails } from "../lib/validation";

type Props = {
  sesionId: number;
  open: boolean;
  onClose: () => void;
  onEnviado: () => void;
};

export default function EnviarMinutaModal({ sesionId, open, onClose, onEnviado }: Props) {
  const [destinatarios, setDestinatarios] = useState("");
  const [asunto, setAsunto] = useState("");
  const [preview, setPreview] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setError(null);
    void previewEmail(sesionId)
      .then((p) => {
        setPreview(p.cuerpo_texto);
        setAsunto(p.asunto);
      })
      .catch((e) =>
        setError(e instanceof ApiError ? e.message : "No se pudo generar vista previa.")
      );
  }, [open, sesionId]);

  if (!open) return null;

  async function handleEnviar() {
    let emails: string[] = [];
    if (destinatarios.trim()) {
      const v = validarEmails(destinatarios);
      if (v.error) {
        setError(v.error);
        return;
      }
      emails = v.emails;
    }
    setBusy(true);
    setError(null);
    try {
      await enviarMinuta(sesionId, {
        destinatarios: emails,
        asunto: asunto.trim() || undefined,
      });
      onEnviado();
      onClose();
    } catch (e) {
      setError(
        e instanceof ApiError
          ? e.message
          : "Error al enviar. Verificá SMTP en el servidor."
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal">
        <header>
          <h2>Enviar minuta por correo</h2>
          <button type="button" className="modal-close" onClick={onClose} aria-label="Cerrar">
            ×
          </button>
        </header>
        <label>
          Destinatarios (separados por coma)
          <input
            value={destinatarios}
            onChange={(e) => setDestinatarios(e.target.value)}
            placeholder="compras@empresa.com, jefatura@empresa.com"
            disabled={busy}
          />
        </label>
        <label>
          Asunto
          <input value={asunto} onChange={(e) => setAsunto(e.target.value)} disabled={busy} />
        </label>
        <label>
          Vista previa
          <textarea readOnly rows={12} value={preview} className="preview-text" />
        </label>
        {error && <p className="banner error inline">{error}</p>}
        <p className="hint">
          Si SMTP no está configurado en el servidor, podés copiar la vista previa manualmente.
        </p>
        <footer className="modal-actions">
          <button type="button" className="btn-ghost" onClick={onClose} disabled={busy}>
            Cancelar
          </button>
          <button
            type="button"
            className="btn-primary"
            disabled={busy}
            onClick={() => void handleEnviar()}
          >
            {busy ? "Enviando…" : "Enviar minuta"}
          </button>
        </footer>
      </div>
    </div>
  );
}
