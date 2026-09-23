import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "../../auth/AuthContext";
import {
  getImportLog,
  getMaestroStats,
  importMaestroStock,
  type ImportLog,
  type ImportResult,
  type MaestroStats,
} from "../../api/maestroStockClient";

type Status = "idle" | "uploading" | "success" | "error";

function clasificar(nombre: string): string {
  const n = nombre.toLowerCase();
  if (n.includes("detallado")) return "detallado";
  if (n.includes("valorizado")) return "valorizado";
  return "general";
}

function truncate(s: string, n: number): string {
  if (!s) return "";
  return s.length > n ? s.slice(0, n) + "…" : s;
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString("es-AR", { dateStyle: "short", timeStyle: "short" });
  } catch {
    return iso;
  }
}

function pillColor(tipo: string): string {
  if (tipo === "detallado") return "#0e7c66";
  if (tipo === "valorizado") return "#1e40af";
  return "#6b7280";
}

export default function ActualizacionPage() {
  const { token } = useAuth();
  const [files, setFiles] = useState<File[]>([]);
  const [status, setStatus] = useState<Status>("idle");
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [logs, setLogs] = useState<ImportLog[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [logsError, setLogsError] = useState<string | null>(null);
  const [stats, setStats] = useState<MaestroStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);
  const [statsError, setStatsError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const fetchLogsAndStats = useCallback(async () => {
    setLogsLoading(true);
    setLogsError(null);
    setStatsLoading(true);
    setStatsError(null);
    try {
      const [logRes, statRes] = await Promise.allSettled([
        getImportLog(token ?? undefined),
        getMaestroStats(token ?? undefined),
      ]);
      if (logRes.status === "fulfilled") {
        setLogs(logRes.value.items || []);
      } else {
        setLogsError(logRes.reason instanceof Error ? logRes.reason.message : "Error al cargar log");
      }
      if (statRes.status === "fulfilled") {
        setStats(statRes.value);
      } else {
        setStatsError(statRes.reason instanceof Error ? statRes.reason.message : "Error al cargar stats");
      }
    } finally {
      setLogsLoading(false);
      setStatsLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void fetchLogsAndStats();
  }, [fetchLogsAndStats, refreshKey]);

  const addFiles = useCallback((incoming: FileList | File[]) => {
    const arr = Array.from(incoming).filter((f) => f.name.toLowerCase().endsWith(".xlsx"));
    if (arr.length === 0) return;
    setFiles((prev) => {
      const map = new Map(prev.map((f) => [`${f.name}-${f.size}`, f]));
      for (const f of arr) map.set(`${f.name}-${f.size}`, f);
      return Array.from(map.values()).slice(0, 20);
    });
    setStatus("idle");
    setError(null);
    setResult(null);
  }, []);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      if (e.dataTransfer.files) addFiles(e.dataTransfer.files);
    },
    [addFiles],
  );

  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  };

  const onDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
  };

  const removeFile = (idx: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleImport = async () => {
    if (files.length === 0) return;
    setStatus("uploading");
    setError(null);
    setResult(null);
    try {
      const data = await importMaestroStock(files, token ?? undefined);
      setResult(data);
      setStatus("success");
      setRefreshKey((k) => k + 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al importar");
      setStatus("error");
    }
  };

  const handleClear = () => {
    setFiles([]);
    setStatus("idle");
    setError(null);
    setResult(null);
  };

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto", padding: "28px 24px 48px", display: "flex", flexDirection: "column", gap: 20 }}>
      <header>
        <h1 style={{ margin: 0, fontFamily: "var(--font-display)", fontSize: "1.55rem" }}>Actualización y datos</h1>
        <p className="sub" style={{ margin: "6px 0 0" }}>
          Importá el maestro de stock desde Excel. Los archivos se clasifican automáticamente por nombre: <strong>detallado</strong> / <strong>valorizado</strong> / <strong>general</strong>. Reglas: vacío no borra, precio 0 no pisa.
        </p>
      </header>

      {/* Info box explicación */}
      <div
        style={{
          background: "color-mix(in srgb, var(--primary) 8%, var(--surface))",
          border: "1px solid color-mix(in srgb, var(--primary) 18%, var(--border))",
          borderRadius: 10,
          padding: "12px 14px",
          fontSize: "0.88rem",
          lineHeight: 1.5,
          color: "var(--text)",
        }}
      >
        <strong style={{ display: "block", marginBottom: 4 }}>Cómo se clasifica cada archivo</strong>
        <span>
          Si el nombre contiene <code style={{ background: "var(--surface)", border: "1px solid var(--border)", padding: "1px 6px", borderRadius: 4 }}>detallado</code> → solo se actualiza{" "}
          <strong>stock_minimo + ubicación</strong>; si contiene{" "}
          <code style={{ background: "var(--surface)", border: "1px solid var(--border)", padding: "1px 6px", borderRadius: 4 }}>valorizado</code> →{" "}
          <strong>stock + resto (sin mínimo)</strong>; otro nombre → <strong>resto sin stock ni mínimo</strong>. Vacío nunca borra y precio 0 nunca pisa precio &gt; 0.
        </span>
      </div>

      {/* Dropzone */}
      <section
        style={{
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius)",
          padding: 16,
          display: "flex",
          flexDirection: "column",
          gap: 16,
        }}
      >
        <div
          onDrop={onDrop}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onClick={() => inputRef.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              inputRef.current?.click();
            }
          }}
          aria-label="Zona para arrastrar archivos Excel"
          style={{
            border: `1.5px dashed ${dragOver ? "var(--primary)" : "var(--border)"}`,
            borderRadius: 10,
            padding: "22px 16px",
            textAlign: "center",
            cursor: "pointer",
            background: dragOver ? "color-mix(in srgb, var(--primary) 8%, var(--surface))" : "color-mix(in srgb, var(--bg) 55%, var(--surface))",
            transition: "border-color 0.15s, background 0.15s",
          }}
        >
          <div style={{ fontSize: "1.7rem", lineHeight: 1 }}>📦</div>
          <div style={{ fontWeight: 700, marginTop: 8, color: "var(--text)" }}>Arrastrá archivos .xlsx aquí</div>
          <div style={{ color: "var(--muted)", fontSize: "0.88rem", marginTop: 2 }}>o hacé click para seleccionar — 1 a 20 archivos</div>
          <div style={{ color: "var(--muted)", fontSize: "0.8rem", marginTop: 6 }}>Se clasifican por nombre: detallado / valorizado / general</div>
        </div>

        <input
          ref={inputRef}
          type="file"
          accept=".xlsx"
          multiple
          style={{ display: "none" }}
          onChange={(e) => {
            if (e.target.files) addFiles(e.target.files);
            e.target.value = "";
          }}
        />

        {files.length > 0 && (
          <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 8 }}>
            {files.map((f, i) => {
              const tipo = clasificar(f.name);
              return (
                <li
                  key={`${f.name}-${f.size}-${i}`}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    padding: "10px 12px",
                    border: "1px solid var(--border)",
                    borderRadius: 8,
                    background: "color-mix(in srgb, var(--surface) 92%, var(--bg))",
                  }}
                >
                  <span style={{ flex: 1, minWidth: 0, fontSize: "0.88rem", fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={f.name}>
                    {f.name}
                  </span>
                  <span style={{ fontSize: "0.8rem", color: "var(--muted)", whiteSpace: "nowrap" }}>
                    {(f.size / 1024).toFixed(1)} KB
                  </span>
                  <span
                    style={{
                      fontSize: "0.72rem",
                      fontWeight: 700,
                      padding: "2px 8px",
                      borderRadius: 999,
                      background: `color-mix(in srgb, ${pillColor(tipo)} 16%, var(--surface))`,
                      color: pillColor(tipo),
                      border: `1px solid color-mix(in srgb, ${pillColor(tipo)} 30%, transparent)`,
                      textTransform: "uppercase",
                      letterSpacing: "0.04em",
                    }}
                  >
                    {tipo}
                  </span>
                  <button
                    type="button"
                    onClick={() => removeFile(i)}
                    aria-label={`Quitar ${f.name}`}
                    style={{
                      border: "1px solid var(--border)",
                      background: "var(--surface)",
                      borderRadius: 8,
                      width: 30,
                      height: 30,
                      display: "grid",
                      placeItems: "center",
                      cursor: "pointer",
                      fontSize: "1rem",
                      lineHeight: 1,
                      color: "var(--muted)",
                    }}
                  >
                    ×
                  </button>
                </li>
              );
            })}
          </ul>
        )}

        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <button
            type="button"
            className="btn-primary"
            disabled={files.length === 0 || status === "uploading"}
            onClick={() => void handleImport()}
            style={{ minHeight: 40, minWidth: 160 }}
          >
            {status === "uploading" ? "Importando…" : "Importar stock"}
          </button>
          {files.length > 0 && status !== "uploading" && (
            <button type="button" className="btn-ghost" onClick={handleClear} style={{ minHeight: 40 }}>
              Limpiar
            </button>
          )}
        </div>

        {status === "uploading" && <p className="sub" style={{ margin: 0 }}>Procesando en servidor — esto puede tardar algunos segundos…</p>}
        {status === "error" && error && (
          <p className="error" role="alert" style={{ margin: 0, padding: "10px 12px", background: "color-mix(in srgb, var(--danger) 10%, var(--surface))", border: "1px solid color-mix(in srgb, var(--danger) 22%, var(--border))", borderRadius: 8 }}>
            Error: {error}
          </p>
        )}

        {status === "success" && result && (
          <div
            style={{
              border: "1px solid color-mix(in srgb, var(--primary) 20%, var(--border))",
              background: "color-mix(in srgb, var(--primary) 6%, var(--surface))",
              borderRadius: 10,
              padding: 14,
              display: "flex",
              flexDirection: "column",
              gap: 12,
            }}
          >
            <h3 style={{ margin: 0, fontSize: "0.98rem" }}>Resumen importación</h3>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(110px, 1fr))", gap: 10 }}>
              <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: "12px 10px", textAlign: "center" }}>
                <div style={{ fontSize: "1.35rem", fontWeight: 800, color: "var(--text)" }}>{result.codigos_modificados}</div>
                <div style={{ fontSize: "0.78rem", color: "var(--muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.04em" }}>Modificados</div>
              </div>
              <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: "12px 10px", textAlign: "center" }}>
                <div style={{ fontSize: "1.35rem", fontWeight: 800, color: "var(--text)" }}>{result.codigos_nuevos}</div>
                <div style={{ fontSize: "0.78rem", color: "var(--muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.04em" }}>Nuevos</div>
              </div>
              <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: "12px 10px", textAlign: "center" }}>
                <div style={{ fontSize: "1.35rem", fontWeight: 800, color: "var(--primary)" }}>{result.precios_propagados}</div>
                <div style={{ fontSize: "0.78rem", color: "var(--muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.04em" }}>Precios propagados</div>
              </div>
              <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: "12px 10px", textAlign: "center" }}>
                <div style={{ fontSize: "1.35rem", fontWeight: 800, color: "var(--danger)" }}>{result.codigos_sin_precio}</div>
                <div style={{ fontSize: "0.78rem", color: "var(--muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.04em" }}>Sin precio</div>
              </div>
            </div>
            {result.detalle?.length ? (
              <details style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: "10px 12px" }}>
                <summary style={{ cursor: "pointer", fontWeight: 700, fontSize: "0.88rem" }}>Detalle por archivo ({result.detalle.length})</summary>
                <ul style={{ margin: "10px 0 0", padding: "0 0 0 16px", display: "flex", flexDirection: "column", gap: 8, fontSize: "0.88rem" }}>
                  {result.detalle.map((d, i) => (
                    <li key={i} style={{ lineHeight: 1.45 }}>
                      <strong>{d.archivo}</strong>{" "}
                      <span style={{ color: pillColor(d.tipo), fontWeight: 700, fontSize: "0.82rem" }}>({d.tipo})</span>: {d.codigos_modificados} mod, {d.codigos_nuevos} nuevos, {d.precios_propagados} precios · {d.codigos_sin_precio} sin precio
                      {d.reporte && d.reporte.length > 2000 ? (
                        <details style={{ marginTop: 6 }}>
                          <summary style={{ cursor: "pointer", fontSize: "0.8rem", color: "var(--muted)" }}>Ver reporte</summary>
                          <pre style={{ margin: "8px 0 0", padding: 10, background: "color-mix(in srgb, var(--bg) 60%, var(--surface))", border: "1px solid var(--border)", borderRadius: 8, fontSize: "0.75rem", whiteSpace: "pre-wrap", wordBreak: "break-word", maxHeight: 220, overflow: "auto" }}>
                            {d.reporte.slice(0, 4000)}
                            {d.reporte.length > 4000 ? "\n… truncado" : ""}
                          </pre>
                        </details>
                      ) : d.reporte ? (
                        <pre style={{ margin: "8px 0 0", padding: 10, background: "color-mix(in srgb, var(--bg) 60%, var(--surface))", border: "1px solid var(--border)", borderRadius: 8, fontSize: "0.75rem", whiteSpace: "pre-wrap", wordBreak: "break-word", maxHeight: 220, overflow: "auto" }}>
                          {d.reporte.slice(0, 4000)}
                        </pre>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </details>
            ) : null}
            <p className="sub" style={{ margin: 0, fontSize: "0.78rem" }}>
              API: /api/maestro-stock/import · archivos: {result.archivos}
            </p>
          </div>
        )}
      </section>

      {/* Stats */}
      <section
        style={{
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius)",
          padding: 16,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
          <h2 style={{ margin: 0, fontSize: "1rem" }}>Estado del maestro</h2>
          <button type="button" className="btn-secondary btn-sm" onClick={() => setRefreshKey((k) => k + 1)} disabled={statsLoading} style={{ minHeight: 32 }}>
            {statsLoading ? "Cargando…" : "Refrescar"}
          </button>
        </div>
        {statsLoading && <p className="sub" style={{ margin: 0 }}>Cargando estadísticas…</p>}
        {statsError && (
          <p className="error" style={{ margin: 0 }}>
            {statsError}
          </p>
        )}
        {!statsLoading && !statsError && stats && (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 12 }}>
              <div style={{ border: "1px solid var(--border)", borderRadius: 10, padding: "14px 12px", textAlign: "center", background: "color-mix(in srgb, var(--surface) 90%, var(--bg))" }}>
                <div style={{ fontSize: "1.45rem", fontWeight: 800 }}>{stats.total.toLocaleString("es-AR")}</div>
                <div style={{ fontSize: "0.78rem", color: "var(--muted)", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.03em" }}>Total artículos</div>
              </div>
              <div style={{ border: "1px solid color-mix(in srgb, #dc2626 22%, var(--border))", background: "color-mix(in srgb, #dc2626 7%, var(--surface))", borderRadius: 10, padding: "14px 12px", textAlign: "center" }}>
                <div style={{ fontSize: "1.45rem", fontWeight: 800, color: "#b91c1c" }}>{stats.criticos.toLocaleString("es-AR")}</div>
                <div style={{ fontSize: "0.78rem", color: "var(--muted)", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.03em" }}>Críticos (stock ≤ mínimo)</div>
              </div>
              <div style={{ border: "1px solid color-mix(in srgb, #d97706 22%, var(--border))", background: "color-mix(in srgb, #d97706 7%, var(--surface))", borderRadius: 10, padding: "14px 12px", textAlign: "center" }}>
                <div style={{ fontSize: "1.45rem", fontWeight: 800, color: "#b45309" }}>{stats.sin_precio.toLocaleString("es-AR")}</div>
                <div style={{ fontSize: "0.78rem", color: "var(--muted)", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.03em" }}>Sin precio</div>
              </div>
            </div>
            {stats.por_importancia && Object.keys(stats.por_importancia).length > 0 && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 12 }}>
                {Object.entries(stats.por_importancia).map(([k, v]) => (
                  <span
                    key={k}
                    style={{
                      fontSize: "0.78rem",
                      fontWeight: 700,
                      padding: "4px 10px",
                      borderRadius: 999,
                      background: "color-mix(in srgb, var(--border) 45%, var(--surface))",
                      border: "1px solid var(--border)",
                      color: "var(--text)",
                    }}
                  >
                    {k}: {v}
                  </span>
                ))}
              </div>
            )}
          </>
        )}
        {!statsLoading && !statsError && !stats && <p className="sub" style={{ margin: 0 }}>Sin datos.</p>}
      </section>

      {/* Import log */}
      <section
        style={{
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius)",
          padding: 16,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 12 }}>
          <h2 style={{ margin: 0, fontSize: "1rem" }}>
            Últimas importaciones <span style={{ fontSize: "0.78rem", fontWeight: 700, background: "var(--border)", color: "var(--text)", padding: "2px 8px", borderRadius: 999, marginLeft: 8 }}>{logs.length}</span>
          </h2>
        </div>

        {logsLoading ? (
          <p className="sub" style={{ margin: 0 }}>Cargando…</p>
        ) : logsError ? (
          <p className="error" style={{ margin: 0 }}>
            {logsError} — API: /api/maestro-stock/import-log
          </p>
        ) : logs.length === 0 ? (
          <p className="sub" style={{ margin: 0, textAlign: "center", padding: "12px 0" }}>Sin importaciones registradas.</p>
        ) : (
          <div style={{ overflowX: "auto", border: "1px solid var(--border)", borderRadius: 8 }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem", minWidth: 640 }}>
              <thead>
                <tr style={{ background: "color-mix(in srgb, var(--surface) 88%, var(--border))" }}>
                  <th style={{ textAlign: "left", padding: "9px 10px", fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.03em", color: "var(--muted)", borderBottom: "1px solid var(--border)" }}>Archivo</th>
                  <th style={{ textAlign: "left", padding: "9px 10px", fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.03em", color: "var(--muted)", borderBottom: "1px solid var(--border)" }}>Tipo</th>
                  <th style={{ textAlign: "right", padding: "9px 10px", fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.03em", color: "var(--muted)", borderBottom: "1px solid var(--border)" }}>Nuevos</th>
                  <th style={{ textAlign: "right", padding: "9px 10px", fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.03em", color: "var(--muted)", borderBottom: "1px solid var(--border)" }}>Mod</th>
                  <th style={{ textAlign: "right", padding: "9px 10px", fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.03em", color: "var(--muted)", borderBottom: "1px solid var(--border)" }}>Sin precio</th>
                  <th style={{ textAlign: "right", padding: "9px 10px", fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.03em", color: "var(--muted)", borderBottom: "1px solid var(--border)" }}>Duración</th>
                  <th style={{ textAlign: "left", padding: "9px 10px", fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.03em", color: "var(--muted)", borderBottom: "1px solid var(--border)" }}>Fecha</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((l) => (
                  <tr key={l.id} style={{ borderBottom: "1px solid var(--border)" }}>
                    <td title={l.archivo_origen} style={{ padding: "9px 10px", maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontWeight: 600 }}>
                      {truncate(l.archivo_origen, 28)}
                    </td>
                    <td style={{ padding: "9px 10px" }}>
                      <span
                        style={{
                          fontSize: "0.72rem",
                          fontWeight: 700,
                          padding: "2px 8px",
                          borderRadius: 999,
                          background: `color-mix(in srgb, ${pillColor(l.tipo_archivo)} 14%, var(--surface))`,
                          color: pillColor(l.tipo_archivo),
                          border: `1px solid color-mix(in srgb, ${pillColor(l.tipo_archivo)} 24%, transparent)`,
                          textTransform: "lowercase",
                        }}
                      >
                        {l.tipo_archivo}
                      </span>
                    </td>
                    <td style={{ padding: "9px 10px", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{l.codigos_nuevos}</td>
                    <td style={{ padding: "9px 10px", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{l.codigos_modificados}</td>
                    <td style={{ padding: "9px 10px", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{l.codigos_sin_precio}</td>
                    <td style={{ padding: "9px 10px", textAlign: "right", fontVariantNumeric: "tabular-nums", color: "var(--muted)" }}>{l.duracion_ms} ms</td>
                    <td style={{ padding: "9px 10px", whiteSpace: "nowrap", color: "var(--muted)", fontSize: "0.82rem" }}>{formatDate(l.creado_en)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <p className="sub" style={{ margin: 0, fontSize: "0.8rem" }}>
        El método diario por Excel se mantiene. Este módulo solo expone la misma importación para quien no tiene el Excel a mano.
      </p>
    </div>
  );
}
