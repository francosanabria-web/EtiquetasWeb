import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Agrupacion, PuntoSerie } from "../types/kpi";
import { formatearMoneda, formatearFecha } from "../lib/kpiEngine";

const PALETTE = [
  "#2563eb",
  "#0d9488",
  "#d97706",
  "#7c3aed",
  "#db2777",
  "#0891b2",
  "#65a30d",
  "#ea580c",
];

function tooltipMoneda(value: number | string) {
  return formatearMoneda(Number(value));
}

type Props = {
  serie: PuntoSerie[];
  porLinea: Agrupacion[];
  porObra: Agrupacion[];
  porCategoria: Agrupacion[];
};

export default function ChartPanel({ serie, porLinea, porObra, porCategoria }: Props) {
  const serieLabel = serie.map((p) => ({
    ...p,
    label: formatearFecha(p.fecha),
  }));

  return (
    <div className="charts-grid">
      <article className="chart-card wide">
        <h3>Evolución de gastos</h3>
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={serieLabel}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="label" tick={{ fontSize: 11 }} />
            <YAxis tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} tick={{ fontSize: 11 }} />
            <Tooltip formatter={tooltipMoneda} labelFormatter={(l) => `Fecha: ${l}`} />
            <Legend />
            <Line
              type="monotone"
              dataKey="total"
              name="Gasto"
              stroke="#2563eb"
              strokeWidth={2.5}
              dot={{ r: 3 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </article>

      <article className="chart-card">
        <h3>Por línea</h3>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={porLinea.slice(0, 8)} layout="vertical" margin={{ left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} />
            <XAxis type="number" tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
            <YAxis type="category" dataKey="clave" width={90} tick={{ fontSize: 10 }} />
            <Tooltip formatter={tooltipMoneda} />
            <Bar dataKey="total" name="Total" fill="#0d9488" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </article>

      <article className="chart-card">
        <h3>Por obra (top)</h3>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={porObra.slice(0, 6)}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="clave" tick={{ fontSize: 10 }} interval={0} angle={-20} textAnchor="end" height={60} />
            <YAxis tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
            <Tooltip formatter={tooltipMoneda} />
            <Bar dataKey="total" name="Total" fill="#2563eb" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </article>

      {porCategoria.length > 1 && (
        <article className="chart-card">
          <h3>Por categoría</h3>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie
                data={porCategoria}
                dataKey="total"
                nameKey="clave"
                cx="50%"
                cy="50%"
                outerRadius={90}
                label={({ clave, percent }) =>
                  `${String(clave).slice(0, 12)} ${(percent * 100).toFixed(0)}%`
                }
              >
                {porCategoria.map((_, i) => (
                  <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
                ))}
              </Pie>
              <Tooltip formatter={tooltipMoneda} />
            </PieChart>
          </ResponsiveContainer>
        </article>
      )}
    </div>
  );
}
