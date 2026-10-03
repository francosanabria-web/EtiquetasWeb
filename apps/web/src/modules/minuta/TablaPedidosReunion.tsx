import { Fragment, useEffect, useMemo, useState } from "react";
import {
  ESTADOS,
  IMPORTANCIAS,
  fetchPedido,
  rankImportancia,
  upsertNovedad,
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
  idsExport?: Set<number>;
  onToggleExport?: (id: number, checked: boolean) => void;
  columnasVisibles?: string[];
};

type SortKey =
  | "orden"
  | "fecha"
  | "n_pedido"
  | "oc"
  | "fecha_esperada"
  | "pedido"
  | "importancia"
  | "estado";

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
  idsExport,
  onToggleExport,
  columnasVisibles,
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
  // Alturas por fila persistentes (para agrandar/achicar y que quede fijo)
  const [alturas, setAlturas] = useState<Record<number, number>>(() => {
    try {
      const raw = localStorage.getItem("minuta-alturas");
      if (raw) return JSON.parse(raw) as Record<number, number>;
    } catch {}
    return {};
  });
  useEffect(() => {
    try {
      localStorage.setItem("minuta-alturas", JSON.stringify(alturas));
    } catch {}
  }, [alturas]);

  const [viewMode, setViewMode] = useState<"tabla" | "tarjetas">(() => {
    try {
      const raw = localStorage.getItem(`minuta-vista-${modo}`);
      if (raw === "tarjetas" || raw === "tabla") return raw as "tabla" | "tarjetas";
    } catch {}
    return "tabla";
  });
  useEffect(() => {
    try {
      localStorage.setItem(`minuta-vista-${modo}`, viewMode);
    } catch {}
  }, [viewMode, modo]);

  const contadores = useMemo(() => {
    const total = pedidos.length;
    const criticos = pedidos.filter((p) => p.importancia === "critico").length;
    const urgentes = pedidos.filter((p) => p.importancia === "urgente").length;
    const normales = pedidos.filter((p) => p.importancia === "normal").length;
    return { total, criticos, urgentes, normales };
  }, [pedidos]);

  const [novedadExpandida, setNovedadExpandida] = useState<Record<number, boolean>>({});

  const visibleCount = columnasVisibles ? columnasVisibles.length : 10;
  const numCols =
    (modo === "activos" ? 1 : 0) + // drag
    (modo === "activos" && onVisto ? 1 : 0) + // visto
    (idsExport ? 1 : 0) + // export selección
    visibleCount +
    1; // acciones

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
      if (sortKey === "importancia") {
        const cmp = rankImportancia(a.importancia) - rankImportancia(b.importancia);
        if (cmp !== 0) return sortAsc ? cmp : -cmp;
        const porOrden = (Number(a.orden) || 0) - (Number(b.orden) || 0);
        if (porOrden !== 0) return porOrden;
        return (b.id || 0) - (a.id || 0);
      }
      const av = String(a[sortKey] ?? "");
      const bv = String(b[sortKey] ?? "");
      const cmp = av.localeCompare(bv, "es", { numeric: true });
      return sortAsc ? cmp : -cmp;
    });
    return list;
  }, [pedidos, busqueda, filtroImp, filtroEst, sortKey, sortAsc]);

  const isVisible = (key: string) => !columnasVisibles || columnasVisibles.includes(key);

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
        <div>
          <h2 style={{ margin: 0 }}>{modo === "activos" ? "Pedidos activos" : "Finalizados"}</h2>
          <div className="minuta-contadores" aria-label="Contadores por importancia">
            <span className="contador total" title="Total de pedidos en esta reunión">Total: <strong>{contadores.total}</strong></span>
            <span className="contador critico" title="Críticos"><span className="dot critico" aria-hidden="true"></span> Críticos: <strong>{contadores.criticos}</strong></span>
            <span className="contador urgente" title="Urgentes"><span className="dot urgente" aria-hidden="true"></span> Urgentes: <strong>{contadores.urgentes}</strong></span>
            <span className="contador normal" title="Normales"><span className="dot normal" aria-hidden="true"></span> Normales: <strong>{contadores.normales}</strong></span>
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <div className="minuta-vista-toggle" role="group" aria-label="Cambiar vista">
            <button
              type="button"
              className={viewMode === "tabla" ? "active" : ""}
              onClick={() => setViewMode("tabla")}
              title="Vista tabla"
              aria-pressed={viewMode === "tabla"}
            >
              ⊞ Tabla
            </button>
            <button
              type="button"
              className={viewMode === "tarjetas" ? "active" : ""}
              onClick={() => setViewMode("tarjetas")}
              title="Vista tarjetas"
              aria-pressed={viewMode === "tarjetas"}
            >
              ▦ Tarjetas
            </button>
          </div>
          {modo === "activos" && onAdd && (
            <button type="button" className="btn-ghost btn-sm" onClick={onAdd}>
              + Pedido
            </button>
          )}
        </div>
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

      {viewMode === "tabla" ? (
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
              {idsExport && onToggleExport && (
                <th className="minuta-col-export" title="Seleccionar para exportar a Compras">
                  <input
                    type="checkbox"
                    checked={idsExport.size === pedidos.length && pedidos.length > 0}
                    onChange={(e) => {
                      const checked = e.target.checked;
                      pedidos.forEach((p) => onToggleExport(p.id, checked));
                    }}
                    title="Seleccionar todo para export"
                  />
                </th>
              )}
              {isVisible("fecha") && (
                <th>
                  <button type="button" className="minuta-th-btn" onClick={() => toggleSort("fecha")}>
                    Fecha solicitud
                  </button>
                </th>
              )}
              {isVisible("n_pedido") && (
                <th>
                  <button type="button" className="minuta-th-btn" onClick={() => toggleSort("n_pedido")}>
                    Nº solicitud
                  </button>
                </th>
              )}
              {isVisible("oc") && (
                <th>
                  <button type="button" className="minuta-th-btn" onClick={() => toggleSort("oc")}>
                    Nº OC
                  </button>
                </th>
              )}
              {isVisible("fecha_esperada") && (
                <th>
                  <button type="button" className="minuta-th-btn" onClick={() => toggleSort("fecha_esperada")}>
                    Fecha esperada
                  </button>
                </th>
              )}
              {isVisible("pedido") && (
                <th>
                  <button type="button" className="minuta-th-btn" onClick={() => toggleSort("pedido")}>
                    Descripción
                  </button>
                </th>
              )}
              {isVisible("ultima_novedad") && <th>Última novedad</th>}
              {isVisible("consultas") && <th>Consultas</th>}
              {isVisible("novedad_actual") && <th>Novedades nueva reunión ({fmtFecha(fechaReunion)})</th>}
              {isVisible("importancia") && (
                <th>
                  <button type="button" className="minuta-th-btn" onClick={() => toggleSort("importancia")}>
                    Importancia
                  </button>
                </th>
              )}
              {isVisible("estado") && (
                <th>
                  <button type="button" className="minuta-th-btn" onClick={() => toggleSort("estado")}>
                    Estado
                  </button>
                </th>
              )}
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
                    style={alturas[p.id] ? { height: `${alturas[p.id]}px` } : undefined}
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
                        <span className="minuta-drag-handle" aria-hidden="true">⋮⋮</span>
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
                    {idsExport && onToggleExport && (
                      <td className="minuta-col-export">
                        <input
                          type="checkbox"
                          checked={idsExport.has(p.id)}
                          title="Incluir en export a Compras"
                          aria-label={`Exportar: ${label}`}
                          onChange={(e) => onToggleExport(p.id, e.target.checked)}
                        />
                      </td>
                    )}
                    {isVisible("fecha") && (
                      <td>
                        <input
                          type="date"
                          value={p.fecha}
                          onChange={(e) => onCampo(p.id, { fecha: e.target.value })}
                        />
                      </td>
                    )}
                    {isVisible("n_pedido") && (
                      <td>
                        <input
                          value={p.n_pedido}
                          onChange={(e) => onCampo(p.id, { n_pedido: e.target.value })}
                          placeholder="Nº solicitud"
                        />
                      </td>
                    )}
                    {isVisible("oc") && (
                      <td>
                        <input
                          value={p.oc}
                          onChange={(e) => onCampo(p.id, { oc: e.target.value })}
                          placeholder="Nº OC"
                        />
                      </td>
                    )}
                    {isVisible("fecha_esperada") && (
                      <td>
                        <input
                          type="date"
                          value={p.fecha_esperada ?? ""}
                          onChange={(e) => onCampo(p.id, { fecha_esperada: e.target.value || null })}
                          title="Fecha esperada de entrega"
                        />
                      </td>
                    )}
                    {isVisible("pedido") && (
                      <td>
                        <textarea
                          className="minuta-desc-input"
                          rows={2}
                          value={p.pedido}
                          onChange={(e) => onCampo(p.id, { pedido: e.target.value })}
                          onMouseUp={(e) => {
                            const tr = (e.currentTarget.closest("tr") as HTMLElement) || null;
                            if (tr) setAlturas((prev) => ({ ...prev, [p.id]: tr.offsetHeight }));
                          }}
                          placeholder="Descripción"
                        />
                      </td>
                    )}
                    {isVisible("ultima_novedad") && (
                      <td className="minuta-td-ultima">
                        {ultimaNovedad ? (
                          <span className="minuta-ultima-novedad" title={ultimaNovedad}>
                            {ultimaNovedad}
                          </span>
                        ) : (
                          <span className="minuta-hint">—</span>
                        )}
                      </td>
                    )}
                    {isVisible("consultas") && (
                      <td>
                        <textarea
                          className="minuta-consultas-input"
                          rows={2}
                          value={p.consultas ?? ""}
                          onChange={(e) => onCampo(p.id, { consultas: e.target.value })}
                          onMouseUp={(e) => {
                            const tr = (e.currentTarget.closest("tr") as HTMLElement) || null;
                            if (tr) setAlturas((prev) => ({ ...prev, [p.id]: tr.offsetHeight }));
                          }}
                          placeholder="Consultas…"
                        />
                      </td>
                    )}
                    {isVisible("novedad_actual") && (
                      <td>
                        <textarea
                          className="minuta-novedad-input"
                          rows={2}
                          value={borrador}
                          onChange={(e) => onBorrador(p.id, e.target.value)}
                          onMouseUp={(e) => {
                            const tr = (e.currentTarget.closest("tr") as HTMLElement) || null;
                            if (tr) setAlturas((prev) => ({ ...prev, [p.id]: tr.offsetHeight }));
                          }}
                          placeholder={`Novedades del ${fmtFecha(fechaReunion)}…`}
                        />
                      </td>
                    )}
                    {isVisible("importancia") && (
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
                    )}
                    {isVisible("estado") && (
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
                    )}
                    <td className="minuta-acciones">
                      <button
                        type="button"
                        className="btn-ghost btn-sm"
                        title="Agrandar fila"
                        onClick={() => setAlturas((prev) => ({ ...prev, [p.id]: (prev[p.id] || 60) + 24 }))}
                      >
                        ＋
                      </button>
                      <button
                        type="button"
                        className="btn-ghost btn-sm"
                        title="Achicar fila"
                        onClick={() => setAlturas((prev) => ({ ...prev, [p.id]: Math.max(44, (prev[p.id] || 60) - 24) }))}
                      >
                        －
                      </button>
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
      ) : (
        <div className="minuta-cards-grouped">
          {filtrados.length === 0 ? (
            <p className="minuta-empty minuta-empty-cards">
              {modo === "activos" ? "No hay pedidos activos. Agregá uno con «+ Pedido»." : "No hay ítems finalizados."}
            </p>
          ) : (
            (["critico", "urgente", "normal"] as const).map((imp) => {
              const grupo = filtrados.filter((p) => p.importancia === imp);
              if (grupo.length === 0) return null;
              const titulo = imp === "critico" ? "Críticos" : imp === "urgente" ? "Urgentes" : "Normales";
              return (
                <section key={imp} className={`minuta-grupo-imp grupo-${imp}`}>
                  <h3 className="minuta-grupo-titulo">
                    <span className={`minuta-grupo-badge imp-${imp}`}>{titulo}</span>
                    <span className="minuta-grupo-count">{grupo.length}</span>
                  </h3>
                  <div className="minuta-cards-grid">
                    {grupo.map((p) => {
                      const expandido = expandidoId === p.id;
                      const borrador = borradores[p.id] ?? "";
                      const visto = Boolean(vistos[p.id]);
                      const ultimaNovedad = p.ultima_novedad && p.ultima_novedad_fecha !== fechaReunion ? p.ultima_novedad : "";
                      const label = p.n_pedido || p.pedido || `#${p.id}`;
                      const novExpandida = Boolean(novedadExpandida[p.id]);
                      return (
                        <article key={p.id} className={`minuta-pedido-card imp-${p.importancia} ${visto ? "visto" : ""}`}>
                  <header className="minuta-card-head">
                    <div className="minuta-card-head-top">
                      {modo === "activos" && <span className="minuta-drag-handle card" aria-hidden="true" title="Arrastrar para reordenar">⋮⋮</span>}
                      <span className={`minuta-importancia-badge imp-${p.importancia}`}>{p.importancia}</span>
                              <span className={`minuta-estado-badge est-${p.estado}`}>{p.estado}</span>
                              <span className="minuta-card-id">#{p.id}</span>
                            </div>
                            <strong className="minuta-card-pedido" title={p.pedido}>{p.pedido || "Sin descripción"}</strong>
                            <span className="minuta-card-npedido">{p.n_pedido || "—"}</span>
                          </header>
                          <div className="minuta-card-body">
                            {ultimaNovedad && (
                              <div
                                className={`minuta-card-ultima-wrap ${novExpandida ? "expandida" : ""}`}
                                onClick={() => setNovedadExpandida((prev) => ({ ...prev, [p.id]: !prev[p.id] }))}
                                title={novExpandida ? "Click para colapsar" : "Click para expandir"}
                                role="button"
                                tabIndex={0}
                                onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setNovedadExpandida((prev) => ({ ...prev, [p.id]: !prev[p.id] })); } }}
                              >
                                <p className="minuta-card-ultima"><strong>Última:</strong> {ultimaNovedad}</p>
                                {!novExpandida && ultimaNovedad.length > 90 && <span className="minuta-card-ultima-more">Ver más…</span>}
                              </div>
                            )}
                            <label className="minuta-card-field">
                              <span>Consultas</span>
                              <textarea rows={2} value={p.consultas ?? ""} onChange={(e) => onCampo(p.id, { consultas: e.target.value })} placeholder="Consultas…" />
                            </label>
                            <label className="minuta-card-field">
                              <span>Novedad {fmtFecha(fechaReunion)}</span>
                              <textarea rows={2} value={borrador} onChange={(e) => onBorrador(p.id, e.target.value)} placeholder={`Novedades del ${fmtFecha(fechaReunion)}…`} />
                            </label>
                          </div>
                          <div className="minuta-card-actions">
                            <button type="button" className="btn-ghost btn-sm" onClick={() => onExpand(expandido ? null : p.id)}>{expandido ? "▲" : "▼"} Historial</button>
                            {modo === "activos" && onFinalizar && <button type="button" className="btn-ghost btn-sm" disabled={busyId === p.id} onClick={async () => { setBusyId(p.id); try { await onFinalizar(p.id); } finally { setBusyId(null); } }}>Finalizar</button>}
                            <button type="button" className="btn-ghost btn-sm minuta-btn-eliminar" disabled={busyId === p.id} onClick={() => void confirmarEliminar(p.id, label)}>Eliminar</button>
                          </div>
                          {expandido && <div className="minuta-card-historial"><HistorialPedido pedido={p} /></div>}
                        </article>
                      );
                    })}
                  </div>
                </section>
              );
            })
          )}
        </div>
      )}
    </section>
  );
}

