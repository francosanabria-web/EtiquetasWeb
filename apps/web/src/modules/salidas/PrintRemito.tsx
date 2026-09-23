import { fmtNum, fmtPesos } from "../../api/salidasClient";
import type { ItemPendiente } from "../../api/salidasClient";

type RemitoData = {
  fecha: string;
  numero_orden: string | number;
  tipo_comprobante: string;
  sector: string;
  operario: string;
  maquina?: string;
  items: Array<{
    codigo: string;
    descripcion: string;
    ubicacion: string;
    cantidad: number;
    precio_unitario: number;
    monto: number;
  }>;
};

type Props = {
  data: RemitoData;
  onClose?: () => void;
};

export default function PrintRemito({ data, onClose }: Props) {
  const total = data.items.reduce((acc, it) => acc + Math.abs(it.monto), 0);
  const fechaFmt = data.fecha || new Date().toLocaleDateString("es-AR");

  return (
    <div className="print-remito-overlay" role="dialog" aria-modal="true" aria-label="Remito de salida">
      <style>{`
        @media print {
          body * { visibility: hidden; }
          .print-remito, .print-remito * { visibility: visible; }
          .print-remito { position: absolute; left: 0; top: 0; width: 100%; margin: 0; padding: 16px; background: white; }
          .no-print { display: none !important; }
        }
        .print-remito {
          background: white;
          color: #0f172a;
          border: 0.5px solid #e2e8f0;
          border-radius: 12px;
          overflow: hidden;
        }
        .print-remito-header {
          background: #1F4E78;
          color: white;
          padding: 14px 18px;
          text-align: center;
          font-weight: 800;
          letter-spacing: 0.02em;
        }
        .print-remito-sub {
          background: #f1f5f9;
          padding: 10px 18px;
          text-align: center;
          font-weight: 700;
          font-size: 0.92rem;
          border-bottom: 0.5px solid #e2e8f0;
        }
        .print-remito-meta {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 10px;
          padding: 12px 18px;
          border-bottom: 0.5px solid #e2e8f0;
        }
        .print-remito-meta label { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.03em; color: #64748b; display: block; margin-bottom: 2px; }
        .print-remito-meta strong { font-size: 0.92rem; }
        .print-remito table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
        .print-remito th { background: #1F4E78; color: white; padding: 8px 10px; text-align: left; font-size: 0.72rem; text-transform: uppercase; }
        .print-remito td { padding: 8px 10px; border-bottom: 0.5px solid #e2e8f0; }
        .print-remito .num { text-align: right; font-variant-numeric: tabular-nums; }
        .print-remito-total { display: flex; justify-content: flex-end; gap: 12px; padding: 12px 18px; background: #EAF0F7; font-weight: 800; border-top: 1px solid #1F4E78; }
        .print-remito-firmas { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; padding: 18px; }
        .print-remito-firma { border: 0.5px solid #cbd5e1; border-radius: 8px; min-height: 90px; display: flex; flex-direction: column; }
        .print-remito-firma-head { background: #f8fafc; padding: 8px 12px; text-align: center; font-size: 0.78rem; font-weight: 700; color: #475569; border-bottom: 0.5px solid #e2e8f0; }
        .print-remito-firma-body { flex: 1; display: flex; align-items: flex-end; justify-content: center; padding: 8px 12px 14px; color: #94a3b8; font-size: 0.75rem; }
        .print-remito-footer { text-align: center; padding: 10px 18px; font-size: 0.7rem; color: #94a3b8; border-top: 0.5px solid #e2e8f0; }
      `}</style>

      <div style={{ position: "fixed", inset: 0, background: "rgba(15,23,42,0.48)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 70, padding: 16 }} onClick={onClose}>
        <div style={{ width: "min(840px, 96vw)", maxHeight: "94vh", overflow: "auto" }} onClick={(e) => e.stopPropagation()}>
          <div className="no-print" style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginBottom: 10 }}>
            <button type="button" className="btn-secondary" onClick={onClose} style={{ minHeight: 40 }}>
              Cerrar
            </button>
            <button type="button" className="btn-primary" onClick={() => window.print()} style={{ minHeight: 40 }}>
              🖨️ Imprimir / PDF
            </button>
          </div>

          <div className="print-remito">
            <div className="print-remito-header">PAÑOL — COMPROBANTE DE SALIDA / REMITO</div>
            <div className="print-remito-sub">
              Nº ORDEN: {data.numero_orden || "—"} &nbsp;•&nbsp; FECHA: {fechaFmt} &nbsp;•&nbsp; COMPROBANTE: {data.tipo_comprobante || "—"}
            </div>
            <div className="print-remito-meta">
              <div>
                <label>Sector</label>
                <strong>{data.sector || "—"}</strong>
              </div>
              <div>
                <label>Operario</label>
                <strong>{data.operario || "—"}</strong>
              </div>
              <div>
                <label>Máquina / Sitio</label>
                <strong>{data.maquina || "—"}</strong>
              </div>
            </div>

            <table>
              <thead>
                <tr>
                  <th>Código</th>
                  <th>Descripción</th>
                  <th>Ubicación</th>
                  <th className="num">Cant.</th>
                  <th className="num">P. unit.</th>
                  <th className="num">Monto</th>
                </tr>
              </thead>
              <tbody>
                {data.items.length === 0 ? (
                  <tr>
                    <td colSpan={6} style={{ textAlign: "center", color: "#94a3b8", padding: "18px 12px" }}>
                      Sin ítems
                    </td>
                  </tr>
                ) : (
                  data.items.map((it, idx) => (
                    <tr key={`${it.codigo}-${idx}`}>
                      <td style={{ fontWeight: 700 }}>{it.codigo}</td>
                      <td>{it.descripcion}</td>
                      <td>{it.ubicacion || "—"}</td>
                      <td className="num">{fmtNum(it.cantidad)}</td>
                      <td className="num">{fmtPesos(it.precio_unitario)}</td>
                      <td className="num">{fmtPesos(it.monto)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>

            <div className="print-remito-total">
              <span>TOTAL</span>
              <span>{fmtPesos(total)}</span>
            </div>

            <div className="print-remito-firmas">
              <div className="print-remito-firma">
                <div className="print-remito-firma-head">Retiró (firma y aclaración)</div>
                <div className="print-remito-firma-body"> </div>
              </div>
              <div className="print-remito-firma">
                <div className="print-remito-firma-head">Entregó — Pañol (firma)</div>
                <div className="print-remito-firma-body"> </div>
              </div>
            </div>

            <div className="print-remito-footer">
              Generado: {new Date().toLocaleString("es-AR")} • Sistema Pañol — Salidas
            </div>
          </div>

          <div className="no-print" style={{ display: "flex", justifyContent: "center", gap: 8, marginTop: 12 }}>
            <button type="button" className="btn-primary" onClick={() => window.print()} style={{ minHeight: 44, flex: 1 }}>
              🖨️ Imprimir / Guardar PDF
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// Helper para mapear ItemPendiente -> Remito items
export function pendientesToRemito(
  pendientes: ItemPendiente[],
  cabecera: { fecha: string; numero_orden: string | number; tipo_comprobante: string; sector: string; operario: string; maquina: string },
): RemitoData {
  return {
    fecha: cabecera.fecha,
    numero_orden: cabecera.numero_orden,
    tipo_comprobante: cabecera.tipo_comprobante,
    sector: cabecera.sector,
    operario: cabecera.operario,
    maquina: cabecera.maquina,
    items: pendientes.map((p) => ({
      codigo: p.codigo,
      descripcion: p.descripcion,
      ubicacion: p.ubicacion,
      cantidad: p.cantidad,
      precio_unitario: p.precio_unitario,
      monto: p.monto,
    })),
  };
}
