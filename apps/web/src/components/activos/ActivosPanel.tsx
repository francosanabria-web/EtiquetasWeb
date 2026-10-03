import { Fragment, useMemo, useState } from "react";
import {
  claseBadgeDias,
  claseFilaDias,
  DIAS_FUERA_ALERTA,
  DIAS_FUERA_AVISO,
  etiquetaSector,
  fmtFechaIso,
  fmtNum,
  hoyIsoLocal,
  marcarRegreso,
  refreshActivos,
  restablecerFuera,
  urlActivosExcel,
  urlActivosPdf,
  crearSalida,
  editarActivo,
  type ActivoItem,
  type ActivosResumen,
  type CrearSalidaPayload,
  type EditarActivoPayload,
} from "../../api/activosClient";
import "../../styles/activos.css";

type Vista = "fuera" | "ingresados";

type Props = {
  data: ActivosResumen | null;
  loading: boolean;
  error: string | null;
  puedeEscribir?: boolean;
  token?: string | null;
  onRetry?: () => void;
  onRefreshed?: () => void;
};

function matchQuery(a: ActivoItem, q: string): boolean {
  if (!q) return true;
  const ql = q.toLowerCase();
  const hay = [
    a.equipo,
    a.observaciones,
    a.proveedor,
    a.sector,
    a.codigo,
    a.remito,
    a.n_pedido ?? "",
    a.n_oc ?? "",
    a.nro_serie ?? "",
    a.fecha_salida ?? "",
    a.fecha_regreso ?? "",
    a.estado_al_ingreso ?? "",
    String(a.cantidad ?? ""),
    String(a.dias_fuera),
  ]
    .join(" ")
    .toLowerCase();
  return hay.includes(ql);
}

function agruparPorRemito(items: ActivoItem[]): Array<{ remito: string; items: ActivoItem[] }> {
  const map = new Map<string, ActivoItem[]>();
  for (const it of items) {
    const key = (it.remito || "").trim() || "Sin remito";
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(it);
  }
  return Array.from(map.entries())
    .sort((a, b) => {
      if (a[0] === "Sin remito") return 1;
      if (b[0] === "Sin remito") return -1;
      return a[0].localeCompare(b[0], "es", { numeric: true, sensitivity: "base" });
    })
    .map(([remito, list]) => ({ remito, items: list }));
}

