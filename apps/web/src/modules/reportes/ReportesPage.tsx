import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  fetchFiltros,
  fetchMovimientos,
  fetchResumen,
  fmtNum,
  fmtPesos,
  refreshReportes,
  urlExportXlsx,
  type FiltrosOpciones,
  type FiltrosQuery,
  type MovimientoItem,
  type ResumenReportes,
} from "../../api/reportesClient";
import "../../styles/reportes.css";

const LIMITE = 100;

const emptyFiltros: FiltrosQuery = {
  fecha_desde: "",
  fecha_hasta: "",
  sector: "",
  operario: "",
  codigo: "",
  numero_orden: "",
  tipo_comprobante: "",
  q: "",
};

export default function ReportesPage() {
  const [opciones, setOpciones] = useState<FiltrosOpciones | null>(null);
  const [filtros, setFiltros] = useState<FiltrosQuery>({ ...emptyFiltros });
  const [aplicados, setAplicados] = useState<FiltrosQuery>({ ...emptyFiltros });
  const [items, setItems] = useState<MovimientoItem[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [resumen, setResumen] = useState<ResumenReportes | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [fuentePath, setFuentePath] = useState("");

  const cargar = useCallback(async (f: FiltrosQuery, off: number) => {
    setCargando(true);
    setError(null);
    try {
      const query = { ...f, limite: LIMITE, offset: off };
      const [mov, res, opts] = await Promise.all([
        fetchMovimientos(query),
        fetchResumen(f),
        opciones ? Promise.resolve(opciones) : fetchFiltros(),
      ]);
      setItems(mov.items);
      setTotal(mov.total);
      setOffset(off);
      setResumen(res);
      if (!opciones) setOpciones(opts);
      setFuentePath(mov.fuente?.path || res.fuente?.path || "");
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo cargar reportes.");
    } finally {
      setCargando(false);
    }
  }, [opciones]);

  useEffect(() => {
    void cargar(aplicados, 0);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- carga inicial
  }, []);

  function setCampo<K extends keyof FiltrosQuery>(key: K, value: FiltrosQuery[K]) {
    setFiltros((prev) => ({ ...prev, [key]: value }));
  }

  function aplicar(e?: FormEvent) {
    e?.preventDefault();
    setAplicados({ ...filtros });
    void cargar(filtros, 0);
  }

  function limpiar() {
    setFiltros({ ...emptyFiltros });
    setAplicados({ ...emptyFiltros });
    void cargar(emptyFiltros, 0);
  }

  async function recargarArchivo() {
    setCargando(true);
    setError(null);
    try {
      await refreshReportes();
      const opts = await fetchFiltros();
      setOpciones(opts);
      await cargar(aplicados, 0);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo recargar.");
      setCargando(false);
    }
  }

  const pagina = Math.floor(offset / LIMITE) + 1;
  const paginas = Math.max(1, Math.ceil(total / LIMITE));

  return (
    <div className="rep-page">
      <header className="page-header rep-header">
        <div>
          <h1>Reportes</h1>
        </div>
        <div className="rep-header-actions">
          <a className="btn btn-secondary" href={urlExportXlsx(aplicados)} download>
            Exportar Excel
          </a>
          <button type="button" className="btn btn-secondary" onClick={() => void recargarArchivo()}>
            Recargar datos
          </button>
        </div>
      </header>

      {fuentePath ? (
        <p className="rep-fuente">
          Fuente: <code>{fuentePath}</code>
          {resumen ? (
            <>
              {" "}
              — {resumen.filas.toLocaleString("es-AR")} filas · {fmtPesos(resumen.monto_total)}
            </>
          ) : null}
        </p>
      ) : null}

      <form className="rep-filtros" onSubmit={aplicar}>
        <label>
          Desde
          <input
            type="date"
            value={filtros.fecha_desde || ""}
            onChange={(e) => setCampo("fecha_desde", e.target.value)}
          />
        </label>
        <label>
          Hasta
          <input
            type="date"
            value={filtros.fecha_hasta || ""}
            onChange={(e) => setCampo("fecha_hasta", e.target.value)}
          />
        </label>
        <label>
          Sector
          <select
            value={filtros.sector || ""}
            onChange={(e) => setCampo("sector", e.target.value)}
          >
            <option value="">Todos</option>
            {(opciones?.sectores || []).map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <label>
          Operario
          <select
            value={filtros.operario || ""}
            onChange={(e) => setCampo("operario", e.target.value)}
          >
            <option value="">Todos</option>
            {(opciones?.operarios || []).map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <label>
          Código
          <input
            type="text"
            placeholder="ej. RODA"
            value={filtros.codigo || ""}
            onChange={(e) => setCampo("codigo", e.target.value)}
          />
        </label>
        <label>
          N° orden
          <input
            type="text"
            placeholder="OT-…"
            value={filtros.numero_orden || ""}
            onChange={(e) => setCampo("numero_orden", e.target.value)}
          />
        </label>
        <label>
          Comprobante
          <select
            value={filtros.tipo_comprobante || ""}
            onChange={(e) => setCampo("tipo_comprobante", e.target.value)}
          >
            <option value="">Todos</option>
            {(opciones?.tipos_comprobante || []).map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <label className="rep-q">
          Buscar
          <input
            type="search"
            placeholder="código, descripción, operario…"
            value={filtros.q || ""}
            onChange={(e) => setCampo("q", e.target.value)}
          />
        </label>
        <div className="rep-filtros-actions">
          <button type="submit" className="btn btn-primary">
            Filtrar
          </button>
          <button type="button" className="btn btn-secondary" onClick={limpiar}>
            Limpiar
          </button>
        </div>
      </form>

      {error ? <p className="rep-error">{error}</p> : null}

      {resumen && !error ? (
        <section className="rep-resumen" aria-label="Resumen filtrado">
          <div className="rep-kpi">
            <span className="rep-kpi-label">Filas</span>
            <span className="rep-kpi-value">{resumen.filas.toLocaleString("es-AR")}</span>
          </div>
          <div className="rep-kpi">
            <span className="rep-kpi-label">Monto total</span>
            <span className="rep-kpi-value">{fmtPesos(resumen.monto_total)}</span>
          </div>
          <div className="rep-kpi">
            <span className="rep-kpi-label">Cantidad</span>
            <span className="rep-kpi-value">{fmtNum(resumen.cantidad_total)}</span>
          </div>
          <div className="rep-agregados">
            <h3>Por sector</h3>
            <ul>
              {resumen.por_sector.slice(0, 6).map((r) => (
                <li key={r.sector}>
                  <span>{r.sector}</span>
                  <span>{fmtPesos(r.monto)}</span>
                </li>
              ))}
              {!resumen.por_sector.length ? <li className="muted">Sin datos</li> : null}
            </ul>
          </div>
          <div className="rep-agregados">
            <h3>Por operario</h3>
            <ul>
              {resumen.por_operario.slice(0, 6).map((r) => (
                <li key={r.operario}>
                  <span>{r.operario}</span>
                  <span>{fmtPesos(r.monto)}</span>
                </li>
              ))}
              {!resumen.por_operario.length ? <li className="muted">Sin datos</li> : null}
            </ul>
          </div>
          <div className="rep-agregados">
            <h3>Por comprobante</h3>
            <ul>
              {(resumen.por_tipo_comprobante || []).slice(0, 6).map((r) => (
                <li key={r.tipo_comprobante}>
                  <span>{r.tipo_comprobante}</span>
                  <span>{fmtPesos(r.monto)}</span>
                </li>
              ))}
              {!(resumen.por_tipo_comprobante || []).length ? (
                <li className="muted">Sin datos</li>
              ) : null}
            </ul>
          </div>
          <div className="rep-agregados">
            <h3>Por mes</h3>
            <ul>
              {(resumen.por_mes || []).slice(0, 6).map((r) => (
                <li key={r.mes}>
                  <span>{r.mes}</span>
                  <span>{fmtPesos(r.monto)}</span>
                </li>
              ))}
              {!(resumen.por_mes || []).length ? <li className="muted">Sin datos</li> : null}
            </ul>
          </div>
        </section>
      ) : null}

      <section className="rep-tabla-wrap">
        <div className="rep-tabla-head">
          <h2>Movimientos</h2>
          <span className="sub">
            {cargando ? "Cargando…" : `${total.toLocaleString("es-AR")} resultado(s)`}
          </span>
        </div>
        <div className="rep-tabla-scroll">
          <table className="rep-tabla">
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Código</th>
                <th>Descripción</th>
                <th>Cant.</th>
                <th>P. unit.</th>
                <th>Monto</th>
                <th>Comprob.</th>
                <th>Orden</th>
                <th>Máquina/sitio</th>
                <th>Operario</th>
                <th>Sector</th>
              </tr>
            </thead>
            <tbody>
              {!cargando && !items.length ? (
                <tr>
                  <td colSpan={11} className="rep-empty">
                    No hay movimientos con estos filtros.
                  </td>
                </tr>
              ) : null}
              {items.map((m, i) => (
                <tr key={`${m.fecha}-${m.codigo}-${m.numero_orden}-${i}`}>
                  <td>{m.fecha}</td>
                  <td className="mono">{m.codigo}</td>
                  <td>{m.descripcion}</td>
                  <td className="num">{fmtNum(m.cantidad)}</td>
                  <td className="num">{fmtPesos(m.precio_unitario)}</td>
                  <td className="num">{fmtPesos(m.monto_total_salida)}</td>
                  <td>{m.tipo_comprobante}</td>
                  <td className="mono">{m.numero_orden}</td>
                  <td>{m.maquina_sitio}</td>
                  <td>{m.operario}</td>
                  <td>{m.sector}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {total > LIMITE ? (
          <div className="rep-pager">
            <button
              type="button"
              className="btn btn-secondary"
              disabled={offset <= 0 || cargando}
              onClick={() => void cargar(aplicados, Math.max(0, offset - LIMITE))}
            >
              Anterior
            </button>
            <span>
              Página {pagina} / {paginas}
            </span>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={offset + LIMITE >= total || cargando}
              onClick={() => void cargar(aplicados, offset + LIMITE)}
            >
              Siguiente
            </button>
          </div>
        ) : null}
      </section>
    </div>
  );
}
