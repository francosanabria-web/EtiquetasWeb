/**
 * Cliente del servicio Salidas (:8018).
 * Vacío = proxy Vite /api/salidas → :8018.
 * v4 volantazo 2026-09-16: simplificado, conecta DB directo.
 */

const BASE = (import.meta.env.VITE_SALIDAS_API_URL ?? "").replace(/\/$/, "");
const TIMEOUT_MS = 60_000;

export type ArticuloSalida = {
  codigo: string;
  descripcion: string;
  alias?: string | null;
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
  fetchJson<{
    estado: string;
    path?: string;
    path_escritura?: string;
    path_historial?: string;
    maestro_writable?: boolean;
    db_enabled?: boolean;
    excel_backup?: boolean;
    firebase?: Record<string, unknown>;
  }>("/api/salidas/health");

export const fetchCatalogosSalidas = () =>
  fetchJson<CatalogosSalidas>("/api/salidas/catalogos");

export const fetchArticulo = (codigo: string) =>
  fetchJson<ArticuloSalida>(`/api/salidas/articulo/${encodeURIComponent(codigo.trim())}`);

/** Buscar en maestro para modal "Maestro de stock" - ahora incluye alias (F3) */
export function buscarArticulos(params: { q?: string; limite?: number }): Promise<{ total: number; items: ArticuloSalida[]; q: string }> {
  const sp = new URLSearchParams();
  if (params.q) sp.set("q", params.q);
  if (params.limite) sp.set("limite", String(params.limite));
  const qs = sp.toString();
  return fetchJson(`/api/salidas/articulos${qs ? `?${qs}` : ""}`);
}

// Alias bidirectional sync DB <-> Firestore
function getStoredTokenForAlias(): string | null {
  try {
    const raw = localStorage.getItem("panol_shell_session");
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { token?: string };
    return typeof parsed.token === "string" ? parsed.token : null;
  } catch {
    return null;
  }
}

export function actualizarAlias(codigo: string, alias: string | null, token?: string): Promise<ArticuloSalida> {
  const tok = token ?? getStoredTokenForAlias();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (tok) headers["Authorization"] = `Bearer ${tok}`;
  return fetchJson<ArticuloSalida>(`/api/maestro-stock/${encodeURIComponent(codigo.trim().toUpperCase())}/alias`, {
    method: "PUT",
    headers,
    body: JSON.stringify({ alias }),
  });
}

export function syncAliasMaestro(params?: { direction?: "push" | "pull" | "both"; limit?: number }, token?: string): Promise<{ direction: string; push?: unknown; pull?: unknown }> {
  const tok = token ?? getStoredTokenForAlias();
  const headers: Record<string, string> = {};
  if (tok) headers["Authorization"] = `Bearer ${tok}`;
  const sp = new URLSearchParams();
  if (params?.direction) sp.set("direction", params.direction);
  if (params?.limit) sp.set("limit", String(params.limit));
  const qs = sp.toString();
  return fetchJson(`/api/maestro-stock/sync-alias${qs ? `?${qs}` : ""}`, {
    method: "POST",
    headers,
  });
}

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

// Mantener por compat backend pero NO exponer en UI v4 (se quita boton devolucion)
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

// ---------- Atenciones ventanilla v4 simplificada ----------

export type AtencionPayload = {
  fecha?: string;
  con_retiro: boolean;
  observaciones?: string | null;
  atendido_por?: string | null;
};

export type AtencionRow = {
  id: number;
  fecha: string;
  con_retiro: number | boolean;
  observaciones?: string | null;
  atendido_por?: string | null;
  atendido_en?: string | null;
  creado_en?: string | null;
  actualizado_en?: string | null;
  // legacy compat opcional
  hora?: string | null;
  persona_solicitante?: string | null;
  sector_nombre?: string | null;
  motivo_sin_retiro?: string | null;
};

export type AtencionesListResult = {
  total: number;
  items: AtencionRow[];
  limite?: number;
};

export type AtencionesKpi = {
  kpi_mensual: Array<{
    periodo: string;
    total: number;
    con_retiro: number;
    sin_retiro: number;
    pct_con_retiro: number | null;
  }>;
  por_dia?: Array<{
    fecha: string;
    total: number;
    con_retiro: number;
    sin_retiro: number;
    pct_con_retiro: number | null;
  }>;
  resumen?: {
    periodo?: string;
    total: number;
    con_retiro: number;
    sin_retiro: number;
    pct_con_retiro: number | null;
  };
};

export function crearAtencion(payload: AtencionPayload): Promise<{ mensaje: string; id: number }> {
  return fetchJson("/api/salidas/atenciones", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function listarAtenciones(params: {
  desde?: string;
  hasta?: string;
  con_retiro?: string | boolean;
  q?: string;
  limite?: number;
}): Promise<AtencionesListResult> {
  const sp = new URLSearchParams();
  if (params.desde) sp.set("desde", params.desde);
  if (params.hasta) sp.set("hasta", params.hasta);
  if (params.con_retiro !== undefined && params.con_retiro !== null && String(params.con_retiro) !== "") sp.set("con_retiro", String(params.con_retiro));
  if (params.q) sp.set("q", params.q);
  if (params.limite) sp.set("limite", String(params.limite));
  const qs = sp.toString();
  return fetchJson(`/api/salidas/atenciones${qs ? `?${qs}` : ""}`);
}

export function kpiAtenciones(params?: { periodo?: string; desde?: string; hasta?: string }): Promise<AtencionesKpi> {
  const sp = new URLSearchParams();
  if (params?.periodo) sp.set("periodo", params.periodo);
  if (params?.desde) sp.set("desde", params.desde);
  if (params?.hasta) sp.set("hasta", params.hasta);
  const qs = sp.toString();
  return fetchJson(`/api/salidas/atenciones/kpi${qs ? `?${qs}` : ""}`);
}

export async function exportarAtenciones(params: {
  desde?: string;
  hasta?: string;
  formato?: "xlsx" | "csv";
}): Promise<Blob> {
  const sp = new URLSearchParams();
  if (params.desde) sp.set("desde", params.desde);
  if (params.hasta) sp.set("hasta", params.hasta);
  sp.set("formato", params.formato || "xlsx");
  const res = await fetch(`${BASE}/api/salidas/atenciones/export?${sp.toString()}`);
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    const detail = typeof (data as { detail?: string }).detail === "string" ? (data as { detail: string }).detail : `Error ${res.status}`;
    throw new Error(detail);
  }
  return await res.blob();
}

export async function exportarDiario(fecha: string): Promise<Blob> {
  const res = await fetch(`${BASE}/api/salidas/diario/export?fecha=${encodeURIComponent(fecha)}`);
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    const detail = typeof (data as { detail?: string }).detail === "string" ? (data as { detail: string }).detail : `Error ${res.status}`;
    throw new Error(detail);
  }
  return await res.blob();
}

export type ResumenDiarioLinea = {
  codigo: string;
  descripcion: string;
  cantidad: number;
  monto: number;
  tipo_comprobante: string;
  numero_orden: string;
  operario: string;
  sector: string;
  maquina: string;
  fecha: string;
};

export type ResumenDiarioGroup = {
  linea: string;
  total: number;
  cantidad: number;
  items: ResumenDiarioLinea[];
};

export type ResumenDiarioResult = {
  fecha: string;
  grupos: ResumenDiarioGroup[];
  total_general: number;
  mensaje: string;
};

export async function fetchResumenDiario(fecha: string): Promise<ResumenDiarioResult> {
  const sp = new URLSearchParams();
  sp.set("fecha", fecha);
  const res = await fetch(`${BASE}/api/salidas/resumen-diario?${sp.toString()}`);
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    const detail = typeof (data as { detail?: string }).detail === "string" ? (data as { detail: string }).detail : `Error ${res.status}`;
    throw new Error(detail);
  }
  return await res.json();
}

