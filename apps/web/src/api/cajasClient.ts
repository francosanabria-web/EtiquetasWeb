/**
 * API Cajas de Herramientas (:8021).
 * Vacío = proxy Vite /api/cajas* → :8021.
 */

const BASE = (import.meta.env.VITE_CAJAS_API_URL ?? "").replace(/\/$/, "");
const TIMEOUT_MS = 15_000;

async function fetchJson<T>(path: string, init?: RequestInit, token?: string): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(`${BASE}${path}`, {
      ...init,
      signal: ctrl.signal,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(init?.headers ?? {}),
      },
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = typeof data.detail === "string" ? data.detail : `Error ${res.status}`;
      throw new Error(detail);
    }
    return data as T;
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") {
      throw new Error("Tiempo de espera agotado al contactar el servicio de cajas.");
    }
    if (e instanceof TypeError) {
      throw new Error(
        "No se pudo conectar al servicio de cajas. Verificá que esté corriendo (puerto 8021).",
      );
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

export type Caja = {
  id: number;
  codigo: string;
  descripcion: string | null;
  ubicacion: string | null;
  activa: boolean;
};

export type Herramienta = {
  id: number;
  codigo: string;
  descripcion: string | null;
  categoria: string;
  unidad: string;
  articulo_codigo: string | null;
};

export type InventarioDetalle = {
  id: number;
  herramienta_codigo: string;
  articulo_codigo: string | null;
  cantidad: number;
  presente: boolean;
  estado?: 'bueno' | 'regular' | 'malo';
  observaciones?: string;
};

export type Inventario = {
  id: number;
  caja_id: number;
  caja_codigo: string;
  tecnico_id: number;
  tecnico_nombre: string;
  supervisor_id: number;
  supervisor_nombre: string;
  periodo: string; // YYYY-MM-DD (first day of month)
  estado: 'borrador' | 'cerrado';
  obs: string | null;
  area: string | null;
  detalle: InventarioDetalle[];
};

export type CajaListResponse = {
  items: Caja[];
  total: number;
};

export type HerramientaListResponse = {
  items: Herramienta[];
  total: number;
};

export type InventarioListResponse = {
  items: Inventario[];
  total: number;
};

export type CajaListParams = {
  q?: string;
  activa?: boolean;
  limit?: number;
  offset?: number;
};

export type HerramientaListParams = {
  q?: string;
  categoria?: string;
  limit?: number;
  offset?: number;
};

export async function getCajas(token: string, params?: CajaListParams): Promise<CajaListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.q) searchParams.set("q", params.q);
  if (params?.activa != null) searchParams.set("activa", String(params.activa));
  if (params?.limit) searchParams.set("limit", String(params.limit));
  if (params?.offset) searchParams.set("offset", String(params.offset));
  const qs = searchParams.toString();
  const path = qs ? `/api/cajas/cajas?${qs}` : "/api/cajas/cajas";
  const data = await fetchJson<{ items: Caja[]; total: number }>(path, {}, token);
  return { items: data.items ?? data, total: data.total ?? 0 };
}

export async function getCajaById(token: string, id: number): Promise<Caja> {
  const data = await fetchJson<Caja>(`/api/cajas/cajas/${id}`, {}, token);
  return data;
}

export async function createCaja(token: string, data: Omit<Caja, "id">): Promise<Caja> {
  const payload = {
    codigo: data.codigo,
    descripcion: data.descripcion ?? null,
    ubicacion: data.ubicacion ?? null,
    activa: data.activa ?? true,
  };
  const result = await fetchJson<Caja>("/api/cajas/cajas", {
    method: "POST",
    body: JSON.stringify(payload),
  }, token);
  return result;
}

