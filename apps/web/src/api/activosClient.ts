/**
 * Cliente del servicio Activos fuera de planta (:8016).
 * Vacío = proxy Vite /api/activos → :8016.
 */

const BASE = (import.meta.env.VITE_ACTIVOS_API_URL ?? "").replace(/\/$/, "");
const TIMEOUT_MS = 120_000;

export const DIAS_FUERA_ALERTA = 30;
export const DIAS_FUERA_AVISO = 21;

export const SECTOR_CHART_COLORS = [
  "#185FA5",
  "#3B6D11",
  "#854F0B",
  "#A32D2D",
  "#5B4FCF",
];

export type ActivoItem = {
  id: string;
  codigo: string;
  equipo: string;
  sector: string;
  dias_fuera: number;
  cantidad: number;
  estado: string;
  proveedor: string;
  remito: string;
  n_pedido?: string;
  n_oc?: string;
  nro_serie?: string;
  fecha_salida?: string;
  fecha_regreso?: string;
  estado_al_ingreso?: string;
  observaciones?: string;
  fingerprint?: string;
};

export type CrearSalidaPayload = {
  equipo: string;
  sector: string;
  proveedor: string;
  numero_remito: string;
  codigo?: string;
  nro_serie?: string;
  numero_pedido?: string;
  numero_oc?: string;
  cantidad?: number;
  fecha_salida?: string;
  observaciones?: string;
};

export type EditarActivoPayload = {
  equipo?: string;
  sector?: string;
  proveedor?: string;
  numero_remito?: string;
  codigo?: string;
  nro_serie?: string;
  numero_pedido?: string;
  numero_oc?: string;
  cantidad?: number;
  fecha_salida?: string;
  observaciones?: string;
};

export type CrearSalidaResult = {
  mensaje: string;
  id: number;
};

export type MarcarRegresoResult = {
  mensaje: string;
  movidos: number;
  no_encontrados: string[];
  fecha_regreso: string;
  estado_al_ingreso: string;
};

export type ActivosResumen = {
  fuera_de_planta: number;
  ingresados: number;
  dias_promedio_fuera: number;
  criticos: number;
  por_sector: { sector: string; cantidad: number }[];
  sectores: string[];
  lista_fuera: ActivoItem[];
  lista_ingresados: ActivoItem[];
  ultima_actualizacion: string;
};

async function fetchJson<T>(path: string, init?: RequestInit, token?: string): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(`${BASE}${path}`, {
      ...init,
      signal: ctrl.signal,
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(init?.headers ?? {}),
      },
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = typeof data.detail === "string" ? data.detail : `Error ${res.status}`;
      if (res.status === 503) {
        throw new Error(`${detail} (servicio iniciando o Excel en carga — espere y reintente).`);
      }
      throw new Error(detail);
    }
    return data as T;
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") {
      throw new Error("Tiempo de espera agotado al contactar el servicio Activos.");
    }
    if (e instanceof TypeError) {
      throw new Error(
        "No se pudo conectar con el servicio Activos (:8016). Verificá que esté levantado (PortalPanol o _start_activos.bat).",
      );
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

export function fmtNum(n: number): string {
  return n.toLocaleString("es-AR");
}

export function fmtFechaIso(iso: string): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("es-AR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function claseFilaDias(dias: number): string {
  if (dias > DIAS_FUERA_ALERTA) return "act-row-dias-critico";
  if (dias > DIAS_FUERA_AVISO) return "act-row-dias-aviso";
  return "act-row-dias-ok";
}

export function claseBadgeDias(dias: number): string {
  if (dias > DIAS_FUERA_ALERTA) return "act-dias-badge act-dias-critico";
  if (dias > DIAS_FUERA_AVISO) return "act-dias-badge act-dias-aviso";
  return "act-dias-badge act-dias-ok";
}

export function etiquetaSector(code: string): string {
  const m: Record<string, string> = {
    PRODUCCION: "Producción",
    PROYECTOS: "Proyectos",
    MANTENIMIENTO: "Mantenimiento",
    EDILICIO: "Edilicio",
    AUTOELEVADORES: "Autoelevadores",
  };
  return m[code] ?? code;
}

export const fetchActivosResumen = (token?: string) =>
  fetchJson<ActivosResumen>("/api/activos/resumen", undefined, token);

export const refreshActivos = (token?: string) =>
  fetchJson<{ mensaje: string; timestamp: string }>(
    "/api/activos/refresh",
    { method: "POST" },
    token,
  );

export function marcarRegreso(
  payload: {
    ids: string[];
    fecha_regreso: string;
    estado_al_ingreso: string;
  },
  token?: string,
): Promise<MarcarRegresoResult> {
  return fetchJson<MarcarRegresoResult>(
    "/api/activos/marcar-regreso",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    token,
  );
}

export function restablecerFuera(
  ids: string[],
  token?: string,
): Promise<{ mensaje: string; movidos: number }> {
  return fetchJson(
    "/api/activos/restablecer-fuera",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids }),
    },
    token,
  );
}

export function urlActivosExcel(vista: "fuera" | "ingresados" = "fuera"): string {
  return `${BASE}/api/activos/export.xlsx?vista=${vista}`;
}

export function urlActivosPdf(vista: "fuera" | "ingresados" = "fuera"): string {
  return `${BASE}/api/activos/export.pdf?vista=${vista}`;
}

/** Hoy en YYYY-MM-DD para input type=date */
export function hoyIsoLocal(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function crearSalida(
  payload: CrearSalidaPayload,
  token?: string,
): Promise<CrearSalidaResult> {
  return fetchJson<CrearSalidaResult>(
    "/api/activos/salida",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    token,
  );
}

export function editarActivo(
  id: number,
  payload: EditarActivoPayload,
  token?: string,
): Promise<{ mensaje: string }> {
  return fetchJson<{ mensaje: string }>(
    `/api/activos/${id}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    token,
  );
}