// ---------- Historial / Movimientos con filtros v4 ----------

export type MovimientoRow = {
  FECHA: string;
  MES?: string;
  "AÑO"?: number;
  CODIGO: string;
  DESCRIPCION: string;
  UBICACION: string;
  CANTIDAD: number;
  TIPO_COMPROBANTE: string;
  NUMERO_ORDEN: string | number;
  MAQUINA_SITIO: string;
  PRECIO_UNITARIO: number;
  MONTO_TOTAL_SALIDA: number;
  OPERARIO: string;
  SECTOR: string;
  es_devolucion?: boolean;
  id?: number;
  creado_en?: string;
  // v5 audit soft-delete
  anulado?: number | boolean;
  anulado_por?: string | null;
  anulado_en?: string | null;
  motivo_anulacion?: string | null;
  editado_en?: string | null;
  editado_por?: string | null;
};

export type MovimientosListResult = {
  total: number;
  items: MovimientoRow[];
  columnas?: string[];
};

export function listarMovimientos(params: {
  desde?: string;
  hasta?: string;
  q?: string;
  codigo?: string;
  sector?: string;
  numero_orden?: string;
  limite?: number;
  incluir_anulados?: boolean;
}): Promise<MovimientosListResult> {
  const sp = new URLSearchParams();
  if (params.desde) sp.set("desde", params.desde);
  if (params.hasta) sp.set("hasta", params.hasta);
  if (params.q) sp.set("q", params.q);
  if (params.codigo) sp.set("codigo", params.codigo);
  if (params.sector) sp.set("sector", params.sector);
  if (params.numero_orden) sp.set("numero_orden", params.numero_orden);
  if (params.limite) sp.set("limite", String(params.limite));
  if (params.incluir_anulados) sp.set("incluir_anulados", "1");
  const qs = sp.toString();
  return fetchJson(`/api/salidas/movimientos${qs ? `?${qs}` : ""}`);
}

