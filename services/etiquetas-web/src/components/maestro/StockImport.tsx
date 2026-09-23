/**
 * StockImport - Reusable drag&drop component for maestro_stock import.
 * Purpose: Handles multi-file .xlsx selection, upload to /api/maestro-stock/import,
 *          shows progress and post-import summary (nuevos/modificados/precios).
 * Usage: <StockImport apiBase={SALIDAS_API_URL} onSuccess={...} />
 */

import { useCallback, useEffect, useRef, useState } from "react";

const SALIDAS_API_URL = (
  (import.meta.env.VITE_SALIDAS_API_URL as string | undefined) ??
  (import.meta.env.VITE_API_URL as string | undefined) ??
  "http://localhost:8018"
).replace(/\/$/, "");

type ImportDetail = {
  archivo: string;
  tipo: string;
  codigos_nuevos: number;
  codigos_modificados: number;
  codigos_sin_precio: number;
  precios_propagados: number;
  reporte?: string;
};

type ImportResult = {
  archivos: number;
  codigos_nuevos: number;
  codigos_modificados: number;
  codigos_sin_precio: number;
  precios_propagados: number;
  detalle: ImportDetail[];
};

type ImportLog = {
  id: number;
  archivo_origen: string;
  tipo_archivo: string;
  codigos_nuevos: number;
  codigos_modificados: number;
  codigos_sin_precio: number;
  duracion_ms: number;
  creado_en: string;
};

type Status = "idle" | "uploading" | "success" | "error";

export default function StockImport({
  onImported,
}: {
  onImported?: () => void;
}) {
  const [files, setFiles] = useState<File[]>([]);
  const [status, setStatus] = useState<Status>("idle");
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const addFiles = useCallback((incoming: FileList | File[]) => {
    const arr = Array.from(incoming).filter((f) => f.name.toLowerCase().endsWith(".xlsx"));
    if (arr.length === 0) return;
    setFiles((prev) => {
      // Dedupe by name+size
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
    [addFiles]
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
      const fd = new FormData();
      for (const f of files) fd.append("files", f);
      const resp = await fetch(`${SALIDAS_API_URL}/api/maestro-stock/import`, {
        method: "POST",
        body: fd,
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        throw new Error((data as { detail?: string })?.detail || `Error ${resp.status}`);
      }
      setResult(data as ImportResult);
      setStatus("success");
      onImported?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al importar");
      setStatus("error");
    }
  };

  return (
    <div className="stock-import">
      <div
        className={`dropzone ${dragOver ? "dragover" : ""}`}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter") inputRef.current?.click();
        }}
        aria-label="Zona para arrastrar archivos Excel"
      >
        <div className="dropzone-icon">📦</div>
        <div className="dropzone-text">
          <strong>Arrastrá archivos .xlsx aquí</strong> o hacé click para seleccionar
        </div>
        <div className="dropzone-hint">1 a 20 archivos — se clasifican por nombre: detallado / valorizado / general</div>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept=".xlsx"
        multiple
        style={{ display: "none" }}
        onChange={(e) => {
          if (e.target.files) addFiles(e.target.files);
          // reset input to allow re-select same file
          e.target.value = "";
        }}
      />

      {files.length > 0 && (
        <ul className="file-list">
          {files.map((f, i) => (
            <li key={`${f.name}-${f.size}-${i}`} className="file-item">
              <span className="file-name">{f.name}</span>
              <span className="file-meta">
                {(f.size / 1024).toFixed(1)} KB —{" "}
                <span className="file-tipo">
                  {f.name.toLowerCase().includes("detallado")
                    ? "detallado"
                    : f.name.toLowerCase().includes("valorizado")
                      ? "valorizado"
                      : "general"}
                </span>
              </span>
              <button type="button" className="file-remove" onClick={() => removeFile(i)} aria-label={`Quitar ${f.name}`}>
                ×
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="import-actions">
        <button type="button" className="btn-primario" disabled={files.length === 0 || status === "uploading"} onClick={handleImport}>
          {status === "uploading" ? "Importando…" : "Importar stock"}
        </button>
        {files.length > 0 && status !== "uploading" && (
          <button type="button" className="btn-ghost" onClick={() => setFiles([])}>
            Limpiar
          </button>
        )}
      </div>

      {status === "uploading" && <p className="hint">Procesando en servidor — esto puede tardar algunos segundos…</p>}
      {status === "error" && error && <p className="hint error">Error: {error}</p>}

      {status === "success" && result && (
        <div className="import-result">
          <h4>Resumen importación</h4>
          <div className="result-grid">
            <div className="result-item">
              <span className="result-val">{result.codigos_modificados}</span>
              <span className="result-label">Modificados</span>
            </div>
            <div className="result-item">
              <span className="result-val">{result.codigos_nuevos}</span>
              <span className="result-label">Nuevos</span>
            </div>
            <div className="result-item">
              <span className="result-val">{result.precios_propagados}</span>
              <span className="result-label">Precios propagados</span>
            </div>
            <div className="result-item">
              <span className="result-val">{result.codigos_sin_precio}</span>
              <span className="result-label">Sin precio</span>
            </div>
          </div>
          {result.detalle?.length ? (
            <details className="result-details">
              <summary>Detalle por archivo ({result.detalle.length})</summary>
              <ul className="detail-list">
                {result.detalle.map((d, i) => (
                  <li key={i}>
                    <strong>{d.archivo}</strong> ({d.tipo}): {d.codigos_modificados} mod, {d.codigos_nuevos} nuevos
                  </li>
                ))}
              </ul>
            </details>
          ) : null}
          <p className="hint">API: {SALIDAS_API_URL}/api/maestro-stock/import</p>
        </div>
      )}
    </div>
  );
}

// Helper component for import log table (exported for Configuracion to reuse logic)
export function useImportLog(refreshKey: number) {
  const [logs, setLogs] = useState<ImportLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const resp = await fetch(`${SALIDAS_API_URL}/api/maestro-stock/import-log`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = (await resp.json()) as { items: ImportLog[] };
      setLogs(data.items || []);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Error al cargar log");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchLogs();
  }, [fetchLogs, refreshKey]);

  return { logs, loading, err, refetch: fetchLogs };
}

export function useMaestroStats(refreshKey: number) {
  const [stats, setStats] = useState<{ total: number; sin_precio: number; criticos: number; por_importancia?: Record<string, number> } | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const fetchStats = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const resp = await fetch(`${SALIDAS_API_URL}/api/maestro-stock/stats`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = (await resp.json()) as typeof stats;
      setStats(data);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Error al cargar stats");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchStats();
  }, [fetchStats, refreshKey]);

  return { stats, loading, err, refetch: fetchStats };
}
