import { useEffect, useMemo, useState } from "react";
import type { PedidoGrupo } from "../types/minuta";
import PedidoDetalleModal from "./PedidoDetalleModal";

type Props = {
  sesionId: number;
  pedidos: PedidoGrupo[];
  operador: string;
  readOnly?: boolean;
  onConfirmarSeleccion: (refs: string[]) => Promise<void>;
  onNota: (filaId: number, texto: string) => Promise<void>;
};

function storageKey(sesionId: number) {
  return `minutas-refs-${sesionId}`;
}

function leerFiltroGuardado(sesionId: number): { solo: boolean; refs: string[] } | null {
  try {
    const raw = sessionStorage.getItem(storageKey(sesionId));
    if (!raw) return null;
    const p = JSON.parse(raw) as { solo?: boolean; refs?: string[] };
    if (p.solo && Array.isArray(p.refs) && p.refs.length) {
      return { solo: true, refs: p.refs };
    }
  } catch {
    /* ignore */
  }
  return null;
}

export default function PedidosReunionPanel({
  sesionId,
  pedidos,
  operador,
  readOnly,
  onConfirmarSeleccion,
  onNota,
}: Props) {
  const guardado = leerFiltroGuardado(sesionId);
  const [borrador, setBorrador] = useState<Set<string>>(new Set());
  const [refsTrabajo, setRefsTrabajo] = useState<string[] | null>(() => guardado?.refs ?? null);
  const [soloSeleccionadas, setSoloSeleccionadas] = useState(() => !!guardado?.solo);
  const [expandido, setExpandido] = useState<string | null>(null);
  const [detalle, setDetalle] = useState<PedidoGrupo | null>(null);
  const [notasDraft, setNotasDraft] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setBorrador(new Set(pedidos.filter((p) => p.seleccionada).map((p) => p.ref_pedido)));
  }, [pedidos]);

  const visibles = useMemo(() => {
    if (soloSeleccionadas && refsTrabajo?.length) {
      const set = new Set(refsTrabajo);
      return pedidos.filter((p) => set.has(p.ref_pedido));
    }
    return pedidos;
  }, [pedidos, soloSeleccionadas, refsTrabajo]);

  function toggleBorrador(ref: string, marcado: boolean) {
    setBorrador((prev) => {
      const next = new Set(prev);
      if (marcado) next.add(ref);
      else next.delete(ref);
      return next;
    });
  }

  function toggleSeleccionarTodo() {
    if (borrador.size === pedidos.length) {
      setBorrador(new Set());
    } else {
      setBorrador(new Set(pedidos.map((p) => p.ref_pedido)));
    }
  }

  async function confirmarSeleccion() {
    const refs = Array.from(borrador);
    setBusy(true);
    try {
      await onConfirmarSeleccion(refs);
      setRefsTrabajo(refs);
      setSoloSeleccionadas(true);
      sessionStorage.setItem(storageKey(sesionId), JSON.stringify({ solo: true, refs }));
    } finally {
      setBusy(false);
    }
  }

  function verTodas() {
    setSoloSeleccionadas(false);
    setRefsTrabajo(null);
    sessionStorage.removeItem(storageKey(sesionId));
  }

  async function guardarNota(filaId: number) {
    const texto = (notasDraft[filaId] ?? "").trim();
    if (!texto) return;
    setBusy(true);
    try {
      await onNota(filaId, texto);
      setNotasDraft((prev) => ({ ...prev, [filaId]: "" }));
    } finally {
      setBusy(false);
    }
  }

  function renderNotas(notas?: { id: number; autor: string | null; texto: string }[]) {
    if (!notas?.length) return null;
    return (
      <ul className="notas-guardadas">
        {notas.map((n) => (
          <li key={n.id}>
            <strong>{n.autor || "—"}:</strong> {n.texto}
          </li>
        ))}
      </ul>
    );
  }

  if (!pedidos.length) {
    return (
      <section className="panel panel-wide">
        <h3>2. Solicitudes de pedido</h3>
        <p className="muted">
          Importá el Excel del día. Orden: más antigua arriba. Reimportá si actualizaste el archivo.
        </p>
      </section>
    );
  }

  return (
    <section className="panel panel-wide">
      <div className="panel-toolbar">
        <div>
          <h3>
            2. Solicitudes de pedido ({visibles.length}
            {soloSeleccionadas ? ` de ${pedidos.length} seleccionadas` : ""})
          </h3>
          <p className="sub">
            Marcá solicitudes → <strong>Seleccionar</strong> → quedás solo con esas. Clic en el
            pedido para ver detalle completo.
          </p>
        </div>
        {!readOnly && (
          <div className="toolbar-actions">
            <button
              type="button"
              className="btn-ghost btn-sm"
              disabled={busy || pedidos.length === 0}
              onClick={toggleSeleccionarTodo}
            >
              {borrador.size === pedidos.length ? "Deseleccionar todo" : "Seleccionar todo"}
            </button>
            <button
              type="button"
              className="btn-primary"
              disabled={busy || borrador.size === 0}
              onClick={() => void confirmarSeleccion()}
            >
              Seleccionar ({borrador.size})
            </button>
            {soloSeleccionadas && (
              <button type="button" className="btn-ghost btn-sm" disabled={busy} onClick={verTodas}>
                Ver todas ({pedidos.length})
              </button>
            )}
          </div>
        )}
      </div>

      {soloSeleccionadas && (
        <div className="banner info compact">
          Mostrando solo las solicitudes confirmadas para esta reunión.{" "}
          {!readOnly && (
            <button type="button" className="btn-sm btn-ghost" onClick={verTodas}>
              Ver listado completo
            </button>
          )}
        </div>
      )}

      <div className="pedidos-list">
        {visibles.map((p) => (
          <article
            key={p.ref_pedido}
            className={`pedido-card${borrador.has(p.ref_pedido) ? " sel" : ""}${p.seleccionada ? " confirmada" : ""}`}
          >
            <header className="pedido-head">
              <label onClick={(e) => e.stopPropagation()}>
                <input
                  type="checkbox"
                  checked={borrador.has(p.ref_pedido)}
                  disabled={readOnly || busy}
                  onChange={(e) => toggleBorrador(p.ref_pedido, e.target.checked)}
                />
              </label>
              <button type="button" className="pedido-titulo-btn" onClick={() => setDetalle(p)}>
                <strong>{p.ref_pedido}</strong>
                <span className="fecha-badge">{p.fecha_solicitud || "Sin fecha"}</span>
              </button>
              <span className="muted pedido-meta">
                {p.solicitante} · {p.tipo_solicitud} · {p.maquina_linea || "—"} · {p.estado_solicitud}{" "}
                · {p.cantidad_filas} ítem(s)
              </span>
              <div className="pedido-acciones">
                <button type="button" className="btn-sm btn-ghost" onClick={() => setDetalle(p)}>
                  Ver pedido
                </button>
                <button
                  type="button"
                  className="btn-sm btn-ghost"
                  onClick={() =>
                    setExpandido(expandido === p.ref_pedido ? null : p.ref_pedido)
                  }
                >
                  {expandido === p.ref_pedido ? "Ocultar ítems" : "Notas por ítem"}
                </button>
              </div>
            </header>
            {expandido === p.ref_pedido && (
              <div className="pedido-body">
                <div className="table-scroll">
                  <table className="data-table compact">
                    <thead>
                      <tr>
                        <th>Código</th>
                        <th>Descripción</th>
                        <th>Cant.</th>
                        <th>Unid.</th>
                        <th>Precio</th>
                        <th>Proveedor</th>
                        <th>Est. ítem</th>
                        <th>Est. sol.</th>
                        <th>OC/RQ</th>
                        <th>Nota reunión</th>
                      </tr>
                    </thead>
                    <tbody>
                      {p.filas.map((f) => (
                        <tr key={f.id}>
                          <td>{f.codigo}</td>
                          <td>{f.descripcion}</td>
                          <td>{f.cantidad}</td>
                          <td>{f.unidad}</td>
                          <td>{f.precio}</td>
                          <td>{f.proveedor}</td>
                          <td>{f.estado_item}</td>
                          <td>{f.estado_solicitud}</td>
                          <td>{f.oc_rq}</td>
                          <td>
                            {renderNotas(f.notas)}
                            {!readOnly && (
                              <div className="nota-inline">
                                <input
                                  placeholder="Actualización…"
                                  value={notasDraft[f.id] ?? ""}
                                  disabled={busy}
                                  onChange={(e) =>
                                    setNotasDraft((prev) => ({
                                      ...prev,
                                      [f.id]: e.target.value,
                                    }))
                                  }
                                  onKeyDown={(e) => {
                                    if (e.key === "Enter") void guardarNota(f.id);
                                  }}
                                />
                                <button
                                  type="button"
                                  className="btn-sm btn-primary"
                                  disabled={busy || !(notasDraft[f.id] ?? "").trim()}
                                  onClick={() => void guardarNota(f.id)}
                                >
                                  +
                                </button>
                              </div>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </article>
        ))}
      </div>

      {!readOnly && (
        <p className="hint">
          Pañolero: {operador || "sin nombre"} — editable arriba a la derecha.
        </p>
      )}

      <PedidoDetalleModal
        pedido={detalle}
        readOnly={readOnly}
        operador={operador}
        onClose={() => setDetalle(null)}
        onNota={onNota}
      />
    </section>
  );
}
