import {
  claseFilaDiasFuera,
  DIAS_FUERA_ALERTA,
  DIAS_FUERA_AVISO,
  fmtNum,
  KPI_COLORS,
  SECTOR_CHART_COLORS,
  urlActivosExcel,
  urlActivosPdf,
  type ActivosResumen,
} from "../../api/kpisClient";
import KpiDonutChart from "./KpiDonutChart";
import KpiErrorCard, { KpiSectionShell } from "./KpiErrorCard";
import KpiExpandable from "./KpiExpandable";
import { KpiSkeletonGrid } from "./KpiSkeletonCard";
import "../../styles/kpis.css";

type Props = {
  data: ActivosResumen | null;
  loading: boolean;
  error: string | null;
  onRetry?: () => void;
};

function TablaActivos({ data, tableMaxHeight }: { data: ActivosResumen; tableMaxHeight: number | "none" }) {
  const scrollStyle =
    tableMaxHeight === "none" ? undefined : { maxHeight: tableMaxHeight };

  return (
    <div className="kpi-table-wrap kpi-table-scroll" style={scrollStyle}>
      <table className="kpi-table kpi-table-activos">
        <thead>
          <tr>
            <th>Equipo / repuesto</th>
            <th>Código</th>
            <th>Nº remito</th>
            <th>Nº pedido</th>
            <th>Nº OC</th>
            <th>Sector</th>
            <th>Días fuera</th>
            <th>Proveedor</th>
            <th>Estado</th>
          </tr>
        </thead>
        <tbody>
          {data.lista.map((a, i) => (
            <tr key={`${a.codigo}-${a.remito}-${i}`} className={claseFilaDiasFuera(a.dias_fuera)}>
              <td className="kpi-td-desc" title={a.equipo}>
                {a.equipo || "—"}
              </td>
              <td>{a.codigo || "—"}</td>
              <td className="kpi-td-doc">{a.remito || "—"}</td>
              <td className="kpi-td-doc">{a.n_pedido || "—"}</td>
              <td className="kpi-td-doc">{a.n_oc || "—"}</td>
              <td>{a.sector || "—"}</td>
              <td>
                <strong>{a.dias_fuera}</strong>
              </td>
              <td>{a.proveedor || "—"}</td>
              <td>{a.estado.replace(/_/g, " ") || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ActivosSection({ data, loading, error, onRetry }: Props) {
  if (loading) {
    return (
      <KpiSectionShell title="Activos fuera de planta" accent={KPI_COLORS.activos}>
        <KpiSkeletonGrid count={2} />
      </KpiSectionShell>
    );
  }
  if (error) {
    return (
      <KpiSectionShell title="Activos fuera de planta" accent={KPI_COLORS.activos}>
        <KpiErrorCard message={error} onRetry={onRetry} />
      </KpiSectionShell>
    );
  }
  if (!data) return null;

  const donut = data.por_sector.map((s, i) => ({
    name: s.sector,
    value: s.cantidad,
    color: SECTOR_CHART_COLORS[i % SECTOR_CHART_COLORS.length],
  }));

  return (
    <KpiSectionShell title="Activos fuera de planta" accent={KPI_COLORS.activos}>
      <p className="kpi-chart-caption kpi-leyenda-dias">
        <span className="kpi-leyenda-item kpi-row-dias-ok">≤ {DIAS_FUERA_AVISO} días</span>
        <span className="kpi-leyenda-item kpi-row-dias-aviso">
          {DIAS_FUERA_AVISO + 1}–{DIAS_FUERA_ALERTA} días
        </span>
        <span className="kpi-leyenda-item kpi-row-dias-critico">&gt; {DIAS_FUERA_ALERTA} días</span>
        <span className="kpi-leyenda-note">— mismos colores que el mail de seguimiento</span>
      </p>
      <div className="kpi-activos-toolbar">
        <p className="kpi-chart-caption">
          {fmtNum(data.fuera_de_planta)} equipos fuera · Promedio {data.dias_promedio_fuera} días
        </p>
        <div className="kpi-activos-export">
          <a className="btn-ghost btn-sm" href={urlActivosPdf()} target="_blank" rel="noreferrer">
            Exportar PDF
          </a>
          <a className="btn-ghost btn-sm" href={urlActivosExcel()} target="_blank" rel="noreferrer">
            Exportar Excel
          </a>
        </div>
      </div>
      <div className="kpi-grid-2">
        <KpiExpandable title="Listado fuera de planta" className="kpi-span-full-mobile">
          {({ tableMaxHeight }) => <TablaActivos data={data} tableMaxHeight={tableMaxHeight} />}
        </KpiExpandable>
        <KpiExpandable title="Distribución por sector">
          {({ chartHeight }) => (
            <KpiDonutChart data={donut} colors={SECTOR_CHART_COLORS} height={chartHeight} />
          )}
        </KpiExpandable>
      </div>
    </KpiSectionShell>
  );
}
