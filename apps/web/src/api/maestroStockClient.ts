/**
 * Cliente maestro_stock — import/stats/log via :8018 /api/maestro-stock
 * BASE vacío = proxy Vite /api/maestro-stock → :8018
 */

const BASE = (import.meta.env.VITE_SALIDAS_API_URL ?? "").replace(/\/$/, "");
const TIMEOUT_MS = 120_000;

export type ImportDetail = {
  archivo: string;
  tipo: string;
  codigos_nuevos: number;
  codigos_modificados: number;
  codigos_sin_precio: number;
  precios_propagados: number;
  duracion_ms?: number;
  reporte?: string;
  propagated_rows?: number;
  // Desglose distinguido (v2)
  precios_modificados?: number;
  stock_altas?: number;
  stock_bajas?: number;
  stock_min_mod?: number;
  ubic_mod?: number;
  otros_mod?: number;
};

export type ImportResult = {
  archivos: number;
  codigos_nuevos: number;
  codigos_modificados: number;
  codigos_sin_precio: number;
  precios_propagados: number;
  detalle: ImportDetail[];
};

export type ImportLog = {
  id: number;
  archivo_origen: string;
  tipo_archivo: string;
  codigos_nuevos: number;
  codigos_modificados: number;
  codigos_sin_precio: number;
  duracion_ms: number;
  creado_en: string;
  reporte?: string | null;
  // Campos nuevos para reporte distinguido (pueden no venir en logs viejos)
  precios_modificados?: number;
  stock_altas?: number;
  stock_bajas?: number;
  stock_min_mod?: number;
  ubic_mod?: number;
  otros_mod?: number;
  precios_propagados?: number;
  propagated_rows?: number;
};

export type MaestroStats = {
  total: number;
  sin_precio: number;
  sin_precio_total?: number;
  sin_precio_ku_excluidos?: number;
  criticos: number;
  por_importancia: Record<string, number>;
};

export type MaestroListItem = {
  codigo: string;
  descripcion: string;
  alias?: string | null;
  stock: number;
  stock_minimo: number;
  ubicacion: string | null;
  precio_unitario: number;
  importancia: string;
  categoria: string | null;
  activo: number | boolean;
  actualizado_en?: string;
};

export type MaestroListParams = {
  q?: string;
  page?: number;
  limit?: number;
  importancia?: string;
  categoria?: string;
  ubicacion?: string;
};

export type MaestroListResult = {
  total: number;
  page: number;
  limit: number;
  items: MaestroListItem[];
};

function authHeaders(token?: string): Record<string, string> {
  if (token) return { Authorization: `Bearer ${token}` };
  try {
    const raw = localStorage.getItem("panol_shell_session");
    if (raw) {
      const parsed = JSON.parse(raw) as { token?: string };
      if (typeof parsed.token === "string" && parsed.token) {
        return { Authorization: `Bearer ${parsed.token}` };
      }
    }
  } catch {
    // ignore
  }
  return {};
}

