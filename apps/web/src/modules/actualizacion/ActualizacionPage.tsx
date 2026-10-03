import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "../../auth/AuthContext";
import {
  diffRowsToCsv,
  diffRowsToTsv,
  getCodigoHistory,
  getImportDiff,
  getImportLog,
  getImportLogById,
  getMaestroStats,
  importMaestroStock,
  type CodigoHistoryResult,
  type ImportDiffRow,
  type ImportDiffResult,
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

const CAMPO_OPTIONS = ["all", "descripcion", "stock", "stock_minimo", "ubicacion", "precio_unitario", "importancia", "categoria"] as const;

function DiffTable({
  rows,
  filterCodigo,
  setFilterCodigo,
  filterCampo,
  setFilterCampo,
  onViewHistory,
  compact,
}: {
  rows: ImportDiffRow[];
  filterCodigo: string;
  setFilterCodigo: (v: string) => void;
  filterCampo: string;
  setFilterCampo: (v: string) => void;
  onViewHistory: (codigo: string) => void;
  compact?: boolean;
}) {
  const filtered = useMemo(() => {
    const q = filterCodigo.trim().toUpperCase();
    return rows.filter((r) => {
      if (q && !r.codigo.toUpperCase().includes(q)) return false;
      if (filterCampo !== "all" && r.campo !== filterCampo) return false;
      return true;
    });
  }, [rows, filterCodigo, filterCampo]);

  const handleCopy = async () => {
    const tsv = diffRowsToTsv(filtered);
    try {
      await navigator.clipboard.writeText(tsv);
    } catch {
      // fallback
      const ta = document.createElement("textarea");
      ta.value = tsv;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    }
  };

  const handleExport = () => {
    const csv = diffRowsToCsv(filtered);
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `import-diff-${Date.now()}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  if (rows.length === 0) {
    return <p className="sub" style={{ margin: 0, fontSize: "0.85rem" }}>Sin cambios de campo para esta importación (solo reporte texto o sin audit).</p>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <input
          value={filterCodigo}
          onChange={(e) => setFilterCodigo(e.target.value.toUpperCase())}
          placeholder="Filtrar por código (ej: M1046)"
          aria-label="Filtrar por código"
          style={{
            flex: 1,
            minWidth: 160,
            font: "inherit",
            fontSize: "0.85rem",
            padding: "7px 10px",
            border: "0.5px solid var(--border)",
            borderRadius: 7,
            background: "var(--bg)",
            color: "var(--text)",
          }}
        />
        <select
          value={filterCampo}
          onChange={(e) => setFilterCampo(e.target.value)}
          aria-label="Filtrar por campo"
          style={{
            font: "inherit",
            fontSize: "0.85rem",
            padding: "7px 10px",
            border: "0.5px solid var(--border)",
            borderRadius: 7,
            background: "var(--surface)",
            color: "var(--text)",
          }}
        >
          {CAMPO_OPTIONS.map((o) => (
            <option key={o} value={o}>
              {o === "all" ? "Todos los campos" : o}
            </option>
          ))}
        </select>
        <span style={{ fontSize: "0.78rem", color: "var(--muted)" }}>{filtered.length} / {rows.length}</span>
        <button type="button" className="btn-secondary" onClick={() => void handleCopy()} style={{ minHeight: 32, fontSize: "0.78rem" }}>
          Copiar
        </button>
        <button type="button" className="btn-secondary" onClick={handleExport} style={{ minHeight: 32, fontSize: "0.78rem" }}>
          Exportar CSV
        </button>
      </div>

      <div style={{ overflowX: "auto", border: "1px solid var(--border)", borderRadius: 8 }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: compact ? "0.8rem" : "0.85rem", minWidth: 560 }}>
          <thead>
            <tr style={{ background: "color-mix(in srgb, var(--surface) 88%, var(--border))" }}>
              <th style={{ textAlign: "left", padding: "8px 10px", fontSize: "0.72rem", textTransform: "uppercase", color: "var(--muted)", borderBottom: "1px solid var(--border)" }}>Código</th>
              <th style={{ textAlign: "left", padding: "8px 10px", fontSize: "0.72rem", textTransform: "uppercase", color: "var(--muted)", borderBottom: "1px solid var(--border)" }}>Campo</th>
              <th style={{ textAlign: "left", padding: "8px 10px", fontSize: "0.72rem", textTransform: "uppercase", color: "var(--muted)", borderBottom: "1px solid var(--border)" }}>Antes</th>
              <th style={{ textAlign: "left", padding: "8px 10px", fontSize: "0.72rem", textTransform: "uppercase", color: "var(--muted)", borderBottom: "1px solid var(--border)" }}>Después</th>
              <th style={{ textAlign: "left", padding: "8px 10px", fontSize: "0.72rem", textTransform: "uppercase", color: "var(--muted)", borderBottom: "1px solid var(--border)" }}>Archivo</th>
              <th style={{ padding: "8px 10px", borderBottom: "1px solid var(--border)" }}></th>
            </tr>
          </thead>
          <tbody>
            {filtered.slice(0, 500).map((r, idx) => {
              const antes = r.valor_antes ?? "—";
              const despues = r.valor_despues ?? "—";
              const changed = String(antes) !== String(despues);
              return (
                <tr key={`${r.import_log_id}-${r.codigo}-${r.campo}-${idx}`} style={{ borderBottom: "1px solid var(--border)", background: changed ? "color-mix(in srgb, var(--primary) 4%, var(--surface))" : undefined }}>
                  <td style={{ padding: "7px 10px", fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>{r.codigo}</td>
                  <td style={{ padding: "7px 10px", fontSize: "0.8rem" }}>{r.campo}</td>
                  <td style={{ padding: "7px 10px", color: "var(--muted)", background: changed ? "color-mix(in srgb, #f59e0b 10%, transparent)" : undefined, maxWidth: 160, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={String(antes)}>
                    {antes || "∅"}
                  </td>
                  <td style={{ padding: "7px 10px", fontWeight: 600, background: changed ? "color-mix(in srgb, #10b981 14%, transparent)" : undefined, maxWidth: 160, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={String(despues)}>
                    {despues || "∅"}
                  </td>
                  <td style={{ padding: "7px 10px", maxWidth: 160, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    <span style={{ fontSize: "0.72rem", padding: "1px 6px", borderRadius: 999, background: `color-mix(in srgb, ${pillColor(r.tipo_archivo)} 14%, var(--surface))`, color: pillColor(r.tipo_archivo), border: `1px solid color-mix(in srgb, ${pillColor(r.tipo_archivo)} 24%, transparent)` }}>{r.tipo_archivo}</span>{" "}
                    <span style={{ fontSize: "0.75rem", color: "var(--muted)" }}>{truncate(r.archivo_origen, 22)}</span>
                  </td>
                  <td style={{ padding: "7px 10px", textAlign: "right" }}>
                    <button type="button" className="btn-ghost" onClick={() => onViewHistory(r.codigo)} style={{ minHeight: 26, fontSize: "0.72rem", padding: "2px 8px", border: "0.5px solid var(--border)", borderRadius: 6 }}>
                      Historia
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {filtered.length > 500 && <p className="sub" style={{ margin: 0, fontSize: "0.75rem" }}>Mostrando 500 de {filtered.length} (exportá CSV para ver todo).</p>}
    </div>
  );
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
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedLog, setSelectedLog] = useState<ImportLog | null>(null);
  const [selectedLogReporte, setSelectedLogReporte] = useState<string>("");
  const [selectedLogDiff, setSelectedLogDiff] = useState<ImportDiffResult | null>(null);
  const [selectedLogDiffLoading, setSelectedLogDiffLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // Filters for selected modal diff
  const [modalFilterCodigo, setModalFilterCodigo] = useState("");
  const [modalFilterCampo, setModalFilterCampo] = useState("all");
  // Persistent last diff (for the cards area)
  const [lastDiff, setLastDiff] = useState<ImportDiffResult | null>(null);
  const [lastDiffLoading, setLastDiffLoading] = useState(false);
  const [persistentFilterCodigo, setPersistentFilterCodigo] = useState("");
  const [persistentFilterCampo, setPersistentFilterCampo] = useState("all");

  // Expandable logs
  const [expandedLogs, setExpandedLogs] = useState<Record<number, { loading: boolean; diff: ImportDiffResult | null; reporte: string }>>({});

  // History drawer
  const [historyCodigo, setHistoryCodigo] = useState<string | null>(null);
  const [historyData, setHistoryData] = useState<CodigoHistoryResult | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyPage, setHistoryPage] = useState(1);

  const fetchLogsAndStats = useCallback(async () => {
    setLogsLoading(true);
    setLogsError(null);
    setStatsLoading(true);
    setStatsError(null);
    try {
      const [logRes, statRes] = await Promise.allSettled([getImportLog(token ?? undefined), getMaestroStats(token ?? undefined)]);
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

  // Keep persistent diff in sync with logs[0]
  useEffect(() => {
    const id = logs[0]?.id;
    if (!id) {
      setLastDiff(null);
      return;
    }
    // If we just imported and result is for same id, don't refetch yet — fetch after refresh
    let cancelled = false;
    setLastDiffLoading(true);
    getImportDiff(id, token ?? undefined)
      .then((d) => {
        if (!cancelled) setLastDiff(d);
      })
      .catch(() => {
        if (!cancelled) setLastDiff(null);
      })
      .finally(() => {
        if (!cancelled) setLastDiffLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [logs, token]);

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
    // Do NOT clear result — keep persistent last import visible per spec
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
    // Keep result and logs — persistent per spec; only files are cleared
  };

  const toggleExpand = async (log: ImportLog) => {
    const id = log.id;
    const cur = expandedLogs[id];
    if (cur && cur.diff) {
      // collapse
      setExpandedLogs((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
      return;
    }
    setExpandedLogs((prev) => ({ ...prev, [id]: { loading: true, diff: null, reporte: log.reporte ?? "" } }));
    try {
      const [diff, full] = await Promise.all([
        getImportDiff(id, token ?? undefined).catch(() => null),
        getImportLogById(id, token ?? undefined).catch(() => null),
      ]);
      setExpandedLogs((prev) => ({ ...prev, [id]: { loading: false, diff, reporte: (full as ImportLog)?.reporte ?? log.reporte ?? "" } }));
    } catch {
      setExpandedLogs((prev) => ({ ...prev, [id]: { loading: false, diff: null, reporte: log.reporte ?? "" } }));
    }
  };

  const handleViewLastUpdate = async () => {
    if (logs.length === 0) return;
    const lastLog = logs[0];
    setSelectedLog(lastLog);
    setModalOpen(true);
    setSelectedLogDiff(null);
    setSelectedLogDiffLoading(true);
    setModalFilterCodigo("");
    setModalFilterCampo("all");
    try {
      const [full, diff] = await Promise.all([
        getImportLogById(lastLog.id, token ?? undefined).catch(() => lastLog),
        getImportDiff(lastLog.id, token ?? undefined).catch(() => null),
      ]);
      setSelectedLogReporte((full as ImportLog)?.reporte ?? lastLog.reporte ?? "");
      setSelectedLogDiff(diff);
    } catch {
      setSelectedLogReporte(lastLog.reporte ?? "");
    } finally {
      setSelectedLogDiffLoading(false);
    }
  };

  const openHistory = async (codigo: string, page = 1) => {
    const cod = codigo.trim().toUpperCase();
    if (!cod) return;
    setHistoryCodigo(cod);
    setHistoryPage(page);
    setHistoryLoading(true);
    try {
      const data = await getCodigoHistory(cod, { page, limit: 20 }, token ?? undefined);
      setHistoryData(data);
    } catch {
      setHistoryData({ codigo: cod, total: 0, page, limit: 20, items: [] });
    } finally {
      setHistoryLoading(false);
    }
  };

  const closeModal = () => {
    setModalOpen(false);
    setSelectedLog(null);
    setSelectedLogReporte("");
    setSelectedLogDiff(null);
  };

  const closeHistory = () => {
    setHistoryCodigo(null);
    setHistoryData(null);
    setHistoryPage(1);
  };

  const persistentLast = logs[0] ?? null;
  const displayResult = result; // ephemeral, but also show persistentLast card

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto", padding: "28px 24px 48px", display: "flex", flexDirection: "column", gap: 20 }}>
      <header>
        <h1 style={{ margin: 0, fontFamily: "var(--font-display)", fontSize: "1.55rem" }}>Actualización y datos</h1>
        <p className="sub" style={{ margin: "6px 0 0" }}>
          Importá el maestro de stock desde Excel. Los archivos se clasifican automáticamente por nombre: <strong>detallado</strong> / <strong>valorizado</strong> / <strong>general</strong>. Reglas: vacío no borra, precio 0 no pisa.
        </p>
      </header>

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

      {/* Callout double-touch M1046MEC */}
      <div
        style={{
          background: "color-mix(in srgb, #f59e0b 10%, var(--surface))",
          border: "1px solid color-mix(in srgb, #f59e0b 30%, var(--border))",
          borderRadius: 10,
          padding: "10px 14px",
          fontSize: "0.84rem",
          lineHeight: 1.5,
        }}
      >
        <strong>Tip: ¿un código aparece dos veces?</strong> Si mandás <em>detallado</em> y <em>valorizado</em> juntos, el mismo código puede tocarse en ambos: el detallado solo aplica <code>mínimo+ubicación</code> y el valorizado el resto. Por eso <code>M1046MEC</code> puede mostrar 2 filas: una con <em>ubicación</em> y otra con <em>descripción/stock</em>. Filtrá por código para verlo.
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
                  <span style={{ fontSize: "0.8rem", color: "var(--muted)", whiteSpace: "nowrap" }}>{(f.size / 1024).toFixed(1)} KB</span>
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
          <button type="button" className="btn-primary" disabled={files.length === 0 || status === "uploading"} onClick={() => void handleImport()} style={{ minHeight: 40, minWidth: 160 }}>
            {status === "uploading" ? "Importando…" : "Importar stock"}
          </button>
          {files.length > 0 && status !== "uploading" && (
            <button type="button" className="btn-ghost" onClick={handleClear} style={{ minHeight: 40 }}>
              Limpiar archivos
            </button>
          )}
        </div>

        {status === "uploading" && <p className="sub" style={{ margin: 0 }}>Procesando en servidor — esto puede tardar algunos segundos…</p>}
        {status === "error" && error && (
          <p className="error" role="alert" style={{ margin: 0, padding: "10px 12px", background: "color-mix(in srgb, var(--danger) 10%, var(--surface))", border: "1px solid color-mix(in srgb, var(--danger) 22%, var(--border))", borderRadius: 8 }}>
            Error: {error}
          </p>
        )}

        {/* Ephemeral result from this import */}
        {status === "success" && displayResult && (
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
            <h3 style={{ margin: 0, fontSize: "0.98rem" }}>Resultado de esta importación <span style={{ fontWeight: 400, fontSize: "0.8rem", color: "var(--muted)" }}>(persistido en historial abajo)</span></h3>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(110px, 1fr))", gap: 10 }}>
              <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: "12px 10px", textAlign: "center" }}>
                <div style={{ fontSize: "1.35rem", fontWeight: 800, color: "var(--text)" }}>{displayResult.codigos_modificados}</div>
                <div style={{ fontSize: "0.78rem", color: "var(--muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.04em" }}>Modificados</div>
              </div>
              <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: "12px 10px", textAlign: "center" }}>
                <div style={{ fontSize: "1.35rem", fontWeight: 800, color: "var(--text)" }}>{displayResult.codigos_nuevos}</div>
                <div style={{ fontSize: "0.78rem", color: "var(--muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.04em" }}>Nuevos</div>
              </div>
              <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: "12px 10px", textAlign: "center" }}>
                <div style={{ fontSize: "1.35rem", fontWeight: 800, color: "var(--primary)" }}>{displayResult.precios_propagados}</div>
                <div style={{ fontSize: "0.78rem", color: "var(--muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.04em" }}>Precios propagados</div>
              </div>
              <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: "12px 10px", textAlign: "center" }}>
                <div style={{ fontSize: "1.35rem", fontWeight: 800, color: "var(--danger)" }}>{displayResult.codigos_sin_precio}</div>
                <div style={{ fontSize: "0.78rem", color: "var(--muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.04em" }}>
                  Sin precio <span title="Total con precio <=0 excluyendo K y U (no llevan precio por diseño) — sin K/U" style={{ cursor: "help", textDecoration: "underline dotted" }}>(sin K/U)</span>
                </div>
              </div>
            </div>
            {displayResult.detalle?.length ? (
              <details style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: "10px 12px" }}>
                <summary style={{ cursor: "pointer", fontWeight: 700, fontSize: "0.88rem" }}>Detalle por archivo ({displayResult.detalle.length})</summary>
                <ul style={{ margin: "10px 0 0", padding: "0 0 0 16px", display: "flex", flexDirection: "column", gap: 8, fontSize: "0.88rem" }}>
                  {displayResult.detalle.map((d, i) => (
                    <li key={i} style={{ lineHeight: 1.45 }}>
                      <strong>{d.archivo}</strong> <span style={{ color: pillColor(d.tipo), fontWeight: 700, fontSize: "0.82rem" }}>({d.tipo})</span>: {d.codigos_modificados} mod
                      {d.precios_modificados !== undefined || d.stock_altas !== undefined ? (
                        <span style={{ fontSize: "0.82rem", color: "var(--muted)" }}>
                          {" "}
                          ({d.precios_modificados ?? 0} precios, {d.stock_altas ?? 0} altas, {d.stock_bajas ?? 0} bajas, {d.ubic_mod ?? 0} ubic)
                        </span>
                      ) : null}
                      , {d.codigos_nuevos} nuevos, {d.precios_propagados} prop. · {d.codigos_sin_precio} sin precio <span title="Sin K/U — K y U no llevan precio" style={{ cursor: "help" }}>(sin K/U)</span>
                      {d.reporte && d.reporte.length > 2000 ? (
                        <details style={{ marginTop: 6 }}>
                          <summary style={{ cursor: "pointer", fontSize: "0.8rem", color: "var(--muted)" }}>Ver reporte (texto)</summary>
                          <pre style={{ margin: "8px 0 0", padding: 10, background: "color-mix(in srgb, var(--bg) 60%, var(--surface))", border: "1px solid var(--border)", borderRadius: 8, fontSize: "0.75rem", whiteSpace: "pre-wrap", wordBreak: "break-word", maxHeight: 220, overflow: "auto" }}>
                            {d.reporte.slice(0, 4000)}
                            {d.reporte.length > 4000 ? "\n… truncado — ver diff estructurado abajo" : ""}
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
              API: /api/maestro-stock/import · archivos: {displayResult.archivos} · Firestore buscador: {displayResult.firestore_pushed ?? displayResult.detalle.reduce((a, d) => a + (d.firestore_pushed ?? 0), 0)} sincronizados
              {(displayResult.firestore_errors ?? displayResult.detalle.reduce((a, d) => a + (d.firestore_errors ?? 0), 0)) > 0 ? ` (${displayResult.firestore_errors ?? displayResult.detalle.reduce((a, d) => a + (d.firestore_errors ?? 0), 0)} errores — ver reporte)` : " — el detalle estructurado con filtros está en “Último import persistido” y en el historial."}
            </p>
          </div>
        )}

        {/* Persistent last import */}
        {persistentLast && (
          <div
            style={{
              border: "1px solid var(--border)",
              background: "var(--surface)",
              borderRadius: 10,
              padding: 14,
              display: "flex",
              flexDirection: "column",
              gap: 12,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
              <h3 style={{ margin: 0, fontSize: "0.95rem" }}>
                Último import persistido <span style={{ fontWeight: 400, fontSize: "0.8rem", color: "var(--muted)" }}>· {persistentLast.archivo_origen} ({persistentLast.tipo_archivo}) · {formatDate(persistentLast.creado_en)} · id {persistentLast.id}</span>
              </h3>
              <span style={{ fontSize: "0.72rem", padding: "2px 8px", borderRadius: 999, background: "var(--primary)", color: "white", fontWeight: 700 }}>PERSISTENTE</span>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(100px, 1fr))", gap: 10 }}>
              {[
                { label: "Nuevos", value: persistentLast.codigos_nuevos },
                { label: "Modificados", value: persistentLast.codigos_modificados },
                { label: "Sin precio", value: persistentLast.codigos_sin_precio, global: true },
                { label: "Precios mod", value: persistentLast.precios_modificados ?? 0 },
                { label: "Ubic", value: persistentLast.ubic_mod ?? 0 },
                { label: "Stock altas/bajas", value: `${persistentLast.stock_altas ?? 0}/${persistentLast.stock_bajas ?? 0}` },
              ].map(({ label, value, global }) => (
                <div key={label} style={{ border: "1px solid var(--border)", borderRadius: 8, padding: "10px 8px", textAlign: "center", background: "color-mix(in srgb, var(--surface) 90%, var(--bg))" }}>
                  <div style={{ fontSize: "1.15rem", fontWeight: 800 }}>{value as string | number}</div>
                  <div style={{ fontSize: "0.68rem", color: "var(--muted)", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.03em" }}>
                    {label} {global ? <span title="Total sin precio excluyendo K y U (no llevan precio)">(sin K/U)</span> : null}
                  </div>
                </div>
              ))}
            </div>
            {lastDiffLoading ? (
              <p className="sub" style={{ margin: 0 }}>Cargando diff estructurado…</p>
            ) : lastDiff ? (
              <DiffTable
                rows={lastDiff.items}
                filterCodigo={persistentFilterCodigo}
                setFilterCodigo={setPersistentFilterCodigo}
                filterCampo={persistentFilterCampo}
                setFilterCampo={setPersistentFilterCampo}
                onViewHistory={(c) => void openHistory(c)}
              />
            ) : (
              <p className="sub" style={{ margin: 0 }}>Sin diff estructurado — ver reporte texto.</p>
            )}
            <p className="sub" style={{ margin: 0, fontSize: "0.75rem" }}>Este bloque no se borra con “Limpiar archivos” — queda como referencia histórica.</p>
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
        {statsError && <p className="error" style={{ margin: 0 }}>{statsError}</p>}
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
                <div style={{ fontSize: "0.78rem", color: "var(--muted)", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.03em" }}>
                  Sin precio <span title="Total con precio <=0 excluyendo K y U (no llevan precio) — total con K/U sería { (stats.sin_precio_total ?? stats.sin_precio).toLocaleString('es-AR') }" style={{ cursor: "help", textDecoration: "underline dotted" }}>(sin K/U)</span>
                </div>
              </div>
            </div>
            {stats.por_importancia && Object.keys(stats.por_importancia).length > 0 && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 12 }}>
                {Object.entries(stats.por_importancia).map(([k, v]) => (
                  <span key={k} style={{ fontSize: "0.78rem", fontWeight: 700, padding: "4px 10px", borderRadius: 999, background: "color-mix(in srgb, var(--border) 45%, var(--surface))", border: "1px solid var(--border)", color: "var(--text)" }}>
                    {k}: {v}
                  </span>
                ))}
              </div>
            )}
          </>
        )}
        {!statsLoading && !statsError && !stats && <p className="sub" style={{ margin: 0 }}>Sin datos.</p>}
      </section>

      {/* Import log with expandable diff */}
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
          <button type="button" className="btn-secondary" onClick={handleViewLastUpdate} disabled={logs.length === 0} style={{ minHeight: 32, fontSize: "0.78rem", opacity: logs.length === 0 ? 0.5 : 1 }}>
            Última actualización
          </button>
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
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ overflowX: "auto", border: "1px solid var(--border)", borderRadius: 8 }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem", minWidth: 760 }}>
                <thead>
                  <tr style={{ background: "color-mix(in srgb, var(--surface) 88%, var(--border))" }}>
                    <th style={{ textAlign: "left", padding: "9px 10px", fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.03em", color: "var(--muted)", borderBottom: "1px solid var(--border)" }}></th>
                    <th style={{ textAlign: "left", padding: "9px 10px", fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.03em", color: "var(--muted)", borderBottom: "1px solid var(--border)" }}>Archivo</th>
                    <th style={{ textAlign: "left", padding: "9px 10px", fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.03em", color: "var(--muted)", borderBottom: "1px solid var(--border)" }}>Tipo</th>
                    <th style={{ textAlign: "right", padding: "9px 10px", fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.03em", color: "var(--muted)", borderBottom: "1px solid var(--border)" }}>Nuevos</th>
                    <th style={{ textAlign: "right", padding: "9px 10px", fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.03em", color: "var(--muted)", borderBottom: "1px solid var(--border)" }}>Mod</th>
                    <th style={{ textAlign: "right", padding: "9px 10px", fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.03em", color: "var(--muted)", borderBottom: "1px solid var(--border)" }}>
                      <span title="Total sin precio excluyendo K y U (no llevan precio)">(sin K/U)</span> Sin precio
                    </th>
                    <th style={{ textAlign: "right", padding: "9px 10px", fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.03em", color: "var(--muted)", borderBottom: "1px solid var(--border)" }}>Duración</th>
                    <th style={{ textAlign: "left", padding: "9px 10px", fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.03em", color: "var(--muted)", borderBottom: "1px solid var(--border)" }}>Fecha</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map((l) => {
                    const exp = expandedLogs[l.id];
                    const isExpanded = !!exp;
                    return (
                      <>
                        <tr key={l.id} style={{ borderBottom: isExpanded ? "none" : "1px solid var(--border)", background: isExpanded ? "color-mix(in srgb, var(--primary) 4%, var(--surface))" : undefined }}>
                          <td style={{ padding: "9px 10px" }}>
                            <button type="button" onClick={() => void toggleExpand(l)} style={{ border: "1px solid var(--border)", background: "var(--surface)", borderRadius: 6, width: 24, height: 24, display: "grid", placeItems: "center", cursor: "pointer" }} aria-label={isExpanded ? "Colapsar" : "Expandir"}>
                              {isExpanded ? "−" : "+"}
                            </button>
                          </td>
                          <td title={l.archivo_origen} style={{ padding: "9px 10px", maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontWeight: 600 }}>
                            {truncate(l.archivo_origen, 26)}
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
                        {isExpanded && (
                          <tr key={`${l.id}-expanded`} style={{ borderBottom: "1px solid var(--border)" }}>
                            <td colSpan={8} style={{ padding: "12px", background: "color-mix(in srgb, var(--bg) 45%, var(--surface))" }}>
                              {exp.loading ? (
                                <p className="sub" style={{ margin: 0 }}>Cargando diff…</p>
                              ) : (
                                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap", fontSize: "0.75rem", color: "var(--muted)" }}>
                                    <span>Desglose: {exp.diff?.items.length ?? 0} cambios de campo</span>
                                    {(l as ImportLog).precios_modificados !== undefined && <span>· {l.precios_modificados} precios</span>}
                                    {(l as ImportLog).ubic_mod !== undefined && <span>· {l.ubic_mod} ubic</span>}
                                    {(l as ImportLog).stock_altas !== undefined && <span>· {l.stock_altas} altas / {l.stock_bajas} bajas</span>}
                                  </div>
                                  <ExpandableDiff id={l.id} diff={exp.diff} onViewHistory={(c) => void openHistory(c)} />
                                  <details style={{ marginTop: 4 }}>
                                    <summary style={{ cursor: "pointer", fontSize: "0.8rem", color: "var(--muted)" }}>Ver reporte raw (texto)</summary>
                                    <pre style={{ margin: "8px 0 0", padding: 10, background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, fontSize: "0.72rem", whiteSpace: "pre-wrap", wordBreak: "break-word", maxHeight: 200, overflow: "auto" }}>
                                      {exp.reporte || "Sin reporte"}
                                    </pre>
                                  </details>
                                </div>
                              )}
                            </td>
                          </tr>
                        )}
                      </>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>

      {/* Modal: Last import detail */}
      {modalOpen && selectedLog && (
        <div role="dialog" aria-modal="true" aria-label="Última actualización" onClick={closeModal} style={{ position: "fixed", inset: 0, background: "rgba(15,23,42,0.48)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 65, padding: 16 }}>
          <div onClick={(e) => e.stopPropagation()} style={{ background: "var(--surface, #fff)", border: "0.5px solid var(--border, #e2e8f0)", borderRadius: 12, width: "min(860px, 96vw)", maxHeight: "90vh", overflow: "auto", boxShadow: "0 20px 60px rgba(0,0,0,0.22)", display: "flex", flexDirection: "column" }}>
            <div style={{ padding: "14px 16px 0", display: "flex", justifyContent: "space-between", gap: 12, alignItems: "start" }}>
              <div>
                <h2 style={{ margin: 0, fontFamily: "var(--font-display)", fontSize: "1.15rem" }}>Última actualización</h2>
                <p className="sub" style={{ margin: "4px 0 0" }}>
                  {selectedLog.archivo_origen} · {selectedLog.tipo_archivo} · {formatDate(selectedLog.creado_en)} · id {selectedLog.id}
                </p>
              </div>
              <button type="button" className="btn-secondary" onClick={closeModal} aria-label="Cerrar" style={{ minHeight: 36 }}>
                ✕
              </button>
            </div>

            <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 10, flex: 1, minHeight: 0 }}>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(100px, 1fr))", gap: 10 }}>
                {[
                  { label: "Nuevos", value: selectedLog.codigos_nuevos },
                  { label: "Modificados", value: selectedLog.codigos_modificados },
                  { label: "Sin precio (sin K/U)", value: selectedLog.codigos_sin_precio },
                  { label: "Duración", value: `${selectedLog.duracion_ms} ms` },
                  { label: "Precios", value: selectedLog.precios_modificados ?? 0 },
                  { label: "Ubic", value: selectedLog.ubic_mod ?? 0 },
                ].map(({ label, value }) => (
                  <div key={label} style={{ border: "1px solid var(--border)", borderRadius: 8, padding: "10px 8px", textAlign: "center", background: "color-mix(in srgb, var(--surface) 90%, var(--bg))" }}>
                    <div style={{ fontSize: "1.15rem", fontWeight: 800 }}>{value}</div>
                    <div style={{ fontSize: "0.68rem", color: "var(--muted)", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.03em" }}>{label}</div>
                  </div>
                ))}
              </div>
              {selectedLogReporte && selectedLogReporte.includes(">> RESUMEN") && (
                <div style={{ background: "color-mix(in srgb, var(--primary) 6%, var(--surface))", border: "1px solid color-mix(in srgb, var(--primary) 14%, var(--border))", borderRadius: 8, padding: "10px 12px", fontSize: "0.82rem", lineHeight: 1.4 }}>
                  <strong>Desglose:</strong> {selectedLogReporte.split("\n").find((l) => l.includes(">> RESUMEN"))?.replace(">> RESUMEN:", "").trim()}
                  {selectedLogReporte.includes(">> PROPAGADOS") && (
                    <div style={{ marginTop: 4, fontSize: "0.78rem", color: "var(--muted)" }}>{selectedLogReporte.split("\n").find((l) => l.includes(">> PROPAGADOS"))?.replace(">>", "").trim()}</div>
                  )}
                </div>
              )}

              {selectedLogDiffLoading ? (
                <p className="sub" style={{ margin: 0 }}>Cargando diff estructurado…</p>
              ) : selectedLogDiff ? (
                <DiffTable rows={selectedLogDiff.items} filterCodigo={modalFilterCodigo} setFilterCodigo={setModalFilterCodigo} filterCampo={modalFilterCampo} setFilterCampo={setModalFilterCampo} onViewHistory={(c) => void openHistory(c)} />
              ) : null}

              <div style={{ marginTop: 4 }}>
                <h3 style={{ margin: "0 0 6px", fontSize: "0.88rem" }}>Reporte raw</h3>
                {selectedLogReporte ? (
                  <pre style={{ margin: 0, padding: 12, background: "color-mix(in srgb, var(--bg) 60%, var(--surface))", border: "1px solid var(--border)", borderRadius: 8, fontSize: "0.72rem", whiteSpace: "pre-wrap", wordBreak: "break-word", maxHeight: 220, overflow: "auto", fontFamily: "monospace" }}>
                    {selectedLogReporte}
                  </pre>
                ) : (
                  <p className="sub" style={{ margin: 0 }}>Sin reporte disponible.</p>
                )}
              </div>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", padding: "12px 16px", borderTop: "1px solid var(--border)" }}>
              <button type="button" className="btn-secondary" onClick={closeModal} style={{ minHeight: 40 }}>
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* History drawer */}
      {historyCodigo && (
        <div role="dialog" aria-modal="true" aria-label={`Historial ${historyCodigo}`} onClick={closeHistory} style={{ position: "fixed", inset: 0, background: "rgba(15,23,42,0.48)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 70, padding: 16 }}>
          <div onClick={(e) => e.stopPropagation()} style={{ background: "var(--surface, #fff)", border: "0.5px solid var(--border, #e2e8f0)", borderRadius: 12, width: "min(780px, 96vw)", maxHeight: "90vh", overflow: "auto", boxShadow: "0 20px 60px rgba(0,0,0,0.22)", display: "flex", flexDirection: "column" }}>
            <div style={{ padding: "14px 16px 0", display: "flex", justifyContent: "space-between", gap: 12, alignItems: "start" }}>
              <div>
                <h2 style={{ margin: 0, fontFamily: "var(--font-display)", fontSize: "1.15rem" }}>Historial de {historyCodigo}</h2>
                <p className="sub" style={{ margin: "4px 0 0" }}>{historyData ? `${historyData.total} cambios registrados` : "Cargando…"}</p>
              </div>
              <button type="button" className="btn-secondary" onClick={closeHistory} aria-label="Cerrar" style={{ minHeight: 36 }}>
                ✕
              </button>
            </div>
            <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12, flex: 1, minHeight: 0 }}>
              {historyLoading ? (
                <p className="sub" style={{ margin: 0 }}>Cargando historial…</p>
              ) : !historyData || historyData.items.length === 0 ? (
                <p className="sub" style={{ margin: 0 }}>Sin historial para {historyCodigo} (empieza a registrarse desde la próxima importación).</p>
              ) : (
                <>
                  <div style={{ overflowX: "auto", border: "1px solid var(--border)", borderRadius: 8 }}>
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem", minWidth: 560 }}>
                      <thead>
                        <tr style={{ background: "color-mix(in srgb, var(--surface) 88%, var(--border))" }}>
                          <th style={{ textAlign: "left", padding: "8px 10px", fontSize: "0.72rem", textTransform: "uppercase", color: "var(--muted)", borderBottom: "1px solid var(--border)" }}>Fecha</th>
                          <th style={{ textAlign: "left", padding: "8px 10px", fontSize: "0.72rem", textTransform: "uppercase", color: "var(--muted)", borderBottom: "1px solid var(--border)" }}>Campo</th>
                          <th style={{ textAlign: "left", padding: "8px 10px", fontSize: "0.72rem", textTransform: "uppercase", color: "var(--muted)", borderBottom: "1px solid var(--border)" }}>Antes → Después</th>
                          <th style={{ textAlign: "left", padding: "8px 10px", fontSize: "0.72rem", textTransform: "uppercase", color: "var(--muted)", borderBottom: "1px solid var(--border)" }}>Origen</th>
                        </tr>
                      </thead>
                      <tbody>
                        {historyData.items.map((r) => (
                          <tr key={r.id} style={{ borderBottom: "1px solid var(--border)" }}>
                            <td style={{ padding: "8px 10px", whiteSpace: "nowrap", fontSize: "0.8rem", color: "var(--muted)" }}>{r.creado_en ? formatDate(r.creado_en) : "—"} <span style={{ fontSize: "0.7rem" }}>· id {r.import_log_id}</span></td>
                            <td style={{ padding: "8px 10px", fontWeight: 600 }}>{r.campo}</td>
                            <td style={{ padding: "8px 10px" }}>
                              <span style={{ color: "var(--muted)" }}>{r.valor_antes ?? "∅"}</span> → <span style={{ fontWeight: 700 }}>{r.valor_despues}</span>
                            </td>
                            <td style={{ padding: "8px 10px" }}>
                              <span style={{ fontSize: "0.72rem", padding: "1px 6px", borderRadius: 999, background: `color-mix(in srgb, ${pillColor(r.tipo_archivo)} 14%, var(--surface))`, color: pillColor(r.tipo_archivo), border: `1px solid color-mix(in srgb, ${pillColor(r.tipo_archivo)} 24%, transparent)` }}>{r.tipo_archivo}</span>{" "}
                              <span style={{ fontSize: "0.75rem", color: "var(--muted)" }}>{truncate(r.archivo_origen, 20)}</span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
                    <span className="sub" style={{ margin: 0, fontSize: "0.8rem" }}>
                      Página {historyData.page} de {Math.max(1, Math.ceil(historyData.total / historyData.limit))} · {historyData.total} total
                    </span>
                    <div style={{ display: "flex", gap: 8 }}>
                      <button type="button" className="btn-secondary" disabled={historyPage <= 1} onClick={() => void openHistory(historyCodigo!, historyPage - 1)} style={{ minHeight: 32 }}>
                        Anterior
                      </button>
                      <button type="button" className="btn-secondary" disabled={historyPage * historyData.limit >= historyData.total} onClick={() => void openHistory(historyCodigo!, historyPage + 1)} style={{ minHeight: 32 }}>
                        Siguiente
                      </button>
                    </div>
                  </div>
                </>
              )}
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", padding: "12px 16px", borderTop: "1px solid var(--border)" }}>
              <button type="button" className="btn-secondary" onClick={closeHistory} style={{ minHeight: 40 }}>
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ExpandableDiff({ id: _id, diff, onViewHistory }: { id: number; diff: ImportDiffResult | null; onViewHistory: (codigo: string) => void }) {
  const [fCodigo, setFCodigo] = useState("");
  const [fCampo, setFCampo] = useState("all");
  // _id keeps hook order stable, used for keys outside
  void _id;
  if (!diff || diff.items.length === 0) return <p className="sub" style={{ margin: 0, fontSize: "0.8rem" }}>Sin diff estructurado para este log (histórico sin audit).</p>;
  return <DiffTable rows={diff.items} filterCodigo={fCodigo} setFilterCodigo={setFCodigo} filterCampo={fCampo} setFilterCampo={setFCampo} onViewHistory={onViewHistory} compact />;
}
