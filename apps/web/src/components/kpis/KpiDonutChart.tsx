import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { fmtNum, fmtPesos } from "../../api/kpisClient";

export type DonutItem = { name: string; value: number; color?: string };

type Props = {
  data: DonutItem[];
  colors: string[];
  valueFormatter?: (v: number) => string;
  height?: number;
};

export default function KpiDonutChart({ data, colors, valueFormatter = fmtNum, height = 220 }: Props) {
  const filtered = data.filter((d) => d.value > 0);
  if (filtered.length === 0) {
    return <p className="kpi-empty-chart">Sin datos para el período.</p>;
  }
  const innerR = Math.round(Math.min(70, height * 0.22));
  const outerR = Math.round(Math.min(120, height * 0.34));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie
          data={filtered}
          dataKey="value"
          nameKey="name"
          cx="50%"
          cy="50%"
          innerRadius={innerR}
          outerRadius={outerR}
          paddingAngle={2}
        >
          {filtered.map((entry, i) => (
            <Cell key={entry.name} fill={entry.color ?? colors[i % colors.length]} />
          ))}
        </Pie>
        <Tooltip
          formatter={(v: number, name: string) => {
            if (name.includes("$") || String(v).length > 6) return [fmtPesos(v), name];
            return [valueFormatter(v), name];
          }}
          contentStyle={{ fontSize: 13, borderRadius: 8, border: "0.5px solid #dbe3ec" }}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}
