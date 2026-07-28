import { useCallback, useEffect, useState } from "react";
import {
  fetchConsumoLinea,
  fetchConsumoMensual,
  fetchConsumoSector,
  fetchConsumoTop,
  fetchConsumoTendenciaAnual,
  fetchKpisHealth,
  fetchReposicion,
  fetchStockEnCero,
  fetchStockResumen,
  fmtFecha,
  mesActual,
  refreshKpis,
  type ConsumoLinea,
  type ConsumoMensual,
  type ConsumoSector,
  type ConsumoTop,
  type ConsumoTendenciaAnual,
  type KpisHealth,
  type ReposicionResumen,
  type StockResumen,
  type ArticuloStock,
} from "../../api/kpisClient";
import ConsumoSection from "./ConsumoSection";
import KpiResumenCards from "./KpiResumenCards";
import ReposicionSection from "./ReposicionSection";
import StockSection from "./StockSection";
import "../../styles/kpis.css";

type SectionErr = Record<string, string | undefined>;

async function loadSafe<T>(fn: () => Promise<T>): Promise<{ data: T | null; error?: string }> {
  try {
    return { data: await fn() };
  } catch (e) {
    return { data: null, error: e instanceof Error ? e.message : "Error desconocido" };
  }
}

export default function KpiDashboard() {
  const [mes, setMes] = useState(mesActual);
  const [ultimaAct, setUltimaAct] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  const [loadingStock, setLoadingStock] = useState(true);
  const [loadingConsumo, setLoadingConsumo] = useState(true);
  const [loadingRepos, setLoadingRepos] = useState(true);

  const [stock, setStock] = useState<StockResumen | null>(null);
  const [enCero, setEnCero] = useState<ArticuloStock[] | null>(null);
  const [stockErr, setStockErr] = useState<string | null>(null);

  const [mensual, setMensual] = useState<ConsumoMensual | null>(null);
  const [sector, setSector] = useState<ConsumoSector | null>(null);
  const [linea, setLinea] = useState<ConsumoLinea | null>(null);
  const [top, setTop] = useState<ConsumoTop | null>(null);
  const [tendencia, setTendencia] = useState<ConsumoTendenciaAnual | null>(null);
  const [consumoErr, setConsumoErr] = useState<SectionErr>({});
  const [health, setHealth] = useState<KpisHealth | null>(null);

  const [reposicion, setReposicion] = useState<ReposicionResumen | null>(null);
  const [reposErr, setReposErr] = useState<string | null>(null);

  const pickTimestamp = useCallback((...isos: (string | undefined)[]) => {
    const valid = isos.filter(Boolean) as string[];
    if (valid.length) setUltimaAct(valid[0]);
  }, []);

  const loadStock = useCallback(async () => {
    setLoadingStock(true);
    setStockErr(null);
    const [r1, r2] = await Promise.all([
      loadSafe(fetchStockResumen),
      loadSafe(() => fetchStockEnCero(20)),
    ]);
    if (r1.error) setStockErr(r1.error);
    else {
      setStock(r1.data);
      pickTimestamp(r1.data?.ultima_actualizacion);
    }
    if (!r1.error && r2.data) setEnCero(r2.data.articulos);
    setLoadingStock(false);
  }, [pickTimestamp]);

  const loadConsumo = useCallback(
    async (m: string) => {
      setLoadingConsumo(true);
      const errs: SectionErr = {};
      const [rM, rS, rL, rT, rTa] = await Promise.all([
        loadSafe(() => fetchConsumoMensual(12)),
        loadSafe(() => fetchConsumoSector(m)),
        loadSafe(() => fetchConsumoLinea(m)),
        loadSafe(() => fetchConsumoTop(m, 10)),
        loadSafe(() => fetchConsumoTendenciaAnual()),
      ]);
      if (rM.error) errs.mensual = rM.error;
      else {
        setMensual(rM.data);
        pickTimestamp(rM.data?.ultima_actualizacion);
      }
      if (rS.error) errs.sector = rS.error;
      else setSector(rS.data);
      if (rL.error) errs.linea = rL.error;
      else setLinea(rL.data);
      if (rT.error) errs.top = rT.error;
      else setTop(rT.data);
      if (rTa.error) errs.tendencia = rTa.error;
      else {
        setTendencia(rTa.data);
        pickTimestamp(rTa.data?.ultima_actualizacion);
      }
      setConsumoErr(errs);
      setLoadingConsumo(false);
    },
    [pickTimestamp],
  );

  const loadRepos = useCallback(async () => {
    setLoadingRepos(true);
    setReposErr(null);
    const r = await loadSafe(fetchReposicion);
    if (r.error) setReposErr(r.error);
    else {
      setReposicion(r.data);
      pickTimestamp(r.data?.ultima_actualizacion);
    }
    setLoadingRepos(false);
  }, [pickTimestamp]);

  const loadAll = useCallback(async () => {
    await Promise.all([loadStock(), loadConsumo(mes), loadRepos()]);
  }, [loadStock, loadConsumo, loadRepos, mes]);

  useEffect(() => {
    void loadStock();
    void loadRepos();
    loadSafe(fetchKpisHealth).then((r) => {
      if (r.data) setHealth(r.data);
    });
  }, [loadStock, loadRepos]);

  useEffect(() => {
    void loadConsumo(mes);
  }, [mes, loadConsumo]);

  const onRefresh = async () => {
    setRefreshing(true);
    try {
      const r = await refreshKpis();
      setUltimaAct(r.timestamp);
      await loadAll();
    } catch (e) {
      setStockErr(e instanceof Error ? e.message : "Error al actualizar");
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <div className="kpi-dashboard page-content">
      <header className="kpi-topbar">
        <div>
          <h1>KPIs — Sistemas Pañol</h1>
          <p className="kpi-timestamp">
            Datos al {ultimaAct ? fmtFecha(ultimaAct) : "—"}
          </p>
        </div>
        <div className="kpi-topbar-actions">
          <label className="kpi-mes-label">
            Mes consumo
            <input
              type="month"
              value={mes}
              onChange={(e) => setMes(e.target.value)}
              className="kpi-mes-input"
            />
          </label>
          <button type="button" className="btn-primary kpi-refresh-btn" onClick={onRefresh} disabled={refreshing}>
            {refreshing ? "Actualizando…" : "Actualizar datos"}
          </button>
        </div>
      </header>

      {health && health.estado !== "ok" && (
        <p className="kpi-health-warn" role="status">
          Algunos archivos Excel no están disponibles. Verificá que la unidad G: esté montada en esta PC.
          {health.archivos && (
            <> Archivos: {Object.entries(health.archivos).map(([k, v]) => `${k}: ${v ? "OK" : "falta"}`).join(" · ")}</>
          )}
        </p>
      )}

      <KpiResumenCards
        stock={stock}
        reposicion={reposicion}
        consumoSector={sector}
        loading={loadingStock && loadingRepos && loadingConsumo}
      />

      <StockSection resumen={stock} enCero={enCero} loading={loadingStock} error={stockErr} />
      <ConsumoSection
        mensual={mensual}
        sector={sector}
        linea={linea}
        top={top}
        tendencia={tendencia}
        loading={loadingConsumo}
        errors={consumoErr}
      />
      <ReposicionSection data={reposicion} loading={loadingRepos} error={reposErr} />
    </div>
  );
}
