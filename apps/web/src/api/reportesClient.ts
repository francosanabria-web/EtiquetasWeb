/**
 * Cliente del servicio Reportes (:8017).
 * Vacío = proxy Vite /api/reportes → :8017.
 *
 * Consultas operativas de movimientos (distinto de KPIs).
 * Fuente: master_salidas (solo lectura; prod por defecto). Futuro: API Salidas / SQL.
 */

const BASE = (import.meta.env.VITE_REPORTES_API_URL ?? "").replace(/\/$/, "");
const TIMEOUT_MS = 60_000;

export type MovimientoItem = {
  fecha: string;
  mes: string;
  anio: string;
  codigo: string;
  descripcion: string;
  ubicacion: string;
  cantidad: number;
  tipo_comprobante: string;
  numero_orden: string;
  maquina_sitio: string;
  precio_unitario: number;
  monto_total_salida: number;
  operario: string;
  sector: string;
};

export type FuenteMeta = {
  archivo_ok: boolean;
  path: string;
  filas: number;
  ultima_actualizacion: string;
  error?: string | null;
};

export type MovimientosResponse = {
  total: number;
  limite: number;
  offset: number;
  items: MovimientoItem[];
  fuente: FuenteMeta;
};

export type AgregadoNombre = {
  filas: number;
  monto: number;
};

export type ResumenReportes = {
  filas: number;
  monto_total: number;
  cantidad_total: number;
  por_sector: (AgregadoNombre & { sector: string })[];
  por_operario: (AgregadoNombre & { operario: string })[];
  por_tipo_comprobante: (AgregadoNombre & { tipo_comprobante: string })[];
  por_mes: { mes: string; filas: number; monto: number }[];
  fuente: FuenteMeta;
};

export type FiltrosOpciones = {
  sectores: string[];
  operarios: string[];
  tipos_comprobante: string[];
  fecha_min: string;
  fecha_max: string;
  fuente: FuenteMeta;
};

export type FiltrosQuery = {
  fecha_desde?: string;
  fecha_hasta?: string;
  sector?: string;
  operario?: string;
  codigo?: string;
  numero_orden?: string;
  tipo_comprobante?: string;
  q?: string;
  limite?: number;
  offset?: number;
};

function qs(params: FiltrosQuery): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    sp.set(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(`${BASE}${path}`, { ...init, signal: ctrl.signal });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = typeof data.detail === "string" ? data.detail : `Error ${res.status}`;
      if (res.status === 503) {
        throw new Error(`${detail} (servicio iniciando o datos en carga — reintente).`);
      }
      throw new Error(detail);
    }
    return data as T;
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") {
      throw new Error("Tiempo de espera agotado al contactar el servicio Reportes.");
    }
    if (e instanceof TypeError) {
      throw new Error(
        "No se pudo conectar con Reportes (:8017). Verificá _start_reportes.bat o PortalPanol.",
      );
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

export async function fetchHealth(): Promise<{ estado: string; filas?: number; path?: string }> {
  return fetchJson("/api/reportes/health");
}

export async function fetchFiltros(): Promise<FiltrosOpciones> {
  return fetchJson("/api/reportes/filtros");
}

export async function fetchMovimientos(filtros: FiltrosQuery = {}): Promise<MovimientosResponse> {
  return fetchJson(`/api/reportes/movimientos${qs(filtros)}`);
}

export async function fetchResumen(filtros: FiltrosQuery = {}): Promise<ResumenReportes> {
  return fetchJson(`/api/reportes/resumen${qs(filtros)}`);
}

export async function refreshReportes(): Promise<{ mensaje: string; filas: number }> {
  return fetchJson("/api/reportes/refresh", { method: "POST" });
}

/** Descarga Excel Table (layout diario de gastos). Preferido. */
export function urlExportXlsx(filtros: FiltrosQuery = {}): string {
  return `${BASE}/api/reportes/export.xlsx${qs(filtros)}`;
}

/** @deprecated Preferir urlExportXlsx */
export function urlExportCsv(filtros: FiltrosQuery = {}): string {
  return `${BASE}/api/reportes/export.csv${qs(filtros)}`;
}

export function fmtPesos(n: number): string {
  return n.toLocaleString("es-AR", { style: "currency", currency: "ARS", maximumFractionDigits: 0 });
}

export function fmtNum(n: number): string {
  return n.toLocaleString("es-AR", { maximumFractionDigits: 2 });
}
