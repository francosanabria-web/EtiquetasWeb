import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { etiquetaSector, fmtPesos, SECTOR_CHART_COLORS } from "../../api/kpisClient";

export type TendenciaRow = Record<string, string | number>;

type Props = {
  data: TendenciaRow[];
  seriesKeys: string[];
  height?: number;
};

export default function KpiMultiLineChart({ data, seriesKeys, height = 300 }: Props) {
  if (!data.length || !seriesKeys.length) {
    return <p className="kpi-empty-chart">Sin datos de tendencia.</p>;
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 16, left: 8, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#eef2f6" />
        <XAxis dataKey="periodo" tick={{ fontSize: 10 }} />
        <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => fmtPesos(v).replace("$ ", "")} width={72} />
        <Tooltip formatter={(v: number) => fmtPesos(v)} contentStyle={{ fontSize: 12, borderRadius: 8 }} />
        <Legend formatter={(v) => etiquetaSector(v)} wrapperStyle={{ fontSize: 12 }} />
        {seriesKeys.map((key, i) => (
          <Line
            key={key}
            type="monotone"
            dataKey={key}
            name={key}
            stroke={SECTOR_CHART_COLORS[i % SECTOR_CHART_COLORS.length]}
            strokeWidth={2}
            dot={{ r: 2 }}
            activeDot={{ r: 4 }}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