// alias historial
export const listarHistorial = listarMovimientos;

// ---------- v5 soft-delete / edit auditoria ----------

export type AuditoriaRow = {
  id: number;
  historial_id: number;
  accion: "anular" | "editar" | "crear";
  datos_before?: string | Record<string, unknown> | null;
  datos_after?: string | Record<string, unknown> | null;
  realizado_por?: string | null;
  realizado_en: string;
  motivo?: string | null;
};

export type AuditoriaResult = {
  total: number;
  items: AuditoriaRow[];
  historial_id?: number;
};

export function anularMovimiento(id: number, motivo: string): Promise<{ mensaje: string; id: number; movimiento: MovimientoRow }> {
  return fetchJson(`/api/salidas/movimientos/${id}`, {
    method: "DELETE",
    headers: authHeaders(),
    body: JSON.stringify({ motivo }),
  });
}

export function editarMovimiento(
  id: number,
  cambios: Partial<Pick<MovimientoRow, "TIPO_COMPROBANTE" | "NUMERO_ORDEN" | "MAQUINA_SITIO" | "SECTOR" | "OPERARIO" | "CANTIDAD" | "PRECIO_UNITARIO" | "FECHA"> & {
    tipo_comprobante?: string;
    numero_orden?: string | number;
    maquina_sitio?: string;
    sector_nombre?: string;
    operario_nombre?: string;
    cantidad?: number;
    precio_unitario?: number;
    fecha?: string;
    motivo?: string | null;
  }>,
): Promise<{ mensaje: string; id: number; movimiento: MovimientoRow }> {
  // normalizar keys a snake_case esperados por backend
  const payload: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(cambios)) {
    if (v === undefined) continue;
    const lk = k.toLowerCase();
    if (lk === "tipo_comprobante" || lk === "tipo comprobante" || lk === "t_comprobante") payload["tipo_comprobante"] = v;
    else if (lk === "numero_orden" || lk === "numero orden" || lk === "n_orden") payload["numero_orden"] = v;
    else if (lk === "maquina_sitio" || lk === "maquina sitio" || lk === "maquina") payload["maquina_sitio"] = v;
    else if (lk === "sector" || lk === "sector_nombre") payload["sector_nombre"] = v;
    else if (lk === "operario" || lk === "operario_nombre") payload["operario_nombre"] = v;
    else if (lk === "cantidad") payload["cantidad"] = v;
    else if (lk === "precio_unitario" || lk === "precio unitario" || lk === "precio_unitario".toLowerCase()) payload["precio_unitario"] = v;
    else if (lk === "fecha" || lk === "fecha_salida" || lk === "fecha") payload["fecha"] = v;
    else if (lk === "motivo" || lk === "motivo_edicion") payload["motivo"] = v;
    else payload[k] = v;
  }
  return fetchJson(`/api/salidas/movimientos/${id}`, {
    method: "PUT",
    headers: authHeaders(),
    body: JSON.stringify(payload),
  });
}