export async function updateCaja(token: string, id: number, data: Partial<Omit<Caja, "id">>): Promise<Caja> {
  const payload: Record<string, unknown> = {};
  if (data.codigo !== undefined) payload.codigo = data.codigo;
  if (data.descripcion !== undefined) payload.descripcion = data.descripcion ?? null;
  if (data.ubicacion !== undefined) payload.ubicacion = data.ubicacion ?? null;
  if (data.activa !== undefined) payload.activa = data.activa;
  const result = await fetchJson<Caja>(`/api/cajas/cajas/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  }, token);
  return result;
}

export async function deleteCaja(token: string, id: number): Promise<void> {
  await fetchJson<{ ok: boolean }>(`/api/cajas/cajas/${id}`, { method: "DELETE" }, token);
}

export async function getHerramientas(token: string, params?: HerramientaListParams): Promise<HerramientaListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.q) searchParams.set("q", params.q);
  if (params?.categoria) searchParams.set("categoria", params.categoria);
  if (params?.limit) searchParams.set("limit", String(params.limit));
  if (params?.offset) searchParams.set("offset", String(params.offset));
  const qs = searchParams.toString();
  const path = qs ? `/api/cajas/herramientas?${qs}` : "/api/cajas/herramientas";
  const data = await fetchJson<{ items: Herramienta[]; total: number }>(path, {}, token);
  return { items: data.items ?? data, total: data.total ?? 0 };
}

export async function getHerramientaById(token: string, id: number): Promise<Herramienta> {
  const data = await fetchJson<Herramienta>(`/api/cajas/herramientas/${id}`, {}, token);
  return data;
}

export async function createHerramienta(token: string, data: Omit<Herramienta, "id">): Promise<Herramienta> {
  const payload = {
    codigo: data.codigo,
    descripcion: data.descripcion ?? null,
    categoria: data.categoria,
    unidad: data.unidad,
    articulo_codigo: data.articulo_codigo ?? null,
  };
  const result = await fetchJson<Herramienta>("/api/cajas/herramientas", {
    method: "POST",
    body: JSON.stringify(payload),
  }, token);
  return result;
}

export async function updateHerramienta(token: string, id: number, data: Partial<Omit<Herramienta, "id">>): Promise<Herramienta> {
  const payload: Record<string, unknown> = {};
  if (data.codigo !== undefined) payload.codigo = data.codigo;
  if (data.descripcion !== undefined) payload.descripcion = data.descripcion ?? null;
  if (data.categoria !== undefined) payload.categoria = data.categoria;
  if (data.unidad !== undefined) payload.unidad = data.unidad;
  if (data.articulo_codigo !== undefined) payload.articulo_codigo = data.articulo_codigo ?? null;
  const result = await fetchJson<Herramienta>(`/api/cajas/herramientas/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  }, token);
  return result;
}

export async function deleteHerramienta(token: string, id: number): Promise<void> {
  await fetchJson<{ ok: boolean }>(`/api/cajas/herramientas/${id}`, { method: "DELETE" }, token);
}

export async function getHealth(): Promise<{ status: string; service: string }> {
  const data = await fetchJson<{ status: string; service: string }>("/health", {});
  return data;
}

export async function getInventarios(token: string, params?: {
  caja_id?: number; periodo?: string; estado?: string; q?: string; limit?: number; offset?: number;
}): Promise<InventarioListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.caja_id != null) searchParams.set("caja_id", String(params.caja_id));
  if (params?.periodo) searchParams.set("periodo", params.periodo);
  if (params?.estado) searchParams.set("estado", params.estado);
  if (params?.q) searchParams.set("q", params.q);
  if (params?.limit) searchParams.set("limit", String(params.limit));
  if (params?.offset) searchParams.set("offset", String(params.offset));
  const qs = searchParams.toString();
  const path = qs ? `/api/cajas/inventarios?${qs}` : "/api/cajas/inventarios";
  const data = await fetchJson<{ items: Inventario[]; total: number }>(path, {}, token);
  return { items: data.items ?? data, total: data.total ?? 0 };
}

export async function getInventarioById(token: string, id: number): Promise<Inventario> {
  const data = await fetchJson<Inventario>(`/api/cajas/inventarios/${id}`, {}, token);
  return data;
}

export async function createInventario(token: string, data: Omit<Inventario, "id" | "detalle"> & { detalle: Array<Omit<InventarioDetalle, "id">>>): Promise<Inventario> {
  const payload = { ...data };
  const result = await fetchJson<Inventario>("/api/cajas/inventarios", {
    method: "POST", body: JSON.stringify(payload),
  }, token);
  return result;
}

export async function updateInventarioEstado(token: string, id: number, estado: 'borrador' | 'cerrado'): Promise<{ estado: string }> {
  const result = await fetchJson<{ estado: string }>(`/api/cajas/inventarios/${id}/estado`, {
    method: "PATCH", body: JSON.stringify({ estado }),
  }, token);
  return result;
}

export async function deleteInventario(token: string, id: number): Promise<void> {
  await fetchJson<{ ok: boolean }>(`/api/cajas/inventarios/${id}`, { method: "DELETE" }, token);
}
