import type { PedidoGrupo } from "../types/minuta";

type Props = {
  pedido: PedidoGrupo | null;
  readOnly?: boolean;
  operador: string;
  onClose: () => void;
  onNota?: (filaId: number, texto: string) => Promise<void>;
};

export default function PedidoDetalleModal({
  pedido,
  readOnly,
  operador,
  onClose,
  onNota,
}: Props) {
  if (!pedido) return null;

  const cab = pedido.filas[0];

  return (
    <div className="modal-backdrop" onClick={onClose} role="presentation">
      <div
        className="modal modal-wide"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-labelledby="pedido-detalle-titulo"
      >
        <header>
          <div>
            <h2 id="pedido-detalle-titulo">{pedido.ref_pedido}</h2>
            <p className="sub">
              Solicitud del {pedido.fecha_solicitud || "—"} · {pedido.solicitante} ·{" "}
              {pedido.tipo_solicitud}
            </p>
          </div>
          <button type="button" className="modal-close" onClick={onClose} aria-label="Cerrar">
            ×
          </button>
        </header>

        <section className="pedido-resumen-grid">
          <div>
            <span className="meta-label">Fecha solicitud</span>
            <strong>{pedido.fecha_solicitud || "—"}</strong>
          </div>
          <div>
            <span className="meta-label">Solicitante</span>
            <strong>{pedido.solicitante}</strong>
          </div>
          <div>
            <span className="meta-label">Tipo</span>
            <strong>{pedido.tipo_solicitud}</strong>
          </div>
          <div>
            <span className="meta-label">Máquina / línea</span>
            <strong>{pedido.maquina_linea || "—"}</strong>
          </div>
          <div>
            <span className="meta-label">Nº Odoo / Nº solicitud</span>
            <strong>{pedido.ref_pedido}</strong>
          </div>
          <div>
            <span className="meta-label">Almacenista</span>
            <strong>{cab?.almacenista || "—"}</strong>
          </div>
          <div>
            <span className="meta-label">Estado solicitud (X)</span>
            <strong>{pedido.estado_solicitud}</strong>
          </div>
          <div>
            <span className="meta-label">Ítems en pedido</span>
            <strong>{pedido.cantidad_filas}</strong>
          </div>
        </section>

        <div className="table-scroll">
          <table className="data-table compact">
            <thead>
              <tr>
                <th>Código</th>
                <th>Descripción</th>
                <th>Cant.</th>
                <th>Unid.</th>
                <th>Precio</th>
                <th>Total</th>
                <th>Moneda</th>
                <th>Proveedor</th>
                <th>OC/RQ</th>
                <th>Fecha OC</th>
                <th>Comprador</th>
                <th>Envío compras</th>
                <th>Est. ítem (W)</th>
                <th>Est. sol. (X)</th>
              </tr>
            </thead>
            <tbody>
              {pedido.filas.map((f) => (
                <tr key={f.id}>
                  <td>{f.codigo}</td>
                  <td>{f.descripcion}</td>
                  <td>{f.cantidad}</td>
                  <td>{f.unidad}</td>
                  <td>{f.precio}</td>
                  <td>{f.total}</td>
                  <td>{f.moneda}</td>
                  <td>{f.proveedor}</td>
                  <td>{f.oc_rq}</td>
                  <td>{f.fecha_oc}</td>
                  <td>{f.comprador}</td>
                  <td>{f.fecha_envio_compras}</td>
                  <td>{f.estado_item}</td>
                  <td>{f.estado_solicitud}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {!readOnly && onNota && (
          <p className="hint">
            Para anotar cambios de reunión, usá la tabla principal. Operador: {operador || "sin nombre"}.
          </p>
        )}
      </div>
    </div>
  );
}