function HistorialPedido({ pedido }: { pedido: Pedido }) {
  const [novedades, setNovedades] = useState<Pedido["novedades"]>(pedido.novedades);
  const [movimientos, setMovimientos] = useState<Pedido["movimientos"]>(pedido.movimientos);
  const [cargandoHist, setCargandoHist] = useState(
    !(pedido.novedades && pedido.novedades.length > 0),
  );
  const [editandoId, setEditandoId] = useState<number | null>(null);
  const [editTexto, setEditTexto] = useState("");
  const [guardandoId, setGuardandoId] = useState<number | null>(null);

  useEffect(() => {
    let alive = true;
    setCargandoHist(true);
    fetchPedido(pedido.id)
      .then((detalle) => {
        if (!alive) return;
        setNovedades(detalle.novedades ?? []);
        setMovimientos(detalle.movimientos ?? []);
      })
      .catch(() => {
        if (alive) {
          setNovedades(pedido.novedades ?? []);
          setMovimientos(pedido.movimientos ?? []);
        }
      })
      .finally(() => {
        if (alive) setCargandoHist(false);
      });
    return () => {
      alive = false;
    };
  }, [pedido.id]);

  const novs = novedades ?? [];
  const movs = movimientos ?? [];

  if (cargandoHist) {
    return <p className="minuta-hint minuta-historial">Cargando historial…</p>;
  }

  if (novs.length === 0 && movs.length === 0) {
    return (
      <p className="minuta-hint minuta-historial">
        Sin novedades previas. Las de reuniones anteriores aparecen acá al expandir; las de la
        fecha actual se editan en la columna Novedades.
      </p>
    );
  }

  return (
    <div className="minuta-historial">
      <h4>Historial del pedido</h4>
      {movs.length > 0 && (
        <ul className="minuta-movimientos">
          {movs.map((m) => (
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
      {novs.length > 0 && (
        <ul className="minuta-novedades-list">
          {novs.map((n) => {
            const esPlaceholder = n.texto.includes("[Novedad del 15/09");
            const enEdicion = editandoId === n.id;
            return (
              <li key={n.id} className={esPlaceholder ? "minuta-novedad-placeholder" : ""} style={esPlaceholder ? { background: "#fffbeb", border: "1px dashed #f59e0b", borderRadius: 8, padding: "8px 10px" } : undefined}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                  <span>
                    <strong>Novedades del {fmtFecha(n.fecha_reunion)}</strong>
                    <span className="minuta-novedad-sector"> ({n.sector})</span>
                    {esPlaceholder && <span style={{ marginLeft: 8, fontSize: "0.72rem", fontWeight: 700, background: "#f59e0b", color: "#fff", padding: "2px 6px", borderRadius: 999 }}>placeholder 15/09</span>}
                  </span>
                  {!enEdicion && (
                    <button type="button" className="btn-ghost btn-sm" onClick={() => { setEditandoId(n.id); setEditTexto(n.texto === "[Novedad del 15/09 - completar]" ? "" : n.texto); }}>
                      ✏️ Editar
                    </button>
                  )}
                </div>
                {enEdicion ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 8 }}>
                    <textarea rows={3} value={editTexto} onChange={(e) => setEditTexto(e.target.value)} autoFocus placeholder="Escribí la novedad del 15/09…" style={{ width: "100%", padding: 8, borderRadius: 8, border: "1px solid var(--border)", fontFamily: "inherit" }} />
                    <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                      <button type="button" className="btn-ghost btn-sm" disabled={guardandoId === n.id} onClick={() => { setEditandoId(null); setEditTexto(""); }}>
                        Cancelar
                      </button>
                      <button
                        type="button"
                        className="btn-primary btn-sm"
                        disabled={guardandoId === n.id || !editTexto.trim()}
                        onClick={async () => {
                          const texto = editTexto.trim();
                          if (!texto) return;
                          setGuardandoId(n.id);
                          try {
                            await upsertNovedad(pedido.id, { fecha_reunion: n.fecha_reunion, texto });
                            setNovedades((prev) => (prev ? prev.map((x) => (x.id === n.id ? { ...x, texto } : x)) : prev));
                            setEditandoId(null);
                            setEditTexto("");
                          } catch (e) {
                            alert(e instanceof Error ? e.message : "No se pudo guardar");
                          } finally {
                            setGuardandoId(null);
                          }
                        }}
                      >
                        {guardandoId === n.id ? "Guardando…" : "Guardar"}
                      </button>
                    </div>
                  </div>
                ) : (
                  <p style={{ margin: "6px 0 0", whiteSpace: "pre-wrap", color: esPlaceholder ? "#92400e" : undefined, fontStyle: esPlaceholder ? "italic" : undefined }}>{n.texto}</p>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
