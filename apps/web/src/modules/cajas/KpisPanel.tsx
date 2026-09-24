/**
 * KpisPanel — Global KPIs vs Caja Ideal (Card C of hub).
 * Shows total_tecnicos, avg faltantes/completitud/limpieza, distribution charts, empty states with skeletons.
 */

import { useCallback, useEffect, useState } from "react";
import { getKpisResumen, type KpisResumen } from "../../api/cajasClient";
import KpiSkeletonCard from "../../components/kpis/KpiSkeletonCard";
import KpiBarChart from "../../components/kpis/KpiBarChart";
import KpiDonutChart from "../../components/kpis/KpiDonutChart";

type Props = {
  token: string | null;
  onDefineIdeal?: () => void;
  refreshKey?: number;
};

const DIST_COLORS: Record<string, string> = {
  "0-25": "#22c55e",
  "25-50": "#eab308",
  "50-75": "#f97316",
  "75-100": "#ef4444",
};
const DIST_ORDER = ["0-25", "25-50", "50-75", "75-100"] as const;

export default function KpisPanel({ token, onDefineIdeal, refreshKey }: Props) {
  const [kpis, setKpis] = useState<KpisResumen | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getKpisResumen(token);
      setKpis(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudieron cargar los KPIs.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void cargar();
  }, [cargar, refreshKey]);

  if (!token) {
    return (
      <div className="sol-table-wrap cajas-card" style={{ padding: "1rem" }}>
        <h3 style={{ margin: 0, fontSize: "1rem" }}>KPIs Cajas</h3>
        <p className="sol-hint">Sin token — iniciá sesión.</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="sol-table-wrap cajas-card cajas-fade-in" style={{ padding: "1rem", display: "flex", flexDirection: "column", gap: "0.75rem" }}>
        <h3 style={{ margin: 0, fontSize: "1rem" }}>KPIs Cajas</h3>
        <KpiSkeletonCard lines={4} height={160} />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem" }}>
          <div className="kpi-skeleton-line" style={{ height: 90, borderRadius: 8 }} />
          <div className="kpi-skeleton-line" style={{ height: 90, borderRadius: 8 }} />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="sol-table-wrap cajas-card" style={{ padding: "1rem", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
        <h3 style={{ margin: 0, fontSize: "1rem" }}>KPIs Cajas</h3>
        <p className="error" role="status">{error}</p>
        <button type="button" className="btn-ghost btn-sm" onClick={() => void cargar()}>
          Reintentar
        </button>
      </div>
    );
  }

  if (!kpis) {
    return (
      <div className="sol-table-wrap cajas-card" style={{ padding: "1rem", display: "flex", flexDirection: "column", alignItems: "center", gap: "0.5rem", textAlign: "center" }}>
        <h3 style={{ margin: 0, fontSize: "1rem", alignSelf: "flex-start" }}>KPIs Cajas</h3>
        <div style={{ fontSize: "2rem" }} role="img" aria-label="kpis">📊</div>
        <p className="sol-hint">Sin datos.</p>
        {onDefineIdeal && (
          <button type="button" className="btn-primary btn-sm" onClick={onDefineIdeal}>
            Definir Caja Ideal
          </button>
        )}
      </div>
    );
  }

  // Empty ideal case — polished illustration + CTA
  if (kpis.ideal_count === 0 || kpis.mensaje || kpis.hint) {
    const hint = kpis.hint ?? kpis.mensaje ?? "No hay Caja Ideal definida — define una para calcular KPIs";
    return (
      <div className="sol-table-wrap cajas-card cajas-fade-in" style={{ padding: "1.25rem", display: "flex", flexDirection: "column", gap: "0.75rem", alignItems: "center", textAlign: "center" }}>
        <h3 style={{ margin: 0, fontSize: "1rem", alignSelf: "flex-start", width: "100%" }}>KPIs Cajas</h3>
        <div style={{ fontSize: "2.4rem", lineHeight: 1 }} role="img" aria-label="kpis vacio">📊</div>
        <p style={{ margin: 0, fontWeight: 700 }}>Definí la Caja Ideal para ver KPIs</p>
        <p className="sol-hint" style={{ margin: 0, maxWidth: 320 }}>{hint}</p>
        <div
          style={{
            background: "#fef9c3",
            border: "1px solid #facc15",
            borderRadius: 8,
            padding: "0.6rem 0.75rem",
            fontSize: "0.85rem",
            width: "100%",
            textAlign: "left",
          }}
        >
          Sin ideal no hay % faltantes, completitud ni distribución. Define al menos 1 herramienta.
        </div>
        {onDefineIdeal && (
          <button type="button" className="btn-primary btn-sm" onClick={onDefineIdeal}>
            Definir Caja Ideal
          </button>
        )}
        <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap", fontSize: "0.85rem", color: "#6b7280", justifyContent: "center" }}>
          <span>Total técnicos: <strong>{kpis.total_tecnicos}</strong></span>
          <span>Con inventario: <strong>{kpis.tecnicos_con_inventario}</strong></span>
        </div>
      </div>
    );
  }

  const distribucion = kpis.distribucion_faltantes ?? kpis.distribucion ?? { "0-25": 0, "25-50": 0, "50-75": 0, "75-100": 0 };
  const avgFalt = kpis.avg_faltantes_pct ?? kpis.promedio_faltantes_pct ?? 0;
  const avgComp = kpis.avg_completitud_pct ?? kpis.promedio_completitud_pct ?? 0;
  const avgLimp = kpis.avg_limpieza_score ?? 0;

  // Top 5 peores faltantes
  const peores = [...(kpis.tecnicos ?? kpis.items ?? [])]
    .filter((t) => t.faltantes_pct !== null && t.faltantes_pct !== undefined)
    .sort((a, b) => (b.faltantes_pct ?? 0) - (a.faltantes_pct ?? 0))
    .slice(0, 5);

  const donutData = DIST_ORDER.map((r) => ({
    name: `${r}%`,
    value: distribucion[r] ?? 0,
    color: DIST_COLORS[r],
  }));
  const barDistribData = DIST_ORDER.map((r) => ({
    name: `${r}%`,
    value: distribucion[r] ?? 0,
  }));
  const top5BarData = peores.map((t) => ({
    name: t.tecnico_nombre.length > 14 ? t.tecnico_nombre.slice(0, 14) + "…" : t.tecnico_nombre,
    value: Number((t.faltantes_pct ?? 0).toFixed(1)),
  }));

  return (
    <div className="sol-table-wrap cajas-card cajas-fade-in" style={{ padding: "1rem", display: "flex", flexDirection: "column", gap: "0.85rem" }}>
      <h3 style={{ margin: 0, fontSize: "1rem" }}>KPIs Cajas</h3>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(110px, 1fr))", gap: "0.5rem" }}>
        <div style={{ background: "#f9fafb", border: "1px solid #e5e7eb", borderRadius: 8, padding: "0.6rem", textAlign: "center" }}>
          <div style={{ fontSize: "0.75rem", color: "#6b7280", fontWeight: 600, textTransform: "uppercase" }}>Técnicos</div>
          <div style={{ fontSize: "1.25rem", fontWeight: 800 }}>{kpis.total_tecnicos}</div>
          <div style={{ fontSize: "0.75rem", color: "#6b7280" }}>{kpis.tecnicos_con_inventario} con inventario</div>
        </div>
        <div style={{ background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 8, padding: "0.6rem", textAlign: "center" }}>
          <div style={{ fontSize: "0.75rem", color: "#991b1b", fontWeight: 600, textTransform: "uppercase" }}>% Faltantes prom.</div>
          <div style={{ fontSize: "1.25rem", fontWeight: 800, color: "#991b1b" }}>{avgFalt.toFixed(1)}%</div>
          <div style={{ fontSize: "0.75rem", color: "#6b7280" }}>ideal {kpis.ideal_count} ítems</div>
        </div>
        <div style={{ background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: 8, padding: "0.6rem", textAlign: "center" }}>
          <div style={{ fontSize: "0.75rem", color: "#166534", fontWeight: 600, textTransform: "uppercase" }}>Completitud prom.</div>
          <div style={{ fontSize: "1.25rem", fontWeight: 800, color: "#166534" }}>{avgComp.toFixed(1)}%</div>
          <div style={{ fontSize: "0.75rem", color: "#6b7280" }}>presentes / ideal</div>
        </div>
        <div style={{ background: "#fefce8", border: "1px solid #fde68a", borderRadius: 8, padding: "0.6rem", textAlign: "center" }}>
          <div style={{ fontSize: "0.75rem", color: "#854d0e", fontWeight: 600, textTransform: "uppercase" }}>Limpieza prom.</div>
          <div style={{ fontSize: "1.25rem", fontWeight: 800, color: "#854d0e" }}>{avgLimp.toFixed(1)}%</div>
          <div style={{ fontSize: "0.75rem", color: "#6b7280" }}>estado malo</div>
        </div>
      </div>

      <div>
        <h4 style={{ margin: "0 0 0.4rem", fontSize: "0.9rem" }}>Distribución % faltantes</h4>
        <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "0.5rem" }}>
          <KpiDonutChart data={donutData} colors={DIST_ORDER.map((k) => DIST_COLORS[k])} height={180} valueFormatter={(v) => `${v}`} />
          <div style={{ minHeight: 180 }}>
            <KpiBarChart data={barDistribData} color="#0e7c66" height={180} layout="vertical" />
          </div>
        </div>
        <p className="sol-hint" style={{ margin: "0.35rem 0 0", fontSize: "0.75rem", textAlign: "center" }}>
          {kpis.tecnicos_sin_inventario ?? 0} sin inventario se cuentan en 75-100% · Donut + barras por bucket
        </p>
      </div>

      {peores.length > 0 && (
        <div className="cajas-fade-in">
          <h4 style={{ margin: "0 0 0.35rem", fontSize: "0.9rem" }}>Top 5 — mayores faltantes</h4>
          <KpiBarChart data={top5BarData} color="#b42318" layout="vertical" height={Math.max(160, peores.length * 32)} />
          <ul style={{ margin: "0.4rem 0 0", paddingLeft: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: "0.3rem" }}>
            {peores.map((t) => (
              <li
                key={t.tecnico_id}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  background: "#f9fafb",
                  border: "1px solid #e5e7eb",
                  borderRadius: 6,
                  padding: "0.35rem 0.6rem",
                  fontSize: "0.82rem",
                }}
              >
                <span>
                  <strong>{t.tecnico_nombre}</strong>
                  {t.caja_codigo ? <span className="sol-hint"> — {t.caja_codigo}</span> : null}
                </span>
                <span
                  style={{
                    background: (t.faltantes_pct ?? 0) > 50 ? "#fee2e2" : (t.faltantes_pct ?? 0) > 10 ? "#fef9c3" : "#dcfce7",
                    color: (t.faltantes_pct ?? 0) > 50 ? "#991b1b" : (t.faltantes_pct ?? 0) > 10 ? "#854d0e" : "#166534",
                    padding: "0.15rem 0.4rem",
                    borderRadius: 999,
                    fontWeight: 700,
                    fontSize: "0.78rem",
                  }}
                >
                  {(t.faltantes_pct ?? 0).toFixed(1)}% faltante
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
