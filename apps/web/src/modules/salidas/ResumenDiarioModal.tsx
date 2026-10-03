import { useState, useMemo, useCallback } from "react";
import { fmtNum, fmtPesos, fetchResumenDiario, exportarDiario, type ResumenDiarioResult } from "../../api/salidasClient";

type Props = {
  open: boolean;
  onClose: () => void;
  defaultFecha?: string;
};

export default function ResumenDiarioModal({ open, onClose, defaultFecha }: Props) {
  const [fecha, setFecha] = useState(defaultFecha ?? "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ResumenDiarioResult | null>(null);

  async function handleCrear() {
    if (!fecha.trim()) {
      setError("Ingresá una fecha (AAAA-MM-DD).");
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetchResumenDiario(fecha.trim());
      setResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo cargar el resumen.");
    } finally {
      setLoading(false);
    }
  }

  const handleExportExcel = useCallback(async () => {
    if (!fecha.trim()) return;
    try {
      const blob = await exportarDiario(fecha.trim());
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `salidas_${fecha.trim()}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo exportar.");
    }
  }, [fecha]);

  const handlePrint = useCallback(() => {
    const el = document.querySelector(".print-resumen .resumen-print-area") as HTMLElement | null;
    if (!el) {
      window.print();
      return;
    }
    const w = window.open("", "_blank", "width=900,height=700");
    if (!w) {
      window.print();
      return;
    }
    // Copiar estilos relevantes
    const styleNodes = Array.from(document.querySelectorAll('style, link[rel="stylesheet"]')).map((n) => n.outerHTML).join("\n");
    const html = `<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Resumen diario ${fecha || ""}</title>${styleNodes}<style>
      body { margin:0; padding:24px; background:white; color:#0f172a; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }
      .print-header { background:#1F4E78; color:white; padding:14px 18px; border-radius:10px 10px 0 0; }
      table { width:100%; border-collapse:collapse; font-size:11px; }
      th { background:#1F4E78; color:white; padding:6px 8px; text-align:left; }
      td { padding:6px 8px; border:0.5px solid #e2e8f0; color:#000; }
      @media print { @page { margin: 12mm; } table { page-break-inside:auto; } tr { page-break-inside:avoid; } thead { display:table-header-group; } }
    </style></head><body>${el.innerHTML}<script>setTimeout(()=>{window.print(); window.onafterprint=()=>window.close();},300)<\/script></body></html>`;
    w.document.open();
    w.document.write(html);
    w.document.close();
    w.focus();
  }, [fecha]);

  const totalItems = useMemo(
    () => result?.grupos.reduce((acc, g) => acc + g.items.length, 0) ?? 0,
    [result],
  );

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Resumen diario por comprobante"
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
        className="print-resumen"
        style={{
          background: "var(--surface, #fff)",
          border: "0.5px solid var(--border, #e2e8f0)",
          borderRadius: 12,
          width: "min(800px, 96vw)",
          maxHeight: "92vh",
          overflow: "auto",
          boxShadow: "0 20px 60px rgba(0,0,0,0.22)",
        }}
      >
        {/* Header */}
        <div style={{ padding: "14px 16px 0", display: "flex", justifyContent: "space-between", gap: 12, alignItems: "start" }}>
          <div>
            <h2 style={{ margin: 0, fontFamily: "var(--font-display)", fontSize: "1.15rem" }}>Resumen diario por comprobante</h2>
            <p className="sub" style={{ margin: "4px 0 0" }}>
              Agrupa las bajas del dia segun tipo de comprobante (Pañol, L1-L7, Otros).
            </p>
          </div>
          <button type="button" className="btn-secondary no-print" onClick={onClose} aria-label="Cerrar" style={{ minHeight: 36 }}>
            ✕
          </button>
        </div>

        {/* Controls */}
        <div style={{ padding: 16, display: "flex", gap: 8, flexWrap: "wrap", alignItems: "flex-end", borderBottom: "0.5px solid var(--border)" }}>
          <label className="sal-field" style={{ margin: 0, minWidth: 200 }}>
            <span className="sal-muted">Fecha (AAAA-MM-DD)</span>
            <input
              type="date"
              value={fecha}
              onChange={(e) => { setFecha(e.target.value); setResult(null); setError(null); }}
              style={{ minWidth: 180 }}
            />
          </label>
          <button
            type="button"
            className="btn-primary no-print"
            onClick={() => void handleCrear()}
            disabled={loading}
            style={{ minHeight: 40 }}
          >
            {loading ? "Cargando…" : "Crear resumen"}
          </button>
          {result && result.grupos.length > 0 && (
            <>
              <button type="button" className="btn-secondary no-print" onClick={handlePrint} style={{ minHeight: 40 }}>
                🖨️ Imprimir
              </button>
              <button
                type="button"
                className="btn-secondary no-print"
                onClick={handleExportExcel}
                style={{ minHeight: 40 }}
              >
                📥 Exportar Excel
              </button>
            </>
          )}
        </div>

        {error && <p className="error" style={{ margin: "12px 16px 0", fontSize: "0.85rem" }}>{error}</p>}

        {/* Result - area que se imprime en ventana nueva */}
        <div className="resumen-print-area" style={{ padding: 16 }}>
          {result && result.grupos.length === 0 && (
            <p className="sub">Sin datos para la fecha seleccionada.</p>
          )}
          {result && result.grupos.length > 0 && (
            <>
              <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                {result.grupos.map((g) => (
                  <div key={g.linea} style={{ border: "0.5px solid var(--border)", borderRadius: 10, overflow: "hidden" }}>
                    <div style={{ background: "#1F4E78", color: "white", padding: "10px 14px", fontWeight: 700, fontSize: "0.95rem" }}>
                      {g.linea} — {g.cantidad} movimiento(s) · Total: {fmtPesos(g.total)}
                    </div>
                    <table className="sal-table" style={{ margin: 0 }}>
                      <thead>
                        <tr>
                          <th>Código</th>
                          <th>Descripción</th>
                          <th>Cant.</th>
                          <th>Monto</th>
                          <th>Orden</th>
                          <th>Operario</th>
                        </tr>
                      </thead>
                      <tbody>
                        {g.items.map((it, idx) => (
                          <tr key={`${it.codigo}-${idx}`}>
                            <td style={{ fontWeight: 600 }}>{it.codigo}</td>
                            <td>{it.descripcion}</td>
                            <td className="sal-num">{fmtNum(it.cantidad)}</td>
                            <td className="sal-num">{fmtPesos(it.monto)}</td>
                            <td>{it.numero_orden || "—"}</td>
                            <td>{it.operario || "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot>
                        <tr style={{ background: "#EAF0F7", fontWeight: 800 }}>
                          <td colSpan={3} style={{ textAlign: "right", padding: "8px 12px" }}>Subtotal {g.linea}:</td>
                          <td className="sal-num" style={{ padding: "8px 12px" }}>{fmtPesos(g.total)}</td>
                          <td colSpan={2} />
                        </tr>
                      </tfoot>
                    </table>
                  </div>
                ))}
              </div>

              {/* TOTAL DAY */}
              <div
                className="no-print"
                style={{
                  background: "#1F4E78",
                  color: "white",
                  borderRadius: 10,
                  padding: "14px 18px",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  fontWeight: 800,
                  fontSize: "1.05rem",
                  marginTop: 16,
                }}
              >
                <span>TOTAL DEL DÍA ({result.fecha})</span>
                <span>{fmtPesos(result.total_general)}</span>
              </div>
              <p className="sub" style={{ margin: "8px 0 0", textAlign: "center" }}>
                {totalItems} ítem(es) en {result.grupos.length} grupo(s) · {result.grupos.reduce((acc, g) => acc + g.items.length, 0)} movimientos
              </p>
            </>
          )}
        </div>

        {/* Estilos locales - sin hack de print, la impresion va por ventana nueva */}
        <style>{`
          @media print {
            .no-print { display: none !important; }
          }
        `}</style>
      </div>
    </div>
  );
}
