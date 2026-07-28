import {
  etiquetaSector,
  fmtPesos,
  KPI_COLORS,
  SECTOR_CHART_COLORS,
  type ConsumoLinea,
  type ConsumoMensual,
  type ConsumoSector,
  type ConsumoTendenciaAnual,
  type ConsumoTop,
} from "../../api/kpisClient";
import KpiBarChart from "./KpiBarChart";
import KpiDonutChart from "./KpiDonutChart";
import KpiErrorCard, { KpiSectionShell } from "./KpiErrorCard";
import KpiExpandable from "./KpiExpandable";
import KpiLineChart from "./KpiLineChart";
import KpiMultiLineChart from "./KpiMultiLineChart";
import { KpiSkeletonGrid } from "./KpiSkeletonCard";

type Props = {
  mensual: ConsumoMensual | null;
  sector: ConsumoSector | null;
  linea: ConsumoLinea | null;
  top: ConsumoTop | null;
  tendencia: ConsumoTendenciaAnual | null;
  loading: boolean;
  errors: { mensual?: string; sector?: string; linea?: string; top?: string; tendencia?: string };
};

export default function ConsumoSection({
  mensual,
  sector,
  linea,
  top,
  tendencia,
  loading,
  errors,
}: Props) {
  if (loading) {
    return (
      <KpiSectionShell title="Consumo y movimientos" accent={KPI_COLORS.consumo}>
        <KpiSkeletonGrid count={2} />
        <KpiSkeletonGrid count={2} />
      </KpiSectionShell>
    );
  }

  const lineData =
    mensual && !errors.mensual
      ? mensual.datos.map((d) => ({ name: d.periodo, value: d.total }))
      : [];

  const sectorDonut =
    sector && !errors.sector
      ? sector.datos.map((d, i) => ({
          name: etiquetaSector(d.sector),
          value: d.total,
          color: SECTOR_CHART_COLORS[i % SECTOR_CHART_COLORS.length],
        }))
      : [];

  const topBars =
    top && !errors.top
      ? top.por_monto.map((t) => ({
          name: t.codigo,
          value: t.monto,
        }))
      : [];

  const lineaBars =
    linea && !errors.linea
      ? linea.datos.map((d) => ({ name: d.linea, value: d.total }))
      : [];

  const topCantBars =
    top && !errors.top
      ? top.por_cantidad.map((t) => ({
          name: t.codigo,
          value: t.cantidad,
        }))
      : [];

  return (
    <KpiSectionShell title="Consumo y movimientos" accent={KPI_COLORS.consumo}>
      <KpiExpandable title="Tendencia anual por sector (12 meses)" className="kpi-full-width">
        {({ chartHeight }) => (
          <>
            <p className="kpi-chart-caption">
              Evolución del gasto mensual desglosado por sector — vista clave para jefatura y gerencia.
            </p>
            {errors.tendencia ? (
              <KpiErrorCard message={errors.tendencia} />
            ) : (
              <KpiMultiLineChart
                data={tendencia?.datos ?? []}
                seriesKeys={tendencia?.sectores ?? []}
                height={chartHeight}
              />
            )}
          </>
        )}
      </KpiExpandable>
      <div className="kpi-grid-2">
        <KpiExpandable title="Gasto mensual (12 meses)">
          {({ chartHeight }) =>
            errors.mensual ? (
              <KpiErrorCard message={errors.mensual} />
            ) : (
              <KpiLineChart data={lineData} color={KPI_COLORS.consumo} height={chartHeight} />
            )
          }
        </KpiExpandable>
        <KpiExpandable title={`Distribución por sector ${sector ? `(${sector.periodo})` : ""}`}>
          {({ chartHeight }) =>
            errors.sector ? (
              <KpiErrorCard message={errors.sector} />
            ) : (
              <KpiDonutChart
                data={sectorDonut}
                colors={SECTOR_CHART_COLORS}
                valueFormatter={fmtPesos}
                height={chartHeight}
              />
            )
          }
        </KpiExpandable>
      </div>
      <div className="kpi-grid-2">
        <KpiExpandable title="Top 10 artículos por monto">
          {({ chartHeight }) =>
            errors.top ? (
              <KpiErrorCard message={errors.top} />
            ) : (
              <KpiBarChart data={topBars} color={KPI_COLORS.consumo} pesos height={chartHeight} />
            )
          }
        </KpiExpandable>
        <KpiExpandable title="Top 10 artículos por cantidad">
          {({ chartHeight }) =>
            errors.top ? (
              <KpiErrorCard message={errors.top} />
            ) : topCantBars.length === 0 ? (
              <p className="kpi-empty-chart">Sin movimientos con cantidad en el período.</p>
            ) : (
              <KpiBarChart data={topCantBars} color="#0d9488" height={chartHeight} />
            )
          }
        </KpiExpandable>
      </div>
      <KpiExpandable
        title={`Gasto por línea (Mantenimiento)${linea ? ` — ${linea.periodo}` : ""}`}
        className="kpi-full-width"
      >
        {({ chartHeight }) =>
          errors.linea ? (
            <KpiErrorCard message={errors.linea} />
          ) : (
            <KpiBarChart data={lineaBars} color={KPI_COLORS.consumo} pesos height={chartHeight} />
          )
        }
      </KpiExpandable>
    </KpiSectionShell>
  );
}
