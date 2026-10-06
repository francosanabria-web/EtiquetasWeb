import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  enviarMailManual,
  fetchFiltros,
  fetchMovimientos,
  fetchResumen,
  fmtNum,
  fmtPesos,
  refreshReportes,
  urlExportAtenciones,
  urlExportXlsx,
  type FiltrosOpciones,
  type FiltrosQuery,
  type MovimientoItem,
  type ResumenReportes,
} from "../../api/reportesClient";
import { kpiAtenciones } from "../../api/salidasClient";
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
  const [tipoManual, setTipoManual] = useState<"diario" | "activos">("diario");
  const [fechaManual, setFechaManual] = useState(() =>
    new Date(Date.now() - 86400000).toISOString().slice(0, 10),
  );
  const [destsManual, setDestsManual] = useState("");
  const [enviandoManual, setEnviandoManual] = useState(false);
  const [resultadoManual, setResultadoManual] = useState<string | null>(null);
  const [atDesde, setAtDesde] = useState("");
  const [atHasta, setAtHasta] = useState("");
  const [atFormato, setAtFormato] = useState<"xlsx" | "csv">("xlsx");
  const [modal, setModal] = useState<null | "envio" | "atenciones">(null);
  const [kpiAtencion, setKpiAtencion] = useState<{total: number; con_retiro: number; sin_retiro: number} | null>(null);
  const [previewMail, setPreviewMail] = useState<{html: string; asunto: string} | null>(null);

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

  useEffect(() => {
    let mounted = true;
    if (atDesde && atHasta) {
      kpiAtenciones({ desde: atDesde, hasta: atHasta })
        .then((data) => {
          if (mounted) {
            const dias = Array.isArray(data.por_dia) ? data.por_dia : [];
            if (dias.length) {
              setKpiAtencion({
                total: dias.reduce((a, d) => a + (Number(d.total) || 0), 0),
                con_retiro: dias.reduce((a, d) => a + (Number(d.con_retiro) || 0), 0),
                sin_retiro: dias.reduce((a, d) => a + (Number(d.sin_retiro) || 0), 0),
              });
            } else {
              setKpiAtencion({ total: 0, con_retiro: 0, sin_retiro: 0 });
            }
          }
        })
        .catch((e) => {
          console.error("KPI atenciones error:", e);
          if (mounted) setKpiAtencion(null);
        });
    } else {
      setKpiAtencion(null);
    }
    return () => { mounted = false };
  }, [atDesde, atHasta]);

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

  async function enviarManual() {
    const dests = Array.from(
      new Set(
        destsManual
          .split(/[,;\n]+/)
          .map((d) => d.trim())
          .filter((d) => d.includes("@")),
      ),
    );
    if (!dests.length) {
      setResultadoManual("Cargá al menos un destinatario válido.");
      return;
    }
    setEnviandoManual(true);
    setResultadoManual(null);
    try {
      const r = await enviarMailManual({
        fecha: fechaManual || undefined,
        tipo: tipoManual,
        destinatarios: dests,
      });
      setResultadoManual(
        r.enviado
          ? `Enviado (${r.fecha || fechaManual}, ${r.filas ?? "?"} filas).`
          : `No enviado: ${r.error || "sin movimientos"}.`,
      );
    } catch (e) {
      setResultadoManual(e instanceof Error ? e.message : "No se pudo enviar.");
    } finally {
      setEnviandoManual(false);
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
          <button type="button" className="btn btn-secondary" onClick={() => setModal("envio")}>
            Envío manual
          </button>
          <button type="button" className="btn btn-secondary" onClick={() => setModal("atenciones")}>
            Atenciones
          </button>
          <button type="button" className="btn btn-secondary" onClick={() => void recargarArchivo()}>
            Recargar datos
          </button>
        </div>
      </header>

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

      {modal ? (
        <div
          className="rep-modal-backdrop"
          onClick={() => {
            if (!enviandoManual) setModal(null);
          }}
        >
          <div
            className="rep-modal"
            role="dialog"
            aria-modal="true"
            aria-label={modal === "envio" ? "Envío manual" : "Atenciones"}
            onClick={(e) => e.stopPropagation()}
          >
            {modal === "envio" ? (
              <>
                <h2>Envío manual</h2>
                {previewMail ? (
                  <>
                    <div className="rep-fuente" style={{ marginBottom: 12, padding: 8, background: "#f0f4f8", borderRadius: 6 }}>
                      <h4>Vista previa HTML</h4>
                      <iframe
                        srcDoc={previewMail.html}
                        style={{
                          width: "100%",
                          height: 300,
                          border: "1px solid var(--border)",
                          borderRadius: 8,
                          background: "#fff",
                          fontFamily: "inherit",
                        }}
                      />
                      <button
                        type="button"
                        className="btn btn-secondary"
                        style={{ marginTop: 8, marginRight: 8 }}
                        onClick={() => {
                          const w = window.open(
                            "",
                            "_blank",
                            "width=900,height=700,scrollbars=yes,resizable=yes",
                          );
                          if (!w) return;
                          const asunto =
                            previewMail.asunto.replace(
                              /[<>&"]/g,
                              (c): string => {
                                switch (c) {
                                  case "<":
                                    return "<";
                                  case ">":
                                    return ">";
                                  case "&":
                                    return "&";
                                  case '"':
                                    return '"';
                                  default:
                                    return c;
                                }
                              },
                            );
                          w.document.write(
                            `<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>${asunto}</title>
<style>@page{margin:12mm}body{margin:0;padding:12px}</style></head>
<body>${previewMail.html}</body></html>`,
                          );
                          w.document.close();
                          w.focus();
                          w.onload = () => {
                            w.print();
                          };
                        }}
                      >
                        🖨️ Imprimir / PDF
                      </button>
                      <div style={{ marginTop: 8, fontSize: "0.85rem", color: "var(--muted)" }}>
                        {previewMail.asunto}
                      </div>
                      <button
                        type="button"
                        className="btn btn-link"
                        style={{ marginLeft: 8, textDecoration: "underline", fontSize: "0.85rem" }}
                        onClick={() => setPreviewMail(null)}
                      >
                        Ocultar preview
                      </button>
                    </div>
                  </>
                ) : null}
                <label>
                  Tipo
                  <select
                    value={tipoManual}
                    onChange={(e) => setTipoManual(e.target.value as "diario" | "activos")}
                  >
                    <option value="diario">Gastos del día</option>
                    <option value="activos">Activos fuera</option>
                  </select>
                </label>
                <label>
                  Fecha
                  <input
                    type="date"
                    value={fechaManual}
                    onChange={(e) => setFechaManual(e.target.value)}
                  />
                </label>
                <label>
                  Destinatarios (separados por coma)
                  <input
                    type="text"
                    placeholder="ej. franco@pilaresca.com.ar, alan@pilaresca.com.ar"
                    value={destsManual}
                    onChange={(e) => setDestsManual(e.target.value)}
                  />
                </label>
                {resultadoManual ? <p className="rep-fuente">{resultadoManual}</p> : null}
                <div className="rep-modal-actions">
                  <button
                    type="button"
                    className="btn btn-secondary"
                    disabled={enviandoManual}
                    onClick={async () => {
                      const tipo = tipoManual as "diario" | "activos";
                      let html: string | null = null;
                      let asunto: string = "";

                      if (tipo === "diario") {
                        try {
                          const r = await fetch(
                            `/api/reportes/mail/diario/dry-run`,
                            { method: "POST" }
                          );
                          const data = await r.json();
                          if (data?.cuerpo_html_completo) {
                            html = data.cuerpo_html_completo;
                            asunto = data.asunto || "Reporte Diario — PREVIEW";
                          } else {
                            setResultadoManual("Vista previa incompleta del servidor.");
                          }
                        } catch (e) {
                          setResultadoManual(
                            "No se pudo obtener vista previa. " +
                              (e instanceof Error ? e.message : "error desconocido")
                          );
                        }
                      } else {
                        setResultadoManual(
                          "Vista previa no disponible para tipo 'Activos'. Solo disponible para Diario."
                        );
                      }

                      if (html) {
                        setPreviewMail({ html, asunto });
                      }
                    }}
                  >
                    👁️ Vista previa HTML
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={enviandoManual}
                    onClick={() => void enviarManual()}
                  >
                    {enviandoManual ? "Enviando…" : "Enviar mail"}
                  </button>
                  {previewMail ? (
                    <>
                      <button
                        type="button"
                        className="btn btn-link"
                        style={{ marginLeft: 8, textDecoration: "underline" }}
                        onClick={() => setPreviewMail(null)}
                      >
                        Ocultar preview
                      </button>
                    </>
                  ) : null}
                  <button
                    type="button"
                    className="btn btn-secondary"
                    disabled={enviandoManual}
                    onClick={() => setModal(null)}
                  >
                    Cerrar
                  </button>
                </div>
              </>
            ) : (
              <>
                <h2>Atenciones</h2>
                <label>
                  Desde
                  <input
                    type="date"
                    value={atDesde}
                    onChange={(e) => setAtDesde(e.target.value)}
                  />
                </label>
                <label>
                  Hasta
                  <input
                    type="date"
                    value={atHasta}
                    onChange={(e) => setAtHasta(e.target.value)}
                  />
                </label>
                <label>
                  Formato
                  <select
                    value={atFormato}
                    onChange={(e) => setAtFormato(e.target.value as "xlsx" | "csv")}
                  >
                    <option value="xlsx">Excel</option>
                    <option value="csv">CSV</option>
                  </select>
                </label>
                <p className="rep-fuente" aria-label="Resumen atenciones">
                  {kpiAtencion ? (
                    <>
                      Total {kpiAtencion.total.toLocaleString("es-AR")} · Con retiro{" "}
                      {kpiAtencion.con_retiro} · Sin stock {kpiAtencion.sin_retiro}
                    </>
                  ) : (
                    "Elegí desde y hasta para ver el conteo."
                  )}
                </p>
                <div className="rep-modal-actions">
                  <a
                    className="btn btn-primary"
                    href={
                      atDesde && atHasta
                        ? urlExportAtenciones(atDesde, atHasta, atFormato)
                        : undefined
                    }
                    download
                    aria-disabled={!atDesde || !atHasta}
                    onClick={(e) => {
                      if (!atDesde || !atHasta) e.preventDefault();
                    }}
                  >
                    Exportar
                  </a>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => setModal(null)}
                  >
                    Cerrar
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