function Tabla({
  items,
  vista,
  seleccion,
  onToggle,
  onToggleAll,
  puedeSeleccionar,
  puedeEscribir,
  onEditar,
}: {
  items: ActivoItem[];
  vista: Vista;
  seleccion: Set<string>;
  onToggle: (id: string) => void;
  onToggleAll: (ids: string[], all: boolean) => void;
  puedeSeleccionar: boolean;
  puedeEscribir?: boolean;
  onEditar?: (a: ActivoItem) => void;
}) {
  if (items.length === 0) {
    return (
      <p className="act-empty">
        {vista === "fuera" ? "No hay activos fuera de planta con este filtro." : "No hay ingresados con este filtro."}
      </p>
    );
  }

  const ids = items.map((a) => a.id).filter(Boolean);
  const allSelected = ids.length > 0 && ids.every((id) => seleccion.has(id));

  return (
    <>
      <div className="act-table-wrap act-table-desktop">
        <table className="act-table">
          <thead>
            <tr>
              {puedeSeleccionar ? (
                <th className="act-th-check">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    onChange={(e) => onToggleAll(ids, e.target.checked)}
                    aria-label="Seleccionar todos visibles"
                  />
                </th>
              ) : null}
              <th>Días fuera</th>
              <th>Equipo / repuesto</th>
              <th>Cant.</th>
              <th>Código</th>
              <th>N° serie</th>
              <th>Nº remito</th>
              <th>Nº pedido</th>
              <th>Nº OC</th>
              <th>Fecha salida</th>
              {vista === "ingresados" ? (
                <>
                  <th>Fecha regreso</th>
                  <th>Estado ingreso</th>
                </>
              ) : null}
              <th>Observaciones</th>
              <th>Proveedor</th>
              <th>Sector</th>
              {puedeEscribir ? <th style={{ width: 40 }} aria-label="Editar" /> : null}
            </tr>
          </thead>
          <tbody>
            {(() => {
              const grupos = agruparPorRemito(items);
              const baseCols = vista === "ingresados" ? 14 : 12;
              const colSpan = baseCols + (puedeSeleccionar ? 1 : 0) + (puedeEscribir ? 1 : 0);
              return grupos.map((grupo) => (
                <Fragment key={`g-${grupo.remito}`}>
                  <tr className="act-row-grupo">
                    <td colSpan={colSpan}>
                      <span className="act-grupo-remito">Remito {grupo.remito}</span>
                      <span className="act-grupo-count"> · {grupo.items.length} ítem(s)</span>
                      {grupo.remito !== "Sin remito" && grupo.items[0]?.proveedor ? (
                        <span className="act-grupo-extra"> · {grupo.items[0].proveedor}</span>
                      ) : null}
                    </td>
                  </tr>
                  {grupo.items.map((a, i) => {
                    const checked = a.id ? seleccion.has(a.id) : false;
                    return (
                      <tr
                        key={`${a.id || "x"}-${a.equipo}-${grupo.remito}-${i}`}
                        className={`${claseFilaDias(a.dias_fuera)}${checked ? " act-row-selected" : ""}`}
                      >
                        {puedeSeleccionar ? (
                          <td className="act-td-check">
                            <input
                              type="checkbox"
                              checked={checked}
                              disabled={!a.id}
                              onChange={() => a.id && onToggle(a.id)}
                              aria-label={`Seleccionar ${a.equipo || a.dias_fuera}`}
                            />
                          </td>
                        ) : null}
                        <td>
                          <span className={claseBadgeDias(a.dias_fuera)}>{a.dias_fuera}</span>
                        </td>
                        <td className="act-td-desc" title={a.equipo}>
                          {a.equipo || "—"}
                        </td>
                        <td className="act-td-doc" style={{ textAlign: "center" }}>
                          {a.cantidad ?? 1}
                        </td>
                        <td className="act-td-doc" title={a.codigo}>
                          {a.codigo || "—"}
                        </td>
                        <td className="act-td-doc" title={a.nro_serie}>
                          {a.nro_serie || "—"}
                        </td>
                        <td className="act-td-doc" title={a.remito}>
                          {a.remito || "—"}
                        </td>
                        <td className="act-td-doc" title={a.n_pedido}>
                          {a.n_pedido || "—"}
                        </td>
                        <td className="act-td-doc" title={a.n_oc}>
                          {a.n_oc || "—"}
                        </td>
                        <td className="act-td-doc" style={{ whiteSpace: "nowrap" }}>
                          {a.fecha_salida || "—"}
                        </td>
                        {vista === "ingresados" ? (
                          <>
                            <td className="act-td-doc" style={{ whiteSpace: "nowrap" }}>
                              {a.fecha_regreso || "—"}
                            </td>
                            <td className="act-td-desc" title={a.estado_al_ingreso} style={{ maxWidth: 120 }}>
                              {a.estado_al_ingreso || "—"}
                            </td>
                          </>
                        ) : null}
                        <td className="act-td-desc" title={a.observaciones} style={{ maxWidth: 220 }}>
                          {a.observaciones || "—"}
                        </td>
                        <td className="act-td-prov" title={a.proveedor}>
                          {a.proveedor || "—"}
                        </td>
                        <td>{etiquetaSector(a.sector) || "—"}</td>
                        {puedeEscribir && onEditar ? (
                          <td className="act-td-check">
                            <button
                              type="button"
                              className="btn-ghost btn-xs"
                              title="Editar"
                              onClick={() => onEditar(a)}
                              aria-label={`Editar ${a.equipo}`}
                            >
                              ✏️
                            </button>
                          </td>
                        ) : puedeEscribir ? (
                          <td />
                        ) : null}
                      </tr>
                    );
                  })}
                </Fragment>
              ));
            })()}
          </tbody>
        </table>
      </div>

      <div className="act-cards-mobile">
        {(() => {
          const grupos = agruparPorRemito(items);
          return grupos.map((grupo) => (
            <div key={`gm-${grupo.remito}`} className="act-grupo-mobile">
              <div className="act-grupo-mobile-header">
                <span className="act-grupo-remito">Remito {grupo.remito}</span>
                <span className="act-grupo-count"> · {grupo.items.length} ítem(s)</span>
              </div>
              <ul className="act-cards-mobile-list">
                {grupo.items.map((a, i) => {
                  const checked = a.id ? seleccion.has(a.id) : false;
                  return (
                    <li
                      key={`m-${a.id || "x"}-${a.equipo}-${grupo.remito}-${i}`}
                      className={`act-card-row ${claseFilaDias(a.dias_fuera)}${checked ? " act-row-selected" : ""}`}
                    >
                      <div className="act-card-row-top">
                        {puedeSeleccionar ? (
                          <label className="act-card-check">
                            <input
                              type="checkbox"
                              checked={checked}
                              disabled={!a.id}
                              onChange={() => a.id && onToggle(a.id)}
                              aria-label={`Seleccionar ${a.equipo || a.dias_fuera}`}
                            />
                          </label>
                        ) : null}
                        <div className="act-card-row-main">
                          <strong className="act-card-row-title">{a.equipo || "Sin nombre"}</strong>
                          <span className={claseBadgeDias(a.dias_fuera)}>{a.dias_fuera} días</span>
                        </div>
                      </div>
                      <div className="act-card-row-meta">
                        <span>Cant. {a.cantidad ?? 1}</span>
                        <span>{etiquetaSector(a.sector) || "—"}</span>
                        <span>{a.proveedor || "Sin proveedor"}</span>
                      </div>
                      <div className="act-card-row-meta" style={{ marginTop: 4 }}>
                        {a.codigo ? <span>Cód: {a.codigo}</span> : null}
                        {a.nro_serie ? <span>Serie: {a.nro_serie}</span> : null}
                        <span>Remito: {a.remito || "—"}</span>
                        {a.n_pedido ? <span>Pedido: {a.n_pedido}</span> : null}
                        {a.n_oc ? <span>OC: {a.n_oc}</span> : null}
                      </div>
                      <div className="act-card-row-meta" style={{ marginTop: 4 }}>
                        <span>Salida: {a.fecha_salida || "—"}</span>
                        {vista === "ingresados" ? (
                          <>
                            <span>Regreso: {a.fecha_regreso || "—"}</span>
                            {a.estado_al_ingreso ? <span>Estado: {a.estado_al_ingreso}</span> : null}
                          </>
                        ) : null}
                      </div>
                      <div className="act-card-row-docs">
                        <span>{a.observaciones || "Sin observaciones"}</span>
                      </div>
                      {puedeEscribir && onEditar ? (
                        <button
                          type="button"
                          className="btn-ghost btn-xs"
                          title="Editar"
                          onClick={() => onEditar(a)}
                          aria-label={`Editar ${a.equipo}`}
                          style={{ marginTop: 4 }}
                        >
                          ✏️ Editar
                        </button>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            </div>
          ));
        })()}
      </div>
    </>
  );
}

function InsightsFuera({ lista }: { lista: ActivoItem[] }) {
  const { ok, aviso, critico, total, topProv } = useMemo(() => {
    let okN = 0;
    let avisoN = 0;
    let criticoN = 0;
    const byProv = new Map<string, number>();
    for (const a of lista) {
      if (a.dias_fuera > DIAS_FUERA_ALERTA) criticoN += 1;
      else if (a.dias_fuera > DIAS_FUERA_AVISO) avisoN += 1;
      else okN += 1;
      const p = (a.proveedor || "").trim() || "Sin proveedor";
      byProv.set(p, (byProv.get(p) ?? 0) + 1);
    }
    const top = [...byProv.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5);
    return { ok: okN, aviso: avisoN, critico: criticoN, total: lista.length, topProv: top };
  }, [lista]);

  if (total === 0) return null;
  const pct = (n: number) => Math.max(total ? (n / total) * 100 : 0, n > 0 ? 4 : 0);

  return (
    <div className="act-insights">
      <div className="act-insight-block">
        <p className="act-insight-title">Antigüedad (ítems fuera)</p>
        <div className="act-aging-bar" role="img" aria-label="Distribución por días fuera">
          {ok > 0 ? <span className="act-aging-seg ok" style={{ flexGrow: pct(ok) }} /> : null}
          {aviso > 0 ? <span className="act-aging-seg aviso" style={{ flexGrow: pct(aviso) }} /> : null}
          {critico > 0 ? <span className="act-aging-seg critico" style={{ flexGrow: pct(critico) }} /> : null}
        </div>
        <div className="act-aging-counts">
          <span className="act-aging-count ok">
            <i /> ≤{DIAS_FUERA_AVISO}d · {fmtNum(ok)}
          </span>
          <span className="act-aging-count aviso">
            <i /> {DIAS_FUERA_AVISO + 1}–{DIAS_FUERA_ALERTA}d · {fmtNum(aviso)}
          </span>
          <span className="act-aging-count critico">
            <i /> &gt;{DIAS_FUERA_ALERTA}d · {fmtNum(critico)}
          </span>
        </div>
      </div>
      <div className="act-insight-block">
        <p className="act-insight-title">Proveedores con más ítems fuera</p>
        {topProv.length === 0 ? (
          <p className="act-card-hint">Sin datos de proveedor.</p>
        ) : (
          <ul className="act-prov-list">
            {topProv.map(([nombre, cant]) => (
              <li key={nombre}>
                <span className="act-prov-name" title={nombre}>
                  {nombre}
                </span>
                <span className="act-prov-bar-wrap">
                  <span
                    className="act-prov-bar"
                    style={{ width: `${Math.max(8, (cant / topProv[0][1]) * 100)}%` }}
                  />
                </span>
                <span className="act-prov-n">{fmtNum(cant)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export default function ActivosPanel({
  data,
  loading,
  error,
  puedeEscribir = false,
  token = null,
  onRetry,
  onRefreshed,
}: Props) {
  const [vista, setVista] = useState<Vista>("fuera");
  const [q, setQ] = useState("");
  const [sector, setSector] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [seleccion, setSeleccion] = useState<Set<string>>(new Set());
  const [modalAbierto, setModalAbierto] = useState(false);
  const [fechaRegreso, setFechaRegreso] = useState(hoyIsoLocal());
  const [estadoIngreso, setEstadoIngreso] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [msgOk, setMsgOk] = useState<string | null>(null);
  const [msgErr, setMsgErr] = useState<string | null>(null);

  // Modal crear salida
  const [modalCrearAbierto, setModalCrearAbierto] = useState(false);
  const [formCrear, setFormCrear] = useState<{
    equipo: string;
    sector: string;
    proveedor: string;
    numero_remito: string;
    codigo: string;
    nro_serie: string;
    numero_pedido: string;
    numero_oc: string;
    cantidad: number;
    fecha_salida: string;
    observaciones: string;
  }>({
    equipo: "", sector: "", proveedor: "", numero_remito: "",
    codigo: "", nro_serie: "", numero_pedido: "", numero_oc: "",
    cantidad: 1, fecha_salida: hoyIsoLocal(), observaciones: "",
  });
  const [guardandoCrear, setGuardandoCrear] = useState(false);

  // Modal editar activo
  const [modalEditarAbierto, setModalEditarAbierto] = useState(false);
  const [editarId, setEditarId] = useState<number | null>(null);
  const [formEditar, setFormEditar] = useState<EditarActivoPayload>({});
  const [guardandoEditar, setGuardandoEditar] = useState(false);

  const qNorm = q.trim().toLowerCase();

  const filtrados = useMemo(() => {
    if (!data) return [] as ActivoItem[];
    const base = vista === "fuera" ? data.lista_fuera : data.lista_ingresados;
    return base.filter((a) => {
      if (sector && a.sector !== sector) return false;
      return matchQuery(a, qNorm);
    });
  }, [data, vista, sector, qNorm]);

  const seleccionadosItems = useMemo(() => {
    if (!data) return [] as ActivoItem[];
    const base = vista === "fuera" ? data.lista_fuera : data.lista_ingresados;
    return base.filter((a) => a.id && seleccion.has(a.id));
  }, [data, seleccion, vista]);

  const puedeSeleccionar = puedeEscribir;

  function toggleId(id: string) {
    setSeleccion((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAll(ids: string[], all: boolean) {
    setSeleccion((prev) => {
      const next = new Set(prev);
      for (const id of ids) {
        if (all) next.add(id);
        else next.delete(id);
      }
      return next;
    });
  }

  async function handleRefresh() {
    setRefreshing(true);
    setMsgOk(null);
    setMsgErr(null);
    try {
      await refreshActivos(token ?? undefined);
      setSeleccion(new Set());
      onRefreshed?.();
    } catch {
      onRetry?.();
    } finally {
      setRefreshing(false);
    }
  }

  async function confirmarRegreso() {
    const ids = [...seleccion];
    if (ids.length === 0) {
      setMsgErr("Seleccioná al menos un ítem.");
      return;
    }
    if (!fechaRegreso) {
      setMsgErr("Indicá la fecha de ingreso.");
      return;
    }
    const estado = estadoIngreso.trim().toUpperCase();
    if (!estado) {
      setMsgErr("Indicá el estado / condición al ingresar.");
      return;
    }
    setGuardando(true);
    setMsgErr(null);
    try {
      const res = await marcarRegreso(
        {
          ids,
          fecha_regreso: fechaRegreso,
          estado_al_ingreso: estado,
        },
        token ?? undefined,
      );
      setMsgOk(res.mensaje);
      setModalAbierto(false);
      setSeleccion(new Set());
      setEstadoIngreso("");
      onRefreshed?.();
    } catch (e) {
      setMsgErr(e instanceof Error ? e.message : "No se pudo marcar el regreso.");
    } finally {
      setGuardando(false);
    }
  }

  async function confirmarRestablecer() {
    const ids = [...seleccion];
    if (ids.length === 0) {
      setMsgErr("Seleccioná al menos un ítem en Ingresados.");
      return;
    }
    const ok = window.confirm(
      `¿Restablecer ${ids.length} ítem(s) a fuera de planta?\nSe borrará la fecha de regreso y el estado de ingreso.`,
    );
    if (!ok) return;
    setGuardando(true);
    setMsgErr(null);
    setMsgOk(null);
    try {
      const res = await restablecerFuera(ids, token ?? undefined);
      setMsgOk(res.mensaje);
      setSeleccion(new Set());
      onRefreshed?.();
    } catch (e) {
      setMsgErr(e instanceof Error ? e.message : "No se pudo restablecer.");
    } finally {
      setGuardando(false);
    }
  }

  // ── Handlers para crear salida ──

  function abrirModalCrear() {
    if (!puedeEscribir) return;
    setFormCrear({
      equipo: "", sector: "", proveedor: "", numero_remito: "",
      codigo: "", nro_serie: "", numero_pedido: "", numero_oc: "",
      cantidad: 1, fecha_salida: hoyIsoLocal(), observaciones: "",
    });
    setMsgOk(null);
    setMsgErr(null);
    setModalCrearAbierto(true);
  }

  function cerrarModalCrear() {
    setModalCrearAbierto(false);
    setMsgErr(null);
  }

  function actualizarFormCrear(campo: string, valor: string | number) {
    setFormCrear((prev) => ({ ...prev, [campo]: valor }));
  }

  async function handleCrearSalida() {
    const { equipo, sector, proveedor, numero_remito } = formCrear;
    if (!equipo.trim() || !sector.trim() || !proveedor.trim() || !numero_remito.trim()) {
      setMsgErr("Completá los campos obligatorios: equipo, sector, proveedor y número de remito.");
      return;
    }
    setGuardandoCrear(true);
    setMsgErr(null);
    try {
      const payload: CrearSalidaPayload = {
        equipo: equipo.trim(),
        sector: sector.trim(),
        proveedor: proveedor.trim(),
        numero_remito: numero_remito.trim(),
        codigo: formCrear.codigo.trim() || undefined,
        nro_serie: formCrear.nro_serie.trim() || undefined,
        numero_pedido: formCrear.numero_pedido.trim() || undefined,
        numero_oc: formCrear.numero_oc.trim() || undefined,
        cantidad: formCrear.cantidad,
        fecha_salida: formCrear.fecha_salida,
        observaciones: formCrear.observaciones.trim() || undefined,
      };
      const res = await crearSalida(payload, token ?? undefined);
      setMsgOk(res.mensaje);
      setModalCrearAbierto(false);
      onRefreshed?.();
    } catch (e) {
      setMsgErr(e instanceof Error ? e.message : "No se pudo crear la salida.");
    } finally {
      setGuardandoCrear(false);
    }
  }

  function validarFormCrear(): boolean {
    const { equipo, sector, proveedor, numero_remito } = formCrear;
    return !!(equipo.trim() && sector.trim() && proveedor.trim() && numero_remito.trim());
  }

  // ── Handlers para editar activo ──

  function abrirModalEditar(a: ActivoItem) {
    if (!puedeEscribir) return;
    const idNum = a.id ? parseInt(a.id.replace(/^f-|^i-/, ""), 10) : null;
    if (!idNum) return;
    setEditarId(idNum);
    setFormEditar({
      equipo: a.equipo,
      sector: a.sector,
      proveedor: a.proveedor,
      numero_remito: a.remito,
      codigo: a.codigo,
      nro_serie: a.nro_serie || "",
      numero_pedido: a.n_pedido || "",
      numero_oc: a.n_oc || "",
      cantidad: a.cantidad,
      fecha_salida: a.fecha_salida || "",
      observaciones: a.observaciones || "",
    });
    setMsgOk(null);
    setMsgErr(null);
    setModalEditarAbierto(true);
  }

  function cerrarModalEditar() {
    setModalEditarAbierto(false);
    setEditarId(null);
    setMsgErr(null);
  }

  function actualizarFormEditar(campo: string, valor: string | number | undefined) {
    setFormEditar((prev) => ({ ...prev, [campo]: valor }));
  }

  async function handleEditarActivo() {
    if (editarId === null) return;
    setGuardandoEditar(true);
    setMsgErr(null);
    try {
      const payload: EditarActivoPayload = { ...formEditar };
      // Limpiar campos vacíos
      for (const key of Object.keys(payload)) {
        if (payload[key as keyof EditarActivoPayload] === "") {
          delete payload[key as keyof EditarActivoPayload];
        }
      }
      await editarActivo(editarId, payload, token ?? undefined);
      setMsgOk("Actualizado correctamente.");
      setModalEditarAbierto(false);
      setEditarId(null);
      onRefreshed?.();
    } catch (e) {
      setMsgErr(e instanceof Error ? e.message : "No se pudo actualizar el activo.");
    } finally {
      setGuardandoEditar(false);
    }
  }

  if (loading && !data) {
    return (
      <div className="act-page">
        <div className="act-skeleton">
          <div className="act-skel" />
          <div className="act-skel" />
          <div className="act-skel" />
          <div className="act-skel" />
        </div>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="act-error">
        <p>{error}</p>
        {onRetry ? (
          <button type="button" className="btn-ghost btn-sm" onClick={onRetry}>
            Reintentar
          </button>
        ) : null}
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="act-page">
      <div className="act-cards">
        <div className="act-card">
          <p className="act-card-label">Fuera de planta</p>
          <p className="act-card-value">{fmtNum(data.fuera_de_planta)}</p>
          <p className="act-card-hint">Pendientes de regreso</p>
        </div>
        <div className="act-card">
          <p className="act-card-label">Promedio días</p>
          <p className="act-card-value">{data.dias_promedio_fuera}</p>
          <p className="act-card-hint">Solo ítems fuera</p>
        </div>
        <div className={`act-card${data.criticos > 0 ? " critico" : ""}`}>
          <p className="act-card-label">Críticos</p>
          <p className="act-card-value">{fmtNum(data.criticos)}</p>
          <p className="act-card-hint">&gt; {DIAS_FUERA_ALERTA} días fuera</p>
        </div>
        <div className="act-card">
          <p className="act-card-label">Ingresados</p>
          <p className="act-card-value">{fmtNum(data.ingresados)}</p>
          <p className="act-card-hint">Ya volvieron a planta</p>
        </div>
      </div>

      {vista === "fuera" ? <InsightsFuera lista={data.lista_fuera} /> : null}

      <div className="act-leyenda" aria-label="Significado de colores por días fuera">
        <span className="act-leyenda-label">Color = días fuera:</span>
        <span className="act-leyenda-item act-row-dias-ok">Verde · ≤ {DIAS_FUERA_AVISO} días</span>
        <span className="act-leyenda-item act-row-dias-aviso">
          Amarillo · {DIAS_FUERA_AVISO + 1}–{DIAS_FUERA_ALERTA} días
        </span>
        <span className="act-leyenda-item act-row-dias-critico">Rojo · más de {DIAS_FUERA_ALERTA} días</span>
      </div>

      <div className="act-toolbar">
        <div className="act-tabs" role="tablist" aria-label="Vista">
          <button
            type="button"
            role="tab"
            aria-selected={vista === "fuera"}
            className={`act-tab${vista === "fuera" ? " active" : ""}`}
            onClick={() => {
              setVista("fuera");
              setSeleccion(new Set());
            }}
          >
            Fuera ({data.fuera_de_planta})
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={vista === "ingresados"}
            className={`act-tab${vista === "ingresados" ? " active" : ""}`}
            onClick={() => {
              setVista("ingresados");
              setSeleccion(new Set());
            }}
          >
            Ingresados ({data.ingresados})
          </button>
        </div>
        <input
          className="act-search"
          type="search"
          placeholder="Buscar equipo, observaciones, proveedor…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          aria-label="Buscar"
        />
        <select
          className="act-select"
          value={sector}
          onChange={(e) => setSector(e.target.value)}
          aria-label="Filtrar sector"
        >
          <option value="">Todos los sectores</option>
          {data.sectores.map((s) => (
            <option key={s} value={s}>
              {etiquetaSector(s)}
            </option>
          ))}
        </select>
<div className="act-toolbar-actions">
           {puedeEscribir && vista === "fuera" ? (
             <button
               type="button"
               className="btn-primary btn-sm"
               onClick={() => void abrirModalCrear()}
             >
               + Nueva salida
             </button>
           ) : null}
           {puedeEscribir && vista === "fuera" ? (
            <button
              type="button"
              className="btn-primary btn-sm"
              disabled={seleccion.size === 0 || guardando}
              onClick={() => {
                setMsgErr(null);
                setFechaRegreso(hoyIsoLocal());
                setModalAbierto(true);
              }}
            >
              Marcar regreso ({seleccion.size})
            </button>
          ) : null}
          {puedeEscribir && vista === "ingresados" ? (
            <button
              type="button"
              className="btn-ghost btn-sm"
              disabled={seleccion.size === 0 || guardando}
              onClick={() => void confirmarRestablecer()}
            >
              Restablecer a fuera ({seleccion.size})
            </button>
          ) : null}
          <button
            type="button"
            className="btn-ghost btn-sm"
            onClick={() => void handleRefresh()}
            disabled={refreshing}
          >
            {refreshing ? "Actualizando…" : "Actualizar"}
          </button>
          <a
            className="btn-ghost btn-sm"
            href={urlActivosPdf(vista)}
            target="_blank"
            rel="noreferrer"
            title={vista === "fuera" ? "Exportar fuera de planta" : "Exportar ingresados"}
          >
            PDF
          </a>
          <a
            className="btn-ghost btn-sm"
            href={urlActivosExcel(vista)}
            target="_blank"
            rel="noreferrer"
            title={vista === "fuera" ? "Exportar fuera de planta" : "Exportar ingresados"}
          >
            Excel
          </a>
        </div>
        <span className="act-toolbar-meta">
          {filtrados.length} filas · act. {fmtFechaIso(data.ultima_actualizacion)}
        </span>
      </div>

      {msgOk ? <p className="act-flash ok">{msgOk}</p> : null}
      {msgErr && !modalAbierto ? <p className="act-flash err">{msgErr}</p> : null}

      {error ? (
        <div className="act-error">
          <p>{error}</p>
          {onRetry ? (
            <button type="button" className="btn-ghost btn-sm" onClick={onRetry}>
              Reintentar
            </button>
          ) : null}
        </div>
      ) : null}

      <section className="act-panel act-panel-full">
        <h2>{vista === "fuera" ? "Listado fuera de planta" : "Listado ingresados"}</h2>
        {puedeEscribir && vista === "fuera" ? (
          <p className="act-card-hint" style={{ marginTop: -6, marginBottom: 10 }}>
            Seleccioná ítems y usá <strong>Marcar regreso</strong>. No edites el mismo Excel en el escritorio al
            mismo tiempo.
          </p>
        ) : null}
        {puedeEscribir && vista === "ingresados" ? (
          <p className="act-card-hint" style={{ marginTop: -6, marginBottom: 10 }}>
            Si un ingreso fue por error, seleccioná y usá <strong>Restablecer a fuera</strong>.
          </p>
        ) : null}
        <Tabla
          items={filtrados}
          vista={vista}
          seleccion={seleccion}
          onToggle={toggleId}
          onToggleAll={toggleAll}
          puedeSeleccionar={puedeSeleccionar}
          puedeEscribir={puedeEscribir}
          onEditar={puedeEscribir ? abrirModalEditar : undefined}
        />
      </section>

      {modalAbierto ? (
        <div className="act-modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="act-modal-title">
          <div className="act-modal">
            <h3 id="act-modal-title">Confirmar ingreso a planta</h3>
            <p className="act-card-hint">
              {seleccionadosItems.length} ítem(s) seleccionado(s). Se moverán a la hoja de ingresados.
            </p>
            <div className="act-modal-list" style={{ maxHeight: 180, overflow: "auto", margin: "8px 0 12px" }}>
              {(() => {
                const grupos = agruparPorRemito(seleccionadosItems);
                return grupos.map((g) => (
                  <div key={`modal-${g.remito}`} style={{ marginBottom: 6 }}>
                    <strong style={{ fontSize: "0.8rem" }}>Remito {g.remito} · {g.items.length} ítem(s)</strong>
                    <ul style={{ margin: "2px 0 0 14px", padding: 0, fontSize: "0.82rem" }}>
                      {g.items.slice(0, 20).map((a) => (
                        <li key={a.id}>
                          {a.equipo || "(sin nombre)"}
                          {a.codigo ? ` · ${a.codigo}` : ""}
                          {a.cantidad && a.cantidad !== 1 ? ` · x${a.cantidad}` : ""}
                        </li>
                      ))}
                      {g.items.length > 20 ? <li>… y {g.items.length - 20} más en este remito</li> : null}
                    </ul>
                  </div>
                ));
              })()}
              {seleccionadosItems.length > 40 ? (
                <p className="act-card-hint" style={{ marginTop: 6 }}>
                  … y {seleccionadosItems.length - 40} más en total
                </p>
              ) : null}
            </div>
            <label className="act-field">
              Fecha de ingreso a planta *
              <input
                type="date"
                value={fechaRegreso}
                onChange={(e) => setFechaRegreso(e.target.value)}
              />
            </label>
            <label className="act-field">
              Estado / condición al ingresar *
              <textarea
                rows={3}
                value={estadoIngreso}
                onChange={(e) => setEstadoIngreso(e.target.value)}
                placeholder="Ej. REPARADO, REVISADO OK, PARA BAJA"
              />
            </label>
            {msgErr ? <p className="act-flash err">{msgErr}</p> : null}
            <div className="act-modal-actions">
              <button
                type="button"
                className="btn-ghost btn-sm"
                disabled={guardando}
                onClick={() => {
                  setModalAbierto(false);
                  setMsgErr(null);
                }}
              >
                Cancelar
              </button>
              <button
                type="button"
                className="btn-primary btn-sm"
                disabled={guardando}
                onClick={() => void confirmarRegreso()}
              >
                {guardando ? "Guardando…" : "Confirmar ingreso"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {/* ── Modal Crear Salida ── */}
      {modalCrearAbierto ? (
        <div className="act-modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="act-modal-crear">
          <div className="act-modal">
            <h3 id="act-modal-crear">Nueva salida de activo</h3>
            <p className="act-card-hint">Campos marcados con * son obligatorios.</p>
            {msgErr ? <p className="act-flash err">{msgErr}</p> : null}
            {msgOk ? <p className="act-flash ok">{msgOk}</p> : null}
            <label className="act-field">
              Equipo / repuesto *
              <input
                type="text"
                value={formCrear.equipo}
                onChange={(e) => actualizarFormCrear("equipo", e.target.value)}
                placeholder="Ej. MOTOR DIÉSEL MODEL X"
                maxLength={200}
              />
            </label>
            <label className="act-field">
              Sector *
              <input
                type="text"
                value={formCrear.sector}
                onChange={(e) => actualizarFormCrear("sector", e.target.value)}
                placeholder="Ej. MANTENIMIENTO"
                maxLength={100}
              />
            </label>
            <label className="act-field">
              Proveedor *
              <input
                type="text"
                value={formCrear.proveedor}
                onChange={(e) => actualizarFormCrear("proveedor", e.target.value)}
                placeholder="Ej. PARTES S.A."
                maxLength={150}
              />
            </label>
            <label className="act-field">
              Nº remito *
              <input
                type="text"
                value={formCrear.numero_remito}
                onChange={(e) => actualizarFormCrear("numero_remito", e.target.value)}
                placeholder="Ej. 12345-6"
                maxLength={40}
              />
            </label>
            <div className="sal-row">
              <label className="act-field sal-grow">
                Código
                <input
                  type="text"
                  value={formCrear.codigo}
                  onChange={(e) => actualizarFormCrear("codigo", e.target.value)}
                  placeholder="Opcional"
                  maxLength={40}
                />
              </label>
              <label className="act-field sal-grow">
                N° serie
                <input
                  type="text"
                  value={formCrear.nro_serie}
                  onChange={(e) => actualizarFormCrear("nro_serie", e.target.value)}
                  placeholder="Opcional"
                  maxLength={40}
                />
              </label>
            </div>
            <div className="sal-row">
              <label className="act-field sal-grow">
                Nº pedido
                <input
                  type="text"
                  value={formCrear.numero_pedido}
                  onChange={(e) => actualizarFormCrear("numero_pedido", e.target.value)}
                  placeholder="Opcional"
                  maxLength={40}
                />
              </label>
              <label className="act-field sal-grow">
                Nº OC
                <input
                  type="text"
                  value={formCrear.numero_oc}
                  onChange={(e) => actualizarFormCrear("numero_oc", e.target.value)}
                  placeholder="Opcional"
                  maxLength={40}
                />
              </label>
            </div>
            <div className="sal-row">
              <label className="act-field">
                Cantidad *
                <input
                  type="number"
                  min={1}
                  value={formCrear.cantidad}
                  onChange={(e) => actualizarFormCrear("cantidad", parseInt(e.target.value) || 1)}
                />
              </label>
              <label className="act-field">
                Fecha salida *
                <input
                  type="date"
                  value={formCrear.fecha_salida}
                  onChange={(e) => actualizarFormCrear("fecha_salida", e.target.value)}
                />
              </label>
            </div>
            <label className="act-field">
              Observaciones
              <textarea
                rows={3}
                value={formCrear.observaciones}
                onChange={(e) => actualizarFormCrear("observaciones", e.target.value)}
                placeholder="Opcional"
                maxLength={500}
              />
            </label>
            <div className="act-modal-actions">
              <button
                type="button"
                className="btn-ghost btn-sm"
                disabled={guardandoCrear}
                onClick={() => cerrarModalCrear()}
              >
                Cancelar
              </button>
              <button
                type="button"
                className="btn-primary btn-sm"
                disabled={!validarFormCrear() || guardandoCrear}
                onClick={() => void handleCrearSalida()}
              >
                {guardandoCrear ? "Creando…" : "Crear salida"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {/* ── Modal Editar Activo ── */}
      {modalEditarAbierto && editarId !== null ? (
        <div className="act-modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="act-modal-editar">
          <div className="act-modal">
            <h3 id="act-modal-editar">Editar activo #{editarId}</h3>
            <p className="act-card-hint">Podés cambiar cualquier dato. El estado y la fecha de regreso no se modifican por esta vía.</p>
            {msgErr ? <p className="act-flash err">{msgErr}</p> : null}
            {msgOk ? <p className="act-flash ok">{msgOk}</p> : null}
            <label className="act-field">
              Equipo *
              <input
                type="text"
                value={formEditar.equipo ?? ""}
                onChange={(e) => actualizarFormEditar("equipo", e.target.value)}
                maxLength={200}
              />
            </label>
            <label className="act-field">
              Sector *
              <input
                type="text"
                value={formEditar.sector ?? ""}
                onChange={(e) => actualizarFormEditar("sector", e.target.value)}
                maxLength={100}
              />
            </label>
            <label className="act-field">
              Proveedor *
              <input
                type="text"
                value={formEditar.proveedor ?? ""}
                onChange={(e) => actualizarFormEditar("proveedor", e.target.value)}
                maxLength={150}
              />
            </label>
            <label className="act-field">
              Nº remito *
              <input
                type="text"
                value={formEditar.numero_remito ?? ""}
                onChange={(e) => actualizarFormEditar("numero_remito", e.target.value)}
                maxLength={40}
              />
            </label>
            <div className="sal-row">
              <label className="act-field sal-grow">
                Código
                <input
                  type="text"
                  value={formEditar.codigo ?? ""}
                  onChange={(e) => actualizarFormEditar("codigo", e.target.value)}
                  maxLength={40}
                />
              </label>
              <label className="act-field sal-grow">
                N° serie
                <input
                  type="text"
                  value={formEditar.nro_serie ?? ""}
                  onChange={(e) => actualizarFormEditar("nro_serie", e.target.value)}
                  maxLength={40}
                />
              </label>
            </div>
            <div className="sal-row">
              <label className="act-field sal-grow">
                Nº pedido
                <input
                  type="text"
                  value={formEditar.numero_pedido ?? ""}
                  onChange={(e) => actualizarFormEditar("numero_pedido", e.target.value)}
                  maxLength={40}
                />
              </label>
              <label className="act-field sal-grow">
                Nº OC
                <input
                  type="text"
                  value={formEditar.numero_oc ?? ""}
                  onChange={(e) => actualizarFormEditar("numero_oc", e.target.value)}
                  maxLength={40}
                />
              </label>
            </div>
            <div className="sal-row">
              <label className="act-field">
                Cantidad
                <input
                  type="number"
                  min={1}
                  value={formEditar.cantidad ?? 1}
                  onChange={(e) => actualizarFormEditar("cantidad", parseInt(e.target.value) || 1)}
                />
              </label>
              <label className="act-field">
                Fecha salida
                <input
                  type="date"
                  value={formEditar.fecha_salida ?? ""}
                  onChange={(e) => actualizarFormEditar("fecha_salida", e.target.value)}
                />
              </label>
            </div>
            <label className="act-field">
              Observaciones
              <textarea
                rows={3}
                value={formEditar.observaciones ?? ""}
                onChange={(e) => actualizarFormEditar("observaciones", e.target.value)}
                maxLength={500}
              />
            </label>
            <div className="act-modal-actions">
              <button
                type="button"
                className="btn-ghost btn-sm"
                disabled={guardandoEditar}
                onClick={() => cerrarModalEditar()}
              >
                Cancelar
              </button>
              <button
                type="button"
                className="btn-primary btn-sm"
                disabled={guardandoEditar}
                onClick={() => void handleEditarActivo()}
              >
                {guardandoEditar ? "Guardando…" : "Guardar cambios"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