async function fetchJson<T>(path: string, init?: RequestInit, token?: string): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  try {
    const headers: Record<string, string> = {
      ...(authHeaders(token) as Record<string, string>),
      ...((init?.headers as Record<string, string>) ?? {}),
    };
    // For JSON, ensure Content-Type
    if (init?.body && typeof init.body === "string" && !headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }
    const res = await fetch(`${BASE}${path}`, { ...init, signal: ctrl.signal, headers });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail =
        typeof (data as { detail?: unknown }).detail === "string"
          ? (data as { detail: string }).detail
          : `Error ${res.status}`;
      if (res.status === 503) {
        throw new Error(`${detail} (servicio iniciando — espere y reintente).`);
      }
      throw new Error(detail);
    }
    return data as T;
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") {
      throw new Error("Tiempo de espera agotado al contactar maestro stock.");
    }
    if (e instanceof TypeError) {
      throw new Error("No se pudo conectar con maestro stock (:8018). Verificá que Salidas esté corriendo.");
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

export async function importMaestroStock(files: File[], token?: string): Promise<ImportResult> {
  if (!files.length) throw new Error("Seleccioná al menos un archivo .xlsx");
  if (files.length > 20) throw new Error("Máximo 20 archivos por importación");
  const fd = new FormData();
  for (const f of files) fd.append("files", f);

  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  try {
    const headers = authHeaders(token);
    const res = await fetch(`${BASE}/api/maestro-stock/import`, {
      method: "POST",
      body: fd,
      headers,
      signal: ctrl.signal,
    });
    // Do NOT set Content-Type for multipart — browser sets boundary
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail =
        typeof (data as { detail?: unknown }).detail === "string"
          ? (data as { detail: string }).detail
          : `Error ${res.status}`;
      throw new Error(detail);
    }
    return data as ImportResult;
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") {
      throw new Error("Tiempo de espera agotado al importar maestro stock.");
    }
    if (e instanceof TypeError) {
      throw new Error("No se pudo conectar con maestro stock (:8018).");
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

export function getImportLog(token?: string): Promise<{ items: ImportLog[] }> {
  return fetchJson<{ items: ImportLog[] }>("/api/maestro-stock/import-log", {}, token);
}

export function getImportLogById(id: number, token?: string): Promise<ImportLog> {
  return fetchJson<ImportLog>(`/api/maestro-stock/import-log/${id}`, {}, token);
}

export type ImportDiffRow = {
  id?: number;
  codigo: string;
  campo: string;
  valor_antes: string | null;
  valor_despues: string;
  archivo_origen: string;
  tipo_archivo: string;
  import_log_id: number;
  creado_en: string | null;
};

export type ImportDiffResult = {
  import_log_id: number;
  archivo_origen: string;
  tipo_archivo: string;
  creado_en: string | null;
  items: ImportDiffRow[];
};

export type CodigoHistoryResult = {
  codigo: string;
  total: number;
  page: number;
  limit: number;
  items: ImportDiffRow[];
};

export function getImportDiff(id: number, token?: string): Promise<ImportDiffResult> {
  return fetchJson<ImportDiffResult>(`/api/maestro-stock/import-log/${id}/diff`, {}, token);
}

export function getCodigoHistory(codigo: string, params?: { page?: number; limit?: number }, token?: string): Promise<CodigoHistoryResult> {
  const sp = new URLSearchParams();
  if (params?.page) sp.set("page", String(params.page));
  if (params?.limit) sp.set("limit", String(params.limit));
  const qs = sp.toString();
  return fetchJson<CodigoHistoryResult>(`/api/maestro-stock/${encodeURIComponent(codigo)}/history${qs ? `?${qs}` : ""}`, {}, token);
}

export function diffRowsToCsv(rows: ImportDiffRow[]): string {
  const header = "codigo,campo,antes,despues,archivo,tipo,import_log_id,creado_en";
  const esc = (s: string | null | undefined) => {
    if (s == null) return "";
    const str = String(s);
    if (str.includes(",") || str.includes('"') || str.includes("\n")) return '"' + str.replace(/"/g, '""') + '"';
    return str;
  };
  const lines = rows.map((r) => [esc(r.codigo), esc(r.campo), esc(r.valor_antes), esc(r.valor_despues), esc(r.archivo_origen), esc(r.tipo_archivo), String(r.import_log_id), esc(r.creado_en)].join(","));
  return [header, ...lines].join("\n");
}

export function diffRowsToTsv(rows: ImportDiffRow[]): string {
  return rows.map((r) => [r.codigo, r.campo, r.valor_antes ?? "", r.valor_despues, r.archivo_origen, r.tipo_archivo].join("\t")).join("\n");
}

export function getMaestroStats(token?: string): Promise<MaestroStats> {
  return fetchJson<MaestroStats>("/api/maestro-stock/stats", {}, token);
}

export function listMaestro(params: MaestroListParams, token?: string): Promise<MaestroListResult> {
  const sp = new URLSearchParams();
  if (params.q) sp.set("q", params.q);
  if (params.page) sp.set("page", String(params.page));
  if (params.limit) sp.set("limit", String(params.limit));
  if (params.importancia) sp.set("importancia", params.importancia);
  if (params.categoria) sp.set("categoria", params.categoria);
  if (params.ubicacion) sp.set("ubicacion", params.ubicacion);
  const qs = sp.toString();
  return fetchJson<MaestroListResult>(`/api/maestro-stock${qs ? `?${qs}` : ""}`, {}, token);
}
