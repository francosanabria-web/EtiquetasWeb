import { fmtNum, fmtPct, fmtPesos, KPI_COLORS, type StockResumen, type ReposicionResumen, type ConsumoSector } from "../../api/kpisClient";

type Props = {
  stock: StockResumen | null;
  reposicion: ReposicionResumen | null;
  consumoSector: ConsumoSector | null;
  loading: boolean;
};

function ResumenCard({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string;
  sub?: string;
  accent: string;
}) {
  return (
    <div className="kpi-resumen-card" style={{ borderTopColor: accent }}>
      <span className="kpi-resumen-label">{label}</span>
      <span className="kpi-resumen-value" style={{ color: accent }}>
        {value}
      </span>
      {sub && <span className="kpi-resumen-sub">{sub}</span>}
    </div>
  );
}

export default function KpiResumenCards({ stock, reposicion, consumoSector, loading }: Props) {
  if (loading) {
    return (
      <div className="kpi-resumen-row">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="kpi-resumen-card kpi-resumen-skeleton" />
        ))}
      </div>
    );
  }

  const gastoMes = consumoSector
    ? consumoSector.datos.reduce((s, d) => s + d.total, 0)
    : 0;

  return (
    <div className="kpi-resumen-row">
      <ResumenCard
        label="Stock valorizado"
        value={stock ? fmtPesos(stock.stock_valorizado_total) : "—"}
        sub={stock ? `${fmtNum(stock.total_articulos)} artículos en catálogo` : undefined}
        accent="#1d4ed8"
      />
      <ResumenCard
        label="Artículos bajo mínimo"
        value={stock ? fmtNum(stock.bajo_minimo.cantidad) : "—"}
        sub={stock ? fmtPct(stock.bajo_minimo.porcentaje) + " del catálogo" : undefined}
        accent={KPI_COLORS.stock}
      />
      <ResumenCard
        label="Gasto del mes"
        value={fmtPesos(gastoMes)}
        sub={consumoSector?.periodo}
        accent={KPI_COLORS.consumo}
      />
      <ResumenCard
        label="Artículos a reponer"
        value={reposicion ? fmtNum(reposicion.articulos_a_reponer) : "—"}
        sub={reposicion ? fmtPesos(reposicion.valor_total_reposicion) + " estimado" : undefined}
        accent={KPI_COLORS.reposicion}
      />
    </div>
  );
}
