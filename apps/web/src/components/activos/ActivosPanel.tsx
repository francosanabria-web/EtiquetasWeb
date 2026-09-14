import { useMemo, useState } from "react";
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
  type ActivoItem,
  type ActivosResumen,
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
  const hay = [a.equipo, a.codigo, a.remito, a.n_pedido, a.n_oc, a.proveedor, a.sector, a.nro_serie]
    .join(" ")
    .toLowerCase();
  return hay.includes(q);
}

function Tabla({
  items,
  vista,
  seleccion,
  onToggle,
  onToggleAll,
  puedeSeleccionar,
}: {
  items: ActivoItem[];
  vista: Vista;
  seleccion: Set<string>;
  onToggle: (id: string) => void;
  onToggleAll: (ids: string[], all: boolean) => void;
  puedeSeleccionar: boolean;
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
              <th>Equipo / repuesto</th>
              <th>Código</th>
              <th>Remito</th>
              <th>Pedido</th>
              <th>OC</th>
              <th>Sector</th>
              <th>Días</th>
              <th>Proveedor</th>
              <th>{vista === "ingresados" ? "Regreso" : "Salida"}</th>
              {vista === "ingresados" ? <th>Estado ingreso</th> : null}
            </tr>
          </thead>
          <tbody>
            {items.map((a, i) => {
              const checked = a.id ? seleccion.has(a.id) : false;
              return (
                <tr
                  key={`${a.id || "x"}-${a.codigo}-${a.remito}-${i}`}
                  className={`${claseFilaDias(a.dias_fuera)}${checked ? " act-row-selected" : ""}`}
                >
                  {puedeSeleccionar ? (
                    <td className="act-td-check">
                      <input
                        type="checkbox"
                        checked={checked}
                        disabled={!a.id}
                        onChange={() => a.id && onToggle(a.id)}
                        aria-label={`Seleccionar ${a.equipo || a.codigo}`}
                      />
                    </td>
                  ) : null}
                  <td className="act-td-desc" title={a.equipo}>
                    {a.equipo || "—"}
                  </td>
                  <td>{a.codigo || "—"}</td>
                  <td className="act-td-doc">{a.remito || "—"}</td>
                  <td className="act-td-doc">{a.n_pedido || "—"}</td>
                  <td className="act-td-doc">{a.n_oc || "—"}</td>
                  <td>{etiquetaSector(a.sector) || "—"}</td>
                  <td>
                    <span className={claseBadgeDias(a.dias_fuera)}>{a.dias_fuera}</span>
                  </td>
                  <td className="act-td-prov" title={a.proveedor}>
                    {a.proveedor || "—"}
                  </td>
                  <td className="act-td-doc">
                    {vista === "ingresados" ? a.fecha_regreso || "—" : a.fecha_salida || "—"}
                  </td>
                  {vista === "ingresados" ? (
                    <td>{(a.estado_al_ingreso || a.estado || "").replace(/_/g, " ") || "—"}</td>
                  ) : null}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <ul className="act-cards-mobile">
        {items.map((a, i) => {
          const checked = a.id ? seleccion.has(a.id) : false;
          return (
            <li
              key={`m-${a.id || "x"}-${a.codigo}-${i}`}
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
                      aria-label={`Seleccionar ${a.equipo || a.codigo}`}
                    />
                  </label>
                ) : null}
                <div className="act-card-row-main">
                  <strong className="act-card-row-title">{a.equipo || a.codigo || "Sin nombre"}</strong>
                  <span className={claseBadgeDias(a.dias_fuera)}>{a.dias_fuera} días</span>
                </div>
              </div>
              <div className="act-card-row-meta">
                <span>{a.codigo || "—"}</span>
                <span>{etiquetaSector(a.sector) || "—"}</span>
                <span>{a.proveedor || "Sin proveedor"}</span>
              </div>
              <div className="act-card-row-docs">
                <span>Remito {a.remito || "—"}</span>
                <span>
                  {vista === "ingresados" ? "Regreso" : "Salida"}{" "}
                  {vista === "ingresados" ? a.fecha_regreso || "—" : a.fecha_salida || "—"}
                </span>
              </div>
            </li>
          );
        })}
      </ul>
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
          placeholder="Buscar equipo, código, remito…"
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
        />
      </section>

      {modalAbierto ? (
        <div className="act-modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="act-modal-title">
          <div className="act-modal">
            <h3 id="act-modal-title">Confirmar ingreso a planta</h3>
            <p className="act-card-hint">
              {seleccionadosItems.length} ítem(s) seleccionado(s). Se moverán a la hoja de ingresados.
            </p>
            <ul className="act-modal-list">
              {seleccionadosItems.slice(0, 8).map((a) => (
                <li key={a.id}>
                  {a.equipo || "(sin nombre)"}
                  {a.codigo ? ` · ${a.codigo}` : ""}
                  {a.remito ? ` · remito ${a.remito}` : ""}
                </li>
              ))}
              {seleccionadosItems.length > 8 ? (
                <li>… y {seleccionadosItems.length - 8} más</li>
              ) : null}
            </ul>
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
    </div>
  );
}
