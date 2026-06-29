import FilterBar from "./FilterBar";
import ChartPanel from "./ChartPanel";
import DataTable from "./DataTable";
import { KpiCardMoneda } from "./KpiCard";
import type { useKpiStore } from "../hooks/useKpiStore";
import { formatearMoneda } from "../lib/kpiEngine";

type Store = ReturnType<typeof useKpiStore>;

type Props = Pick<
  Store,
  | "registrosFiltrados"
  | "resumen"
  | "porLinea"
  | "porObra"
  | "porCategoria"
  | "serie"
  | "filtros"
  | "setFiltros"
  | "lineasDisponibles"
  | "obrasDisponibles"
  | "registros"
>;

export default function Dashboard({
  registrosFiltrados,
  resumen,
  porLinea,
  porObra,
  porCategoria,
  serie,
  filtros,
  setFiltros,
  lineasDisponibles,
  obrasDisponibles,
  registros,
}: Props) {
  const rango = registros.length
    ? { desde: filtros.fechaDesde, hasta: filtros.fechaHasta }
    : null;

  return (
    <div className="dashboard">
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

      <section className="kpi-grid">
        <KpiCardMoneda
          titulo="Gasto total (período)"
          monto={resumen.total}
          detalle={
            rango
              ? `${rango.desde.split("-").reverse().join("/")} — ${rango.hasta.split("-").reverse().join("/")}`
              : undefined
          }
          accent="blue"
        />
        <KpiCardMoneda
          titulo="Promedio diario"
          monto={resumen.promedioDiario}
          detalle={`${resumen.diasConDatos} días con movimientos`}
          accent="teal"
        />
        <KpiCardMoneda
          titulo="Línea principal"
          monto={resumen.lineaTop?.total ?? 0}
          detalle={resumen.lineaTop?.nombre ?? "—"}
          accent="violet"
        />
        <KpiCardMoneda
          titulo="Obra principal"
          monto={resumen.obraTop?.total ?? 0}
          detalle={resumen.obraTop?.nombre ?? "—"}
          accent="amber"
        />
      </section>

      <section className="kpi-grid secondary">
        <article className="kpi-card accent-blue">
          <span className="kpi-label">Movimientos</span>
          <strong className="kpi-value">{resumen.cantidad}</strong>
        </article>
        <article className="kpi-card accent-teal">
          <span className="kpi-label">Ticket promedio</span>
          <strong className="kpi-value">
            {formatearMoneda(resumen.cantidad ? resumen.total / resumen.cantidad : 0)}
          </strong>
        </article>
        <article className="kpi-card accent-violet">
          <span className="kpi-label">Líneas activas</span>
          <strong className="kpi-value">{porLinea.length}</strong>
        </article>
        <article className="kpi-card accent-amber">
          <span className="kpi-label">Obras activas</span>
          <strong className="kpi-value">{porObra.length}</strong>
        </article>
      </section>

      <ChartPanel
        serie={serie}
        porLinea={porLinea}
        porObra={porObra}
        porCategoria={porCategoria}
      />

      <section className="panel">
        <header className="panel-head">
          <h3>Detalle de movimientos</h3>
          <span className="badge">{registrosFiltrados.length} filas</span>
        </header>
        <DataTable registros={registrosFiltrados} />
      </section>
    </div>
  );
}
