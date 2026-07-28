import { Fragment, useMemo, useState } from "react";
import {
  ESTADOS,
  IMPORTANCIAS,
  type EstadoItem,
  type Importancia,
  type Pedido,
  type PedidoPatch,
} from "../../api/minutaClient";
import { fmtFecha } from "./types";

type Props = {
  pedidos: Pedido[];
  fechaReunion: string;
  borradores: Record<number, string>;
  vistos?: Record<number, boolean>;
  expandidoId: number | null;
  modo?: "activos" | "finalizados";
  onExpand: (id: number | null) => void;
  onCampo: (id: number, patch: PedidoPatch) => void;
  onBorrador: (id: number, texto: string) => void;
  onVisto?: (id: number, visto: boolean) => void;
  onFinalizar?: (id: number) => Promise<void>;
  onReactivar?: (id: number) => Promise<void>;
  onEliminar: (id: number) => Promise<void>;
  onReordenar?: (idsOrdenados: number[]) => void;
  onAdd?: () => void;
};

type SortKey = "orden" | "fecha" | "n_pedido" | "oc" | "pedido" | "importancia" | "estado";

export default function TablaPedidosReunion({
  pedidos,
  fechaReunion,
  borradores,
  vistos = {},
  expandidoId,
  modo = "activos",
  onExpand,
  onCampo,
  onBorrador,
  onVisto,
  onFinalizar,
  onReactivar,
  onEliminar,
  onReordenar,
  onAdd,
}: Props) {
  const [busqueda, setBusqueda] = useState("");
  const [filtroImp, setFiltroImp] = useState<string>("");
  const [filtroEst, setFiltroEst] = useState<string>("");
  /** Por defecto orden manual (drag). Un click en columna ordena por ese campo. */
  const [sortKey, setSortKey] = useState<SortKey>("orden");
  const [sortAsc, setSortAsc] = useState(true);
  const [dragId, setDragId] = useState<number | null>(null);
  const [dragOverId, setDragOverId] = useState<number | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const numCols =
    (modo === "activos" ? 1 : 0) + // drag
    (modo === "activos" && onVisto ? 1 : 0) + // visto
    10;

  const filtrados = useMemo(() => {
    const q = busqueda.trim().toLowerCase();
    let list = [...pedidos];
    if (q) {
      list = list.filter((p) =>
        [p.n_pedido, p.oc, p.pedido, p.consultas, p.ultima_novedad ?? ""]
          .join(" ")
          .toLowerCase()
          .includes(q),
      );
    }
    if (filtroImp) list = list.filter((p) => p.importancia === filtroImp);
    if (filtroEst) list = list.filter((p) => p.estado === filtroEst);
    list.sort((a, b) => {
      if (sortKey === "orden") {
        const cmp = (Number(a.orden) || 0) - (Number(b.orden) || 0);
        if (cmp !== 0) return sortAsc ? cmp : -cmp;
        return (b.id || 0) - (a.id || 0);
      }
      const av = String(a[sortKey] ?? "");
      const bv = String(b[sortKey] ?? "");
      const cmp = av.localeCompare(bv, "es", { numeric: true });
      return sortAsc ? cmp : -cmp;
    });
    return list;
  }, [pedidos, busqueda, filtroImp, filtroEst, sortKey, sortAsc]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc((v) => !v);
    else {
      setSortKey(key);
      setSortAsc(true);
    }
  };

  const soltarSobre = (targetId: number) => {
    if (!onReordenar || dragId == null || dragId === targetId) {
      setDragId(null);
      setDragOverId(null);
      return;
    }
    const ids = filtrados.map((p) => p.id);
    const from = ids.indexOf(dragId);
    const to = ids.indexOf(targetId);
    if (from < 0 || to < 0) {
      setDragId(null);
      setDragOverId(null);
      return;
    }
    ids.splice(to, 0, ids.splice(from, 1)[0]);
    // Tras mover, volver a orden manual para que no lo pise el sort de columna.
    setSortKey("orden");
    setSortAsc(true);
    onReordenar(ids);
    setDragId(null);
    setDragOverId(null);
  };

  const confirmarEliminar = async (id: number, label: string) => {
    if (!window.confirm(`¿Eliminar el ítem «${label}»? Esta acción no se puede deshacer.`)) {
      return;
    }
    setBusyId(id);
    try {
      await onEliminar(id);
    } finally {
      setBusyId(null);
    }
  };

  return (
    <section className="minuta-section">
      <div className="minuta-section-head">
        <h2>{modo === "activos" ? "Pedidos activos" : "Finalizados"}</h2>
        {modo === "activos" && onAdd && (
          <button type="button" className="btn-ghost btn-sm" onClick={onAdd}>
            + Pedido
          </button>
        )}
      </div>

      <div className="minuta-toolbar">
        <input
          type="search"
          className="minuta-search"
          placeholder="Buscar…"
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
        />
        <select value={filtroImp} onChange={(e) => setFiltroImp(e.target.value)}>
          <option value="">Importancia: todas</option>
          {IMPORTANCIAS.map((i) => (
            <option key={i.value} value={i.value}>
              {i.label}
            </option>
          ))}
        </select>
        <select value={filtroEst} onChange={(e) => setFiltroEst(e.target.value)}>
          <option value="">Estado: todos</option>
          {ESTADOS.map((e) => (
            <option key={e.value} value={e.value}>
              {e.label}
            </option>
          ))}
        </select>
        {modo === "activos" && sortKey !== "orden" && (
          <button
            type="button"
            className="btn-ghost btn-sm"
            onClick={() => {
              setSortKey("orden");
              setSortAsc(true);
            }}
          >
            Orden manual
          </button>
        )}
      </div>

      <div className="minuta-table-wrap">
        <table className="minuta-table minuta-table-pedidos">
          <thead>
            <tr>
              {modo === "activos" && <th aria-label="Mover" className="minuta-col-drag" />}
              {modo === "activos" && onVisto && (
                <th className="minuta-col-visto" title="Visto en esta reunión">
                  ✓
                </th>
              )}
              <th>
                <button type="button" className="minuta-th-btn" onClick={() => toggleSort("fecha")}>
                  Fecha solicitud
                </button>
              </th>
              <th>
                <button type="button" className="minuta-th-btn" onClick={() => toggleSort("n_pedido")}>
                  Nº solicitud
                </button>
              </th>
              <th>
                <button type="button" className="minuta-th-btn" onClick={() => toggleSort("oc")}>
                  Nº OC
                </button>
              </th>
              <th>
                <button type="button" className="minuta-th-btn" onClick={() => toggleSort("pedido")}>
                  Descripción
                </button>
              </th>
              <th>Última novedad</th>
              <th>Consultas</th>
              <th>Novedades nueva reunión ({fmtFecha(fechaReunion)})</th>
              <th>
                <button type="button" className="minuta-th-btn" onClick={() => toggleSort("importancia")}>
                  Importancia
                </button>
              </th>
              <th>
                <button type="button" className="minuta-th-btn" onClick={() => toggleSort("estado")}>
                  Estado
                </button>
              </th>
              <th aria-label="Acciones" />
            </tr>
          </thead>
          <tbody>
            {filtrados.length === 0 && (
              <tr>
                <td colSpan={numCols} className="minuta-empty">
                  {modo === "activos"
                    ? "No hay pedidos activos. Agregá uno con «+ Pedido»."
                    : "No hay ítems finalizados."}
                </td>
              </tr>
            )}
            {filtrados.map((p) => {
              const expandido = expandidoId === p.id;
              const borrador = borradores[p.id] ?? "";
              const visto = Boolean(vistos[p.id]);
              const ultimaNovedad =
                p.ultima_novedad && p.ultima_novedad_fecha !== fechaReunion
                  ? p.ultima_novedad
                  : "";
              const label = p.n_pedido || p.pedido || `#${p.id}`;
              return (
                <Fragment key={p.id}>
                  <tr
                    className={[
                      expandido ? "minuta-row-expanded" : "",
                      dragOverId === p.id ? "minuta-row-dragover" : "",
                      dragId === p.id ? "minuta-row-dragging" : "",
                      visto ? "minuta-row-visto" : "",
                    ]
                      .filter(Boolean)
                      .join(" ")}
                    onDragOver={(e) => {
                      if (dragId != null) {
                        e.preventDefault();
                        setDragOverId(p.id);
                      }
                    }}
                    onDrop={(e) => {
                      e.preventDefault();
                      soltarSobre(p.id);
                    }}
                  >
                    {modo === "activos" && (
                      <td
                        className="minuta-col-drag"
                        draggable
                        onDragStart={() => setDragId(p.id)}
                        onDragEnd={() => {
                          setDragId(null);
                          setDragOverId(null);
                        }}
                        title="Arrastrar para reordenar"
                      >
                        <span className="minuta-drag-handle">⠿</span>
                      </td>
                    )}
                    {modo === "activos" && onVisto && (
                      <td className="minuta-col-visto">
                        <input
                          type="checkbox"
                          checked={visto}
                          title={visto ? "Visto en esta reunión" : "Marcar como visto"}
                          aria-label={`Visto: ${label}`}
                          onChange={(e) => onVisto(p.id, e.target.checked)}
                        />
                      </td>
                    )}
                    <td>
                      <input
                        type="date"
                        value={p.fecha}
                        onChange={(e) => onCampo(p.id, { fecha: e.target.value })}
                      />
                    </td>
                    <td>
                      <input
                        value={p.n_pedido}
                        onChange={(e) => onCampo(p.id, { n_pedido: e.target.value })}
                        placeholder="Nº solicitud"
                      />
                    </td>
                    <td>
                      <input
                        value={p.oc}
                        onChange={(e) => onCampo(p.id, { oc: e.target.value })}
                        placeholder="Nº OC"
                      />
                    </td>
                    <td>
                      <textarea
                        className="minuta-desc-input"
                        rows={2}
                        value={p.pedido}
                        onChange={(e) => onCampo(p.id, { pedido: e.target.value })}
                        placeholder="Descripción"
                      />
                    </td>
                    <td className="minuta-td-ultima">
                      {ultimaNovedad ? (
                        <span className="minuta-ultima-novedad" title={ultimaNovedad}>
                          {ultimaNovedad}
                        </span>
                      ) : (
                        <span className="minuta-hint">—</span>
                      )}
                    </td>
                    <td>
                      <textarea
                        className="minuta-consultas-input"
                        rows={2}
                        value={p.consultas ?? ""}
                        onChange={(e) => onCampo(p.id, { consultas: e.target.value })}
                        placeholder="Consultas…"
                      />
                    </td>
                    <td>
                      <textarea
                        className="minuta-novedad-input"
                        rows={2}
                        value={borrador}
                        onChange={(e) => onBorrador(p.id, e.target.value)}
                        placeholder={`Novedades del ${fmtFecha(fechaReunion)}…`}
                      />
                    </td>
                    <td>
                      <select
                        className={`minuta-select minuta-imp-${p.importancia}`}
                        value={p.importancia}
                        onChange={(e) =>
                          onCampo(p.id, { importancia: e.target.value as Importancia })
                        }
                      >
                        {IMPORTANCIAS.map((i) => (
                          <option key={i.value} value={i.value}>
                            {i.label}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td>
                      <select
                        className={`minuta-select minuta-estado-${p.estado}`}
                        value={p.estado}
                        onChange={(e) =>
                          onCampo(p.id, { estado: e.target.value as EstadoItem })
                        }
                      >
                        {ESTADOS.map((e) => (
                          <option key={e.value} value={e.value}>
                            {e.label}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="minuta-acciones">
                      <button
                        type="button"
                        className="btn-ghost btn-sm"
                        title="Ver historial"
                        onClick={() => onExpand(expandido ? null : p.id)}
                      >
                        {expandido ? "▲" : "▼"}
                      </button>
                      {modo === "activos" && onFinalizar && (
                        <button
                          type="button"
                          className="btn-ghost btn-sm minuta-btn-finalizar"
                          disabled={busyId === p.id}
                          onClick={async () => {
                            setBusyId(p.id);
                            try {
                              await onFinalizar(p.id);
                            } finally {
                              setBusyId(null);
                            }
                          }}
                        >
                          Finalizar
                        </button>
                      )}
                      {modo === "finalizados" && onReactivar && (
                        <button
                          type="button"
                          className="btn-ghost btn-sm"
                          disabled={busyId === p.id}
                          onClick={async () => {
                            setBusyId(p.id);
                            try {
                              await onReactivar(p.id);
                            } finally {
                              setBusyId(null);
                            }
                          }}
                        >
                          Reactivar
                        </button>
                      )}
                      <button
                        type="button"
                        className="btn-ghost btn-sm minuta-btn-eliminar"
                        disabled={busyId === p.id}
                        onClick={() => void confirmarEliminar(p.id, label)}
                      >
                        Eliminar
                      </button>
                    </td>
                  </tr>
                  {expandido && (
                    <tr className="minuta-historial-row">
                      <td colSpan={numCols}>
                        <HistorialPedido pedido={p} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function HistorialPedido({ pedido }: { pedido: Pedido }) {
  const novedades = pedido.novedades ?? [];
  const movimientos = pedido.movimientos ?? [];

  if (novedades.length === 0 && movimientos.length === 0) {
    return (
      <p className="minuta-hint minuta-historial">
        Sin novedades previas. Las que se envíen por mail aparecerán acá.
      </p>
    );
  }

  return (
    <div className="minuta-historial">
      <h4>Historial del pedido</h4>
      {movimientos.length > 0 && (
        <ul className="minuta-movimientos">
          {movimientos.map((m) => (
            <li key={m.id}>
              <span className="minuta-mov-badge">
                {m.sector_origen} → {m.sector_destino}
              </span>
              <span className="minuta-mov-fecha">{fmtFecha(m.fecha)}</span>
              {m.notas && <span> — {m.notas}</span>}
            </li>
          ))}
        </ul>
      )}
      {novedades.length > 0 && (
        <ul className="minuta-novedades-list">
          {novedades.map((n) => (
            <li key={n.id}>
              <strong>Novedades del {fmtFecha(n.fecha_reunion)}</strong>
              <span className="minuta-novedad-sector"> ({n.sector})</span>
              <p>{n.texto}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
