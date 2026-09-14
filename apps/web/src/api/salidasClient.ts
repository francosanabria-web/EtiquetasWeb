/**
 * Cliente del servicio Salidas (:8018).
 * Vacío = proxy Vite /api/salidas → :8018.
 */

const BASE = (import.meta.env.VITE_SALIDAS_API_URL ?? "").replace(/\/$/, "");
const TIMEOUT_MS = 60_000;

export type ArticuloSalida = {
  codigo: string;
  descripcion: string;
  ubicacion: string;
  stock_actual: number;
  precio_unitario: number;
  categoria: string;
  hoja?: string;
};

export type CatalogosSalidas = {
  tipos_comprobante: string[];
  sectores: string[];
  operarios: string[];
  operarios_proyectos: string[];
  sector_operarios: Record<string, string[]>;
  ultima_actualizacion?: string;
};

export type ItemPendiente = {
  id: string;
  fecha: string;
  codigo: string;
  descripcion: string;
  ubicacion: string;
  cantidad: number;
  tipo_comprobante: string;
  numero_orden: string | number;
  maquina: string;
  precio_unitario: number;
  monto: number;
  operario: string;
  sector: string;
  es_devolucion: boolean;
};

export type ProyeccionStock = {
  codigo: string;
  descripcion: string;
  ubicacion: string;
  precio_unitario: number;
  stock_actual: number;
  stock_base_con_pendientes: number;
  cantidad: number;
  stock_proyectado: number;
  alerta_negativo: boolean;
  es_devolucion: boolean;
};

export type ConfirmarResult = {
  mensaje: string;
  movimientos: number;
  archivos: string[];
  firebase_escritos: number;
  filas: Record<string, unknown>[];
  ultima_actualizacion: string;
};

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(`${BASE}${path}`, { ...init, signal: ctrl.signal });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = typeof data.detail === "string" ? data.detail : `Error ${res.status}`;
      if (res.status === 503) {
        throw new Error(`${detail} (servicio iniciando — espere y reintente).`);
      }
      throw new Error(detail);
    }
    return data as T;
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") {
      throw new Error("Tiempo de espera agotado al contactar Salidas.");
    }
    if (e instanceof TypeError) {
      throw new Error(
        "No se pudo conectar con Salidas (:8018). Verificá _start_salidas.bat o PortalPanol.",
      );
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

export function hoyIsoLocal(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function fmtNum(n: number): string {
  return n.toLocaleString("es-AR", { maximumFractionDigits: 2 });
}

export function fmtPesos(n: number): string {
  return n.toLocaleString("es-AR", {
    style: "currency",
    currency: "ARS",
    maximumFractionDigits: 2,
  });
}

export const fetchSalidasHealth = () =>
  fetchJson<{ estado: string; path?: string; firebase?: Record<string, unknown> }>(
    "/api/salidas/health",
  );

export const fetchCatalogosSalidas = () =>
  fetchJson<CatalogosSalidas>("/api/salidas/catalogos");

export const fetchArticulo = (codigo: string) =>
  fetchJson<ArticuloSalida>(`/api/salidas/articulo/${encodeURIComponent(codigo.trim())}`);

export function proyectarStock(payload: {
  codigo: string;
  cantidad: number;
  es_devolucion?: boolean;
  pendientes?: { codigo: string; cantidad: number }[];
}): Promise<ProyeccionStock> {
  return fetchJson("/api/salidas/proyectar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function confirmarSalida(payload: {
  items: Record<string, unknown>[];
  forzar_negativos?: boolean;
}): Promise<ConfirmarResult> {
  return fetchJson("/api/salidas/confirmar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function confirmarDevolucion(payload: {
  items: Record<string, unknown>[];
}): Promise<ConfirmarResult> {
  return fetchJson("/api/salidas/devolucion", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function operariosParaSector(
  cats: CatalogosSalidas | null,
  sector: string,
): string[] {
  if (!cats) return [];
  const key = sector.trim().toUpperCase();
  const mapped = cats.sector_operarios?.[key];
  if (mapped && mapped.length) return mapped;
  if (key === "PROYECTOS" && cats.operarios_proyectos?.length) {
    return cats.operarios_proyectos;
  }
  return cats.operarios || [];
}
