/**
 * Configuracion - Module with 3 sections (Stock/Maestro, Sistema, Informacion).
 * Purpose: Central settings page for maestro_stock import and system info.
 * Route: /configuracion (handled via pathname check in App.tsx)
 */

import { useState } from "react";
import StockImport, { useImportLog, useMaestroStats } from "../components/maestro/StockImport";

const APP_VERSION = "1.0.0";
const SALIDAS_API_URL = (
  (import.meta.env.VITE_SALIDAS_API_URL as string | undefined) ??
  (import.meta.env.VITE_API_URL as string | undefined) ??
  "http://localhost:8018"
).replace(/\/$/, "");

type TabId = "stock" | "sistema" | "info";

export default function Configuracion() {
  const [tab, setTab] = useState<TabId>("stock");
  const [refreshKey, setRefreshKey] = useState(0);

  const handleImported = () => setRefreshKey((k) => k + 1);

  return (
    <div className="config-page">
      <header className="config-header">
        <h1>Configuración</h1>
        <p className="hint">Gestión de maestro, parámetros y estado del sistema</p>
      </header>

      <div className="seg config-tabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={tab === "stock"}
          className={`seg-btn ${tab === "stock" ? "active" : ""}`}
          onClick={() => setTab("stock")}
        >
          Stock / Maestro
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "sistema"}
          className={`seg-btn ${tab === "sistema" ? "active" : ""}`}
          onClick={() => setTab("sistema")}
        >
          Sistema
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "info"}
          className={`seg-btn ${tab === "info" ? "active" : ""}`}
          onClick={() => setTab("info")}
        >
          Información
        </button>
      </div>

      <div className="config-body">
        {tab === "stock" && <StockSection refreshKey={refreshKey} onImported={handleImported} />}
        {tab === "sistema" && <SistemaSection />}
        {tab === "info" && <InfoSection refreshKey={refreshKey} />}
      </div>

      <div className="config-footer">
        <a href="/" className="link-btn">
          ← Volver a etiquetas
        </a>
        <a href="/maestro-stock" className="link-btn">
          Ver maestro →
        </a>
      </div>
    </div>
  );
}

function StockSection({ refreshKey, onImported }: { refreshKey: number; onImported: () => void }) {
  const { logs, loading, err } = useImportLog(refreshKey);

  return (
    <div className="config-section">
      <section className="card">
        <h2>Actualización de stock</h2>
        <p className="hint">Importa archivos Excel con el maestro. Vacío no borra. Precio 0 no pisa precio existente.</p>
        <StockImport onImported={onImported} />
      </section>

      <section className="card">
        <div className="card-head-row">
          <h3>Últimas importaciones</h3>
          <span className="badge">{logs.length}</span>
        </div>
        {loading ? (
          <p className="hint">Cargando…</p>
        ) : err ? (
          <p className="hint error">{err} — API: {SALIDAS_API_URL}/api/maestro-stock/import-log</p>
        ) : logs.length === 0 ? (
          <p className="hint">Sin importaciones registradas.</p>
        ) : (
          <div className="table-wrap">
            <table className="import-log-table">
              <thead>
                <tr>
                  <th>Archivo</th>
                  <th>Tipo</th>
                  <th>Nuevos</th>
                  <th>Mod</th>
                  <th>Sin precio</th>
                  <th>Duración</th>
                  <th>Fecha</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((l) => (
                  <tr key={l.id}>
                    <td title={l.archivo_origen}>{truncate(l.archivo_origen, 28)}</td>
                    <td>
                      <span className={`pill pill-${l.tipo_archivo}`}>{l.tipo_archivo}</span>
                    </td>
                    <td>{l.codigos_nuevos}</td>
                    <td>{l.codigos_modificados}</td>
                    <td>{l.codigos_sin_precio}</td>
                    <td>{l.duracion_ms} ms</td>
                    <td>{formatDate(l.creado_en)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="card-actions-row">
          <a href="/maestro-stock" className="btn-secundario btn-sm">
            Ver maestro
          </a>
        </div>
      </section>
    </div>
  );
}

function SistemaSection() {
  return (
    <div className="config-section">
      <section className="card">
        <h2>Parámetros generales</h2>
        <p className="hint">Extensible para futuras configuraciones del sistema.</p>
        <div className="placeholder-box">
          <p>Próximamente: impresoras, depósitos, mapeo de estanterías, backups y más.</p>
          <p className="hint">Este módulo es el punto central de configuración — se irán agregando secciones sin romper navegación.</p>
        </div>
      </section>
    </div>
  );
}

function InfoSection({ refreshKey }: { refreshKey: number }) {
  const { stats, loading, err } = useMaestroStats(refreshKey);
  return (
    <div className="config-section">
      <section className="card">
        <h2>Información</h2>
        <div className="info-grid">
          <div className="info-item">
            <span className="info-label">Versión</span>
            <span className="info-val">{APP_VERSION}</span>
          </div>
          <div className="info-item">
            <span className="info-label">API Salidas</span>
            <span className="info-val">{SALIDAS_API_URL}</span>
          </div>
          <div className="info-item">
            <span className="info-label">DB</span>
            <span className="info-val">panol · maestro_stock</span>
          </div>
        </div>
      </section>

      <section className="card">
        <h3>Estadísticas maestro</h3>
        {loading ? (
          <p className="hint">Cargando estadísticas…</p>
        ) : err ? (
          <p className="hint error">{err}</p>
        ) : stats ? (
          <div className="stats-grid">
            <div className="stat-card">
              <span className="stat-val">{stats.total}</span>
              <span className="stat-label">Total artículos</span>
            </div>
            <div className="stat-card warn">
              <span className="stat-val">{stats.criticos}</span>
              <span className="stat-label">Críticos (stock ≤ mínimo)</span>
            </div>
            <div className="stat-card error">
              <span className="stat-val">{stats.sin_precio}</span>
              <span className="stat-label">Sin precio</span>
            </div>
          </div>
        ) : (
          <p className="hint">Sin datos.</p>
        )}
        {stats?.por_importancia && (
          <div className="imp-breakdown">
            {Object.entries(stats.por_importancia).map(([k, v]) => (
              <span key={k} className="pill pill-base">
                {k}: {v}
              </span>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function truncate(s: string, n: number) {
  if (!s) return "";
  return s.length > n ? s.slice(0, n) + "…" : s;
}

function formatDate(iso: string) {
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleString("es-AR", { dateStyle: "short", timeStyle: "short" });
  } catch {
    return iso;
  }
}
