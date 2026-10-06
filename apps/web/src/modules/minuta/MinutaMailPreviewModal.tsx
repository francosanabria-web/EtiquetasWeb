import { useCallback, useState } from "react";

type Props = {
  asunto: string;
  cuerpoHtml: string;
  cuerpoTexto?: string;
  onClose: () => void;
};

export default function MinutaMailPreviewModal({ asunto, cuerpoHtml, cuerpoTexto, onClose }: Props) {
  // vista: 'html' = mail real (default), 'texto' = plano si hay cuerpoTexto
  const [vista, setVista] = useState<"html" | "texto">("html");

  const handleImprimir = useCallback(() => {
    const w = window.open(
      "",
      "_blank",
      "width=900,height=700,scrollbars=yes,resizable=yes",
    );
    if (!w) return;
    // Escapa asunto para <title>: reemplaza <>&"
    const escapeHtml = (s: string) =>
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
        };
      });
    const asuntoEscape = escapeHtml(asunto);
    w.document.write(
      `<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>${asuntoEscape}</title>
<style>@page{margin:12mm}body{margin:0;padding:12px}</style></head>
<body>${cuerpoHtml}</body></html>`,
    );
    w.document.close();
    w.focus();
    w.onload = () => {
      w.print();
    };
  }, [asunto, cuerpoHtml]);

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal" style={{ maxWidth: "1000px", maxHeight: "80vh" }}>
        <header>
          <h2>Vista previa / Imprimir minuta</h2>
          <button type="button" className="modal-close" onClick={onClose} aria-label="Cerrar">
            ×
          </button>
        </header>

        <div className="preview-tabs">
          <button
            type="button"
            className={vista === "html" ? "btn-primary" : "btn-ghost"}
            onClick={() => setVista("html")}
          >
            Mail real
          </button>
          {cuerpoTexto ? (
            <button
              type="button"
              className={vista === "texto" ? "btn-primary" : "btn-ghost"}
              onClick={() => setVista("texto")}
            >
              Texto
            </button>
          ) : null}
        </div>

        <div className="mail-html-preview">
          {vista === "html" ? (
            <iframe
              title="Vista mail real"
              srcDoc={cuerpoHtml}
              sandbox=""
              style={{
                width: "100%",
                height: 400,
                border: "1px solid #e2e8f0",
                borderRadius: 8,
                background: "#fff",
              }}
            />
          ) : (
            <pre
              style={{
                width: "100%",
                height: 400,
                overflow: "auto",
                border: "1px solid #e2e8f0",
                borderRadius: 8,
                background: "#f8fafc",
                padding: 12,
                fontSize: 12,
                whiteSpace: "pre-wrap",
              }}
            >
              {cuerpoTexto}
            </pre>
          )}
        </div>

        <button
          type="button"
          className="btn-ghost"
          style={{
            marginTop: 8,
            border: "none",
            background: "transparent",
            color: "var(--primary)",
            cursor: "pointer",
          }}
          onClick={handleImprimir}
        >
          🖨️ Imprimir / PDF
        </button>

        <button type="button" className="btn-ghost" onClick={onClose} style={{ marginTop: 8 }}>
          Cerrar
        </button>
      </div>
    </div>
  );
}