import { fmtNum, fmtPesos, SECTOR_CHART_COLORS } from "../../api/kpisClient";
import type { BarItem } from "./KpiBarChart";

type Props = {
  data: BarItem[];
  /** Altura orientativa del bloque (compat. con KpiExpandable). */
  height?: number;
  /** Etiqueta accesible del gráfico. */
  ariaLabel?: string;
  /** Paleta de relleno (ciclo). */
  colors?: readonly string[];
  /**
   * Si true (default), valores en pesos compactos ($ / k / M).
   * Si false, números sin símbolo (p. ej. cantidades).
   */
  pesos?: boolean;
};

function fmtCompactPesos(n: number): string {
  const abs = Math.abs(n);
  const sign = n < 0 ? "-" : "";
  if (abs >= 1_000_000) {
    return `${sign}$${(abs / 1_000_000).toLocaleString("es-AR", { maximumFractionDigits: 1 })}M`;
  }
  if (abs >= 10_000) {
    return `${sign}$${(abs / 1_000).toLocaleString("es-AR", { maximumFractionDigits: 0 })}k`;
  }
  return `${sign}$${abs.toLocaleString("es-AR", { maximumFractionDigits: 0 })}`;
}

function fmtCompactNum(n: number): string {
  const abs = Math.abs(n);
  const sign = n < 0 ? "-" : "";
  if (abs >= 1_000_000) {
    return `${sign}${(abs / 1_000_000).toLocaleString("es-AR", { maximumFractionDigits: 1 })}M`;
  }
  if (abs >= 10_000) {
    return `${sign}${(abs / 1_000).toLocaleString("es-AR", { maximumFractionDigits: 0 })}k`;
  }
  return `${sign}${abs.toLocaleString("es-AR", { maximumFractionDigits: 0 })}`;
}

/**
 * Barras HTML/CSS para rankings con nombre + valor + %.
 * Evita Recharts (ResponsiveContainer / ResizeObserver) que colapsan en CSS grid
 * y deja legibles categorías chicas frente a un dominante.
 */
export default function KpiNamedBarList({
  data,
  height = 260,
  ariaLabel = "Comparación por categoría",
  colors = SECTOR_CHART_COLORS,
  pesos = true,
}: Props) {
  if (!data.length) {
    return <p className="kpi-empty-chart">Sin datos.</p>;
  }

  const max = Math.max(...data.map((d) => d.value), 1);
  const total = data.reduce((s, d) => s + d.value, 0) || 1;
  const fmtCompact = pesos ? fmtCompactPesos : fmtCompactNum;
  const fmtFull = pesos ? fmtPesos : fmtNum;

  return (
    <div
      className="kpi-named-bars"
      style={height > 400 ? { gap: 18, paddingTop: 8 } : undefined}
      role="img"
      aria-label={ariaLabel}
    >
      {data.map((d, i) => {
        const pctMax = Math.max(2.5, (d.value / max) * 100);
        const pctShare = (d.value / total) * 100;
        const color = colors[i % colors.length];
        return (
          <div className="kpi-named-row" key={`${d.name}-${i}`}>
            <div className="kpi-named-meta">
              <span className="kpi-named-name" title={d.name}>
                {d.name}
              </span>
              <span className="kpi-named-vals">
                <strong title={fmtFull(d.value)}>{fmtCompact(d.value)}</strong>
                <span className="kpi-named-share">{pctShare.toFixed(1)} %</span>
              </span>
            </div>
            <div className="kpi-named-track" aria-hidden>
              <div
                className="kpi-named-fill"
                style={{ width: `${pctMax}%`, background: color }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
