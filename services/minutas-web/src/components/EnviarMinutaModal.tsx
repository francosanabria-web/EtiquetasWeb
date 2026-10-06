import { useCallback, useEffect, useState } from "react";
import { previewEmail, enviarMinuta, ApiError } from "../api/client";
import { validarEmails } from "../lib/validation";

type PreviewData = {
  cuerpo_texto: string;
  cuerpo_html: string;
  asunto: string;
};

type Props = {
  sesionId: number;
  open: boolean;
  onClose: () => void;
  onEnviado: () => void;
};

export default function EnviarMinutaModal({ sesionId, open, onClose, onEnviado }: Props) {
  const [destinatarios, setDestinatarios] = useState("");
  const [asunto, setAsunto] = useState("");

  const escapeTitulo = useCallback((s: string) =>
    s.replace(/[<>&"]/g, (c) => {
      switch (c) {
        case "<":
          return "<";
        case ">":
          return ">";
        case "&":
          return "&";
        case '"':
          return String.fromCharCode(34);
        default:
          return c;
      }
    }),
  []);
  const [previewTexto, setPreviewTexto] = useState("");
  const [previewHtml, setPreviewHtml] = useState("");
  const [vistaActual, setVistaActual] = useState<"texto" | "html">("texto");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setError(null);
    void previewEmail(sesionId)
      .then((p: PreviewData) => {
        setPreviewTexto(p.cuerpo_texto);
        setPreviewHtml(p.cuerpo_html);
        setAsunto(p.asunto);
        setVistaActual("texto");
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
          <div className="preview-tabs">
            <button
              className={vistaActual === "texto" ? "btn-primary" : "btn-ghost"}
              onClick={() => setVistaActual("texto")}
            >
              Texto
            </button>
            <button
              className={vistaActual === "html" ? "btn-primary" : "btn-ghost"}
              onClick={() => setVistaActual("html")}
            >
              Mail real
            </button>
          </div>
          {vistaActual === "texto" ? (
            <textarea
              readOnly
              rows={12}
              value={previewTexto}
              className="preview-text"
            />
          ) : (
            <iframe
              srcDoc={previewHtml}
              sandbox=""
              style={{
                width: "100%",
                height: 400,
                border: "1px solid #e2e8f0",
                borderRadius: 8,
                background: "#fff",
                fontFamily: "inherit",
              }}
            />
          )}
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
        {/* Botón de imprimir visible solo en vista HTML */}
        {vistaActual === "html" && !busy && (
          <button
            type="button"
            className="btn-ghost"
            style={{ marginTop: 8, border: "none", background: "transparent", color: "var(--primary)", cursor: "pointer" }}
            onClick={() => {
              // Abrir ventana nueva con documento completo y imprimir
              const printWindow = window.open(
                "",
                "_blank",
                "width=900,height=700,scrollbars=yes,resizable=yes",
              );
              if (!printWindow) return;
              const html = `
                <html>
                  <head>
                    <meta charset="UTF-8">
                    <title>${escapeTitulo(asunto)}</title>
                    <style>
                      @page { margin: 12mm; }
                      @media print { body { margin: 0; } }
                      body { font-family: inherit; padding: 12px; }
                    </style>
                  </head>
                  <body>${previewHtml}</body>
                </html>
              `;
              printWindow.document.write(html);
              printWindow.document.close();
              printWindow.onload = () => {
                printWindow.print();
              };
            }}
          >
            🖨️ Imprimir / PDF
          </button>
        )}
      </div>
    </div>
  );
}
