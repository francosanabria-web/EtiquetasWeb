import {
  fmtNum,
  fmtPct,
  fmtPesos,
  KPI_COLORS,
  type StockResumen,
  type ArticuloStock,
} from "../../api/kpisClient";
import KpiBarChart from "./KpiBarChart";
import KpiDonutChart from "./KpiDonutChart";
import KpiErrorCard, { KpiSectionShell } from "./KpiErrorCard";
import KpiExpandable from "./KpiExpandable";
import KpiSkeletonCard, { KpiSkeletonGrid } from "./KpiSkeletonCard";

type Props = {
  resumen: StockResumen | null;
  enCero: ArticuloStock[] | null;
  loading: boolean;
  error: string | null;
};

const CRIT_COLORS: Record<string, string> = {
  "CRÍTICO": "#A32D2D",
  "ALTA FRECUENCIA": "#854F0B",
  BASE: "#185FA5",
};

export default function StockSection({ resumen, enCero, loading, error }: Props) {
  if (loading) {
    return (
      <KpiSectionShell title="Stock e inventario" accent={KPI_COLORS.stock}>
        <KpiSkeletonGrid count={2} />
        <KpiSkeletonCard lines={5} />
      </KpiSectionShell>
    );
  }
  if (error) {
    return (
      <KpiSectionShell title="Stock e inventario" accent={KPI_COLORS.stock}>
        <KpiErrorCard message={error} />
      </KpiSectionShell>
    );
  }
  if (!resumen) return null;

  const donutData = [
    { name: "Bajo mínimo", value: resumen.bajo_minimo.cantidad },
    { name: "Sobre mínimo", value: resumen.sobre_minimo.cantidad },
  ];

  const critBars = resumen.por_criticidad.map((c) => ({
    name: c.criticidad,
    value: c.valor,
  }));

  return (
    <KpiSectionShell title="Stock e inventario" accent={KPI_COLORS.stock}>
      <div className="kpi-grid-2">
        <KpiExpandable title="Bajo mínimo vs sobre mínimo">
          {({ chartHeight }) => (
            <>
              <KpiDonutChart data={donutData} colors={["#185FA5", "#93c5fd"]} height={chartHeight} />
              <p className="kpi-chart-caption">
                {fmtNum(resumen.bajo_minimo.cantidad)} bajo mínimo ({fmtPct(resumen.bajo_minimo.porcentaje)})
              </p>
            </>
          )}
        </KpiExpandable>
        <KpiExpandable title="Stock valorizado por criticidad">
          {({ chartHeight }) => (
            <KpiBarChart data={critBars} color={KPI_COLORS.stock} pesos height={chartHeight} />
          )}
        </KpiExpandable>
      </div>
      <KpiExpandable title={`Artículos en cero — top ${enCero?.length ?? 0}`} className="kpi-full-width">
        {({ tableMaxHeight }) => (
          <>
            <p className="kpi-chart-caption">
              Total en cero: {fmtNum(resumen.en_cero.cantidad)} · Valor reposición estimado:{" "}
              {fmtPesos(resumen.en_cero.valor_reposicion_estimado)}
            </p>
            <div
              className="kpi-table-wrap kpi-table-scroll"
              style={tableMaxHeight === "none" ? undefined : { maxHeight: tableMaxHeight }}
            >
              <table className="kpi-table">
            <thead>
              <tr>
                <th>Código</th>
                <th>Descripción</th>
                <th>Stock</th>
                <th>Mínimo</th>
                <th>Precio</th>
                <th>Valor repos.</th>
                <th>Criticidad</th>
              </tr>
            </thead>
            <tbody>
              {(enCero ?? []).map((a) => (
                <tr key={a.codigo}>
                  <td>{a.codigo}</td>
                  <td className="kpi-td-desc">{a.desc}</td>
                  <td>{fmtNum(a.stock)}</td>
                  <td>{fmtNum(a.stk_min)}</td>
                  <td>{fmtPesos(a.precio_unitario)}</td>
                  <td>{fmtPesos(a.valor_reposicion ?? 0)}</td>
                  <td>
                    <span
                      className="kpi-badge"
                      style={{ background: `${CRIT_COLORS[a.criticidad] ?? KPI_COLORS.stock}22`, color: CRIT_COLORS[a.criticidad] ?? KPI_COLORS.stock }}
                    >
                      {a.criticidad}
                    </span>
                  </td>
                </tr>
              ))}
              </tbody>
            </table>
            </div>
          </>
        )}
      </KpiExpandable>
    </KpiSectionShell>
  );
}
