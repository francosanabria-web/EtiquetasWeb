import ImportPanel from "./components/ImportPanel";
import MappingWizard from "./components/MappingWizard";
import Dashboard from "./components/Dashboard";
import FilterBar from "./components/FilterBar";
import DataTable from "./components/DataTable";
import { useKpiStore } from "./hooks/useKpiStore";
import { formatearFechaHora } from "./lib/kpiEngine";
import { CAMPOS_DATO, ETIQUETAS_CAMPO } from "./types/kpi";

const SHELL_URL = import.meta.env.VITE_SHELL_URL;

export default function App() {
  const store = useKpiStore();
  const {
    cargando,
    registros,
    registrosFiltrados,
    config,
    setConfig,
    meta,
    filtros,
    setFiltros,
    vista,
    setVista,
    parseo,
    error,
    mensaje,
    resumen,
    porLinea,
    porObra,
    porCategoria,
    serie,
    lineasDisponibles,
    obrasDisponibles,
    iniciarImportacion,
    confirmarMapeo,
    borrarCache,
    setError,
    setMensaje,
  } = store;

  const sinDatos = !registros.length;

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-icon">📈</span>
          <div>
            <h1>KPIs — Mantenimiento</h1>
            <p className="brand-sub">SistemasPañol · Jefatura y gerencia</p>
          </div>
        </div>
        <nav className="nav-tabs">
          <button
            type="button"
            className={vista === "dashboard" ? "active" : ""}
            onClick={() => setVista("dashboard")}
            disabled={sinDatos && vista !== "config"}
          >
            Panel
          </button>
          <button
            type="button"
            className={vista === "datos" ? "active" : ""}
            onClick={() => setVista("datos")}
            disabled={sinDatos}
          >
            Datos
          </button>
          <button
            type="button"
            className={vista === "config" ? "active" : ""}
            onClick={() => setVista("config")}
          >
            Configuración
          </button>
        </nav>
        <div className="top-actions">
          {SHELL_URL && (
            <a className="btn-ghost btn-sm" href={SHELL_URL}>
              ← Portal
            </a>
          )}
        </div>
      </header>

      <main className="main">
        {(error || mensaje) && (
          <div className={`banner ${error ? "error" : "ok"}`}>
            {error ?? mensaje}
            <button
              type="button"
              className="banner-close"
              onClick={() => {
                setError(null);
                setMensaje(null);
              }}
              aria-label="Cerrar"
            >
              ×
            </button>
          </div>
        )}

        {meta && (
          <div className="meta-bar">
            <span>
              <strong>Última importación:</strong> {meta.nombreArchivo} ·{" "}
              {formatearFechaHora(meta.importadoEn)}
            </span>
            <span>
              {meta.filasValidas} registros
              {meta.filasDescartadas > 0 && ` · ${meta.filasDescartadas} descartados`}
            </span>
          </div>
        )}

        {cargando && <div className="loading">Procesando…</div>}

        {!cargando && vista === "config" && parseo && config && (
          <MappingWizard
            config={config}
            parseo={parseo}
            onChange={setConfig}
            onConfirmar={confirmarMapeo}
            onCancelar={() => {
              setVista(registros.length ? "dashboard" : "dashboard");
            }}
          />
        )}

        {!cargando && vista === "config" && !parseo && (
          <section className="panel">
            <header className="panel-head">
              <h2>Configuración guardada</h2>
              <p className="sub">
                El mapeo de columnas y los datos importados persisten en este navegador (caché local).
              </p>
            </header>
            {config ? (
              <dl className="config-dl">
                <dt>Hoja Excel</dt>
                <dd>{config.hoja}</dd>
                {CAMPOS_DATO.map((c) =>
                  config.mapeo[c] ? (
                    <div key={c} className="config-row">
                      <dt>{ETIQUETAS_CAMPO[c]}</dt>
                      <dd>{config.mapeo[c]}</dd>
                    </div>
                  ) : null
                )}
              </dl>
            ) : (
              <p className="sub">Importá una planilla para definir el mapeo.</p>
            )}
            <ImportPanel onArchivo={iniciarImportacion} deshabilitado={cargando} />
            <div className="actions-row">
              <button type="button" className="btn-danger btn-sm" onClick={() => void borrarCache()}>
                Borrar caché local
              </button>
            </div>
          </section>
        )}

        {!cargando && vista === "dashboard" && (
          <>
            {sinDatos ? (
              <div className="empty-state">
                <h2>Interpretá tus KPIs desde Excel</h2>
                <p>
                  Importá la planilla de gastos del mes. El sistema traduce las columnas a indicadores
                  visuales: totales, evolución, desglose por línea y obra.
                </p>
                <ImportPanel onArchivo={iniciarImportacion} />
              </div>
            ) : (
              <>
                <div className="toolbar">
                  <ImportPanel onArchivo={iniciarImportacion} deshabilitado={cargando} />
                </div>
                <Dashboard
                  registrosFiltrados={registrosFiltrados}
                  resumen={resumen}
                  porLinea={porLinea}
                  porObra={porObra}
                  porCategoria={porCategoria}
                  serie={serie}
                  filtros={filtros}
                  setFiltros={setFiltros}
                  lineasDisponibles={lineasDisponibles}
                  obrasDisponibles={obrasDisponibles}
                  registros={registros}
                />
              </>
            )}
          </>
        )}

        {!cargando && vista === "datos" && !sinDatos && (
          <section className="panel">
            <header className="panel-head">
              <h2>Tabla completa</h2>
              <span className="badge">{registrosFiltrados.length} filas</span>
            </header>
            <FilterBar
              filtros={filtros}
              lineas={lineasDisponibles}
              obras={obrasDisponibles}
              onChange={setFiltros}
              onReset={() => {
                const fechas = registros.map((r) => r.fecha).sort();
                setFiltros({
                  fechaDesde: fechas[0] ?? "",
                  fechaHasta: fechas[fechas.length - 1] ?? "",
                  lineas: [],
                  obras: [],
                });
              }}
            />
            <DataTable registros={registrosFiltrados} maxFilas={500} />
          </section>
        )}
      </main>

      <footer className="footer">
        Datos en caché local del navegador · Reimportá la planilla cuando se actualice el Excel del mes
      </footer>
    </div>
  );
}
