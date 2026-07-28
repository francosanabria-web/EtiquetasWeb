import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fmtNum, fmtPesos } from "../../api/kpisClient";

export type BarItem = { name: string; value: number };

type Props = {
  data: BarItem[];
  color: string;
  layout?: "vertical" | "horizontal";
  height?: number;
  pesos?: boolean;
};

export default function KpiBarChart({
  data,
  color,
  layout = "vertical",
  height = 240,
  pesos = false,
}: Props) {
  if (!data.length) {
    return <p className="kpi-empty-chart">Sin datos.</p>;
  }
  const fmt = pesos ? fmtPesos : fmtNum;
  const isVert = layout === "vertical";
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart
        data={data}
        layout={isVert ? "vertical" : "horizontal"}
        margin={{ top: 4, right: 12, left: isVert ? 80 : 8, bottom: 4 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="#eef2f6" />
        {isVert ? (
          <>
            <XAxis type="number" tick={{ fontSize: 12 }} tickFormatter={(v) => (pesos ? fmt(v).replace("$ ", "") : fmt(v))} />
            <YAxis type="category" dataKey="name" tick={{ fontSize: 12 }} width={76} />
          </>
        ) : (
          <>
            <XAxis dataKey="name" tick={{ fontSize: 11 }} interval={0} angle={-25} textAnchor="end" height={50} />
            <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => (pesos ? fmt(v).replace("$ ", "") : fmt(v))} />
          </>
        )}
        <Tooltip formatter={(v: number) => fmt(v)} contentStyle={{ fontSize: 13, borderRadius: 8 }} />
        <Bar dataKey="value" fill={color} radius={[0, 4, 4, 0]} maxBarSize={28} />
      </BarChart>
    </ResponsiveContainer>
  );
}