export function getAuditoria(id: number): Promise<AuditoriaResult> {
  const tok = getStoredToken();
  const headers: Record<string, string> = {};
  if (tok) headers["Authorization"] = `Bearer ${tok}`;
  return fetchJson(`/api/salidas/movimientos/${id}/auditoria`, {
    headers,
  });
}

// ---------- Remito ----------

export async function exportarRemito(params: { orden: string; fecha?: string }): Promise<Blob> {
  const sp = new URLSearchParams();
  sp.set("orden", params.orden);
  if (params.fecha) sp.set("fecha", params.fecha);
  const res = await fetch(`${BASE}/api/salidas/remito/export?${sp.toString()}`);
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    const detail = typeof (data as { detail?: string }).detail === "string" ? (data as { detail: string }).detail : `Error ${res.status}`;
    throw new Error(detail);
  }
  return await res.blob();
}

// ---------- Motivos (v4: DROP - stub compat, no usar) ----------

export type MotivoRow = {
  id: number;
  clave: string;
  nombre: string;
  activo: number | boolean;
  orden: number;
  creado_en?: string | null;
};

export type MotivosListResult = {
  total: number;
  items: MotivoRow[];
};

function getStoredToken(): string | null {
  try {
    const raw = localStorage.getItem("panol_shell_session");
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { token?: string };
    return typeof parsed.token === "string" ? parsed.token : null;
  } catch {
    return null;
  }
}

function authHeaders(extra?: Record<string, string>): Record<string, string> {
  const tok = getStoredToken();
  const base: Record<string, string> = { "Content-Type": "application/json", ...(extra || {}) };
  if (tok) base["Authorization"] = `Bearer ${tok}`;
  return base;
}

// Stub: tabla DROP en v4 -> retorna vacio
export function listarMotivosAtencion(_params?: { activos_only?: boolean }): Promise<MotivosListResult> {
  return Promise.resolve({ total: 0, items: [] });
}

export function crearMotivo(_payload: { clave: string; nombre: string; orden?: number; activo?: number | boolean }): Promise<{ mensaje: string; id: number; motivo: MotivoRow }> {
  return fetchJson(`/api/salidas/atenciones/motivos`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(_payload),
  });
}

export function actualizarMotivo(_id: number, _payload: Partial<Pick<MotivoRow, "clave" | "nombre" | "orden" | "activo">>): Promise<{ mensaje: string; motivo: MotivoRow }> {
  return fetchJson(`/api/salidas/atenciones/motivos/${_id}`, {
    method: "PUT",
    headers: authHeaders(),
    body: JSON.stringify(_payload),
  });
}

export function eliminarMotivo(_id: number): Promise<{ mensaje: string; accion: string }> {
  return fetchJson(`/api/salidas/atenciones/motivos/${_id}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
}
