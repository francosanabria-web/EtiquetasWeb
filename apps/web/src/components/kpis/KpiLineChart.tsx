import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fmtPesos } from "../../api/kpisClient";

export type LineItem = { name: string; value: number };

type Props = {
  data: LineItem[];
  color: string;
  height?: number;
};

export default function KpiLineChart({ data, color, height = 240 }: Props) {
  if (!data.length) {
    return <p className="kpi-empty-chart">Sin datos.</p>;
  }
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 16, left: 8, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#eef2f6" />
        <XAxis dataKey="name" tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => fmtPesos(v).replace("$ ", "")} width={72} />
        <Tooltip formatter={(v: number) => fmtPesos(v)} contentStyle={{ fontSize: 13, borderRadius: 8 }} />
        <Line type="monotone" dataKey="value" stroke={color} strokeWidth={2} dot={{ r: 3 }} activeDot={{ r: 5 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}
