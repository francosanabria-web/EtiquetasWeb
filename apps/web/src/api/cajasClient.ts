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
  herramienta_descripcion?: string;
  descripcion?: string;
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

export async function createInventario(token: string, data: Omit<Inventario, "id" | "detalle"> & { detalle: Array<Omit<InventarioDetalle, "id">> }): Promise<Inventario> {
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

// ---------------------------------------------------------------------------
// Caja Ideal (versionado) — Slice 1 & 2
// ---------------------------------------------------------------------------

export type IdealHerramienta = {
  id: number;
  herramienta_id: number;
  codigo: string;
  descripcion: string | null;
  cantidad_minima: number;
  articulo_codigo: string | null;
};

export type Ideal = {
  id: number | null;
  nombre: string | null;
  descripcion: string | null;
  activa: boolean;
  vigente_desde: string | null;
  creado_por: number | null;
  creado_en: string | null;
  herramientas: IdealHerramienta[];
  mensaje?: string | null;
  hint?: string | null;
};

export type IdealVersionesItem = {
  id: number;
  nombre: string;
  descripcion: string | null;
  activa: boolean;
  vigente_desde: string | null;
  creado_por: number | null;
  creado_en: string | null;
};

export type IdealVersionesResponse = {
  items: IdealVersionesItem[];
  total: number;
};

export type TecnicoCard = {
  tecnico_id: number;
  tecnico_nombre: string;
  tecnico_tipo: string;
  caja_id: number | null;
  caja_codigo: string | null;
  ultimo_periodo: string | null;
  ultimo_estado: "borrador" | "cerrado" | null;
  ideal_count: number;
  presente_count: number;
  faltantes_pct: number | null;
  completitud_pct: number;
  limpieza_score: number;
};

export type TecnicoCardsResponse = {
  items: TecnicoCard[];
  total: number;
};

export type TecnicoInventarioDetalle = {
  id: number;
  herramienta_id: number;
  herramienta_codigo: string;
  nro_item: number;
  cantidad: number;
  estado: "bueno" | "regular" | "malo";
  presente: boolean;
  observaciones: string | null;
};

export type TecnicoInventario = {
  id: number;
  caja_id: number;
  caja_codigo: string | null;
  fecha: string | null;
  periodo: string;
  tecnico_id: number;
  tecnico_nombre: string | null;
  supervisor_id: number;
  supervisor_nombre: string | null;
  area: string | null;
  estado: "borrador" | "cerrado";
  obs: string | null;
  obs_generales: string | null;
  detalle: TecnicoInventarioDetalle[];
};

export type TecnicoHistorialResponse = {
  items: TecnicoInventario[];
  total: number;
};

export type KpisResumenTecnico = {
  tecnico_id: number;
  tecnico_nombre: string;
  tecnico_tipo: string;
  caja_codigo: string | null;
  ultimo_periodo: string | null;
  ultimo_estado: string | null;
  ideal_count: number;
  presente_count: number;
  faltantes_pct: number | null;
  completitud_pct: number | null;
  limpieza_score: number;
};

export type KpisResumenGlobal = {
  ideal_count: number;
  total_tecnicos: number;
  tecnicos_con_inventario: number;
  tecnicos_sin_inventario: number;
  promedio_faltantes_pct: number;
  promedio_completitud_pct: number;
  avg_faltantes_pct: number;
  avg_completitud_pct: number;
  avg_limpieza_score: number;
  distribucion_faltantes?: Record<string, number>;
  distribucion?: Record<string, number>;
};

export type KpisResumen = {
  ideal_count: number;
  total_tecnicos: number;
  tecnicos_con_inventario: number;
  tecnicos_sin_inventario: number;
  avg_faltantes_pct: number;
  avg_completitud_pct: number;
  avg_limpieza_score: number;
  promedio_faltantes_pct: number;
  promedio_completitud_pct: number;
  distribucion_faltantes: Record<string, number>;
  distribucion: Record<string, number>;
  tecnicos: KpisResumenTecnico[];
  items: KpisResumenTecnico[];
  total: number;
  global: KpisResumenGlobal;
  mensaje: string | null;
  hint: string | null;
};

export type KpisPorTecnicoHistorialEntry = {
  inventario_id: number;
  periodo: string | null;
  estado: string | null;
  caja_id: number | null;
  caja_codigo: string | null;
  presente_count: number;
  total_detalle: number;
  faltantes_pct: number | null;
  completitud_pct: number | null;
  limpieza_score: number;
  mal_count: number;
  malos: number;
};

export type KpisPorTecnico = {
  tecnico_id: number;
  tecnico_nombre: string;
  tecnico_tipo: string;
  ideal_count: number;
  presente_count: number;
  faltantes_pct: number | null;
  completitud_pct: number | null;
  limpieza_score: number;
  ultimo_periodo: string | null;
  ultimo_estado: string | null;
  historial: KpisPorTecnicoHistorialEntry[];
  historial_faltantes: KpisPorTecnicoHistorialEntry[];
  total_inventarios: number;
  total: number;
  mensaje: string | null;
  hint: string | null;
};

export type PutIdealPayload = {
  nombre: string;
  descripcion?: string | null;
  detalle: Array<{
    herramienta_codigo: string;
    cantidad_minima: number;
    articulo_codigo?: string | null;
  }>;
};

export async function getIdeal(token: string): Promise<Ideal> {
  const data = await fetchJson<Ideal>("/api/cajas/ideal", {}, token);
  // Normalize: ensure herramientas array present
  if (!Array.isArray(data.herramientas)) {
    return { ...data, herramientas: [] };
  }
  return data;
}

export async function putIdeal(token: string, payload: PutIdealPayload): Promise<Ideal> {
  const data = await fetchJson<Ideal>("/api/cajas/ideal", {
    method: "PUT",
    body: JSON.stringify(payload),
  }, token);
  if (!Array.isArray(data.herramientas)) {
    return { ...data, herramientas: [] };
  }
  return data;
}

export async function getIdealVersiones(
  token: string,
  params?: { limit?: number; offset?: number },
): Promise<IdealVersionesResponse> {
  const searchParams = new URLSearchParams();
  if (params?.limit != null) searchParams.set("limit", String(params.limit));
  if (params?.offset != null) searchParams.set("offset", String(params.offset));
  const qs = searchParams.toString();
  const path = qs ? `/api/cajas/ideal/versiones?${qs}` : "/api/cajas/ideal/versiones";
  const data = await fetchJson<{ items: IdealVersionesItem[]; total: number }>(path, {}, token);
  return { items: data.items ?? [], total: data.total ?? 0 };
}

export async function getTecnicosCards(
  token: string,
  params?: { limit?: number; offset?: number; q?: string; con_inventario?: boolean },
): Promise<TecnicoCardsResponse> {
  const searchParams = new URLSearchParams();
  if (params?.limit != null) searchParams.set("limit", String(params.limit));
  if (params?.offset != null) searchParams.set("offset", String(params.offset));
  if (params?.q) searchParams.set("q", params.q);
  if (params?.con_inventario !== undefined) searchParams.set("con_inventario", params.con_inventario ? "true" : "false");
  const qs = searchParams.toString();
  const path = qs ? `/api/cajas/tecnicos-cards?${qs}` : "/api/cajas/tecnicos-cards";
  const data = await fetchJson<{ items: TecnicoCard[]; total: number }>(path, {}, token);
  return { items: data.items ?? [], total: data.total ?? 0 };
}

export type RecomendacionCodigo = {
  codigo: string;
  descripcion: string;
  alias: string | null;
  score: number;
};

export async function recomendarCodigo(
  token: string,
  descripcion: string,
  limit = 5,
): Promise<{ items: RecomendacionCodigo[]; total: number; query: string }> {
  const sp = new URLSearchParams({ descripcion, limit: String(limit) });
  const path = `/api/cajas/herramientas/recomendar-codigo?${sp.toString()}`;
  const data = await fetchJson<{ items: RecomendacionCodigo[]; total: number; query: string }>(path, {}, token);
  return data;
}

export async function getTecnicoHistorial(
  token: string,
  tecnicoId: number,
  params?: { limit?: number; offset?: number; estado?: string },
): Promise<TecnicoHistorialResponse> {
  const searchParams = new URLSearchParams();
  if (params?.limit != null) searchParams.set("limit", String(params.limit));
  if (params?.offset != null) searchParams.set("offset", String(params.offset));
  if (params?.estado) searchParams.set("estado", params.estado);
  const qs = searchParams.toString();
  const base = `/api/cajas/tecnicos/${tecnicoId}/inventarios`;
  const path = qs ? `${base}?${qs}` : base;
  const data = await fetchJson<{ items: TecnicoInventario[]; total: number }>(path, {}, token);
  // Backend may return array directly in some handlers; normalize
  if (Array.isArray(data as unknown as TecnicoInventario[])) {
    const arr = data as unknown as TecnicoInventario[];
    return { items: arr, total: arr.length };
  }
  return { items: (data as { items: TecnicoInventario[] }).items ?? [], total: (data as { total: number }).total ?? 0 };
}

export async function getKpisResumen(
  token: string,
  params?: { q?: string; limit?: number; offset?: number },
): Promise<KpisResumen> {
  const searchParams = new URLSearchParams();
  if (params?.q) searchParams.set("q", params.q);
  if (params?.limit != null) searchParams.set("limit", String(params.limit));
  if (params?.offset != null) searchParams.set("offset", String(params.offset));
  const qs = searchParams.toString();
  const path = qs ? `/api/cajas/kpis/resumen?${qs}` : "/api/cajas/kpis/resumen";
  const data = await fetchJson<KpisResumen>(path, {}, token);
  return data;
}

export async function getKpisPorTecnico(token: string, tecnicoId: number): Promise<KpisPorTecnico> {
  const data = await fetchJson<KpisPorTecnico>(`/api/cajas/kpis/tecnico/${tecnicoId}`, {}, token);
  return data;
}

// ---------------------------------------------------------------------------
// Limpieza & Asignaciones (Fase 2) — client for /api/cajas/limpieza & /asignaciones

export type LimpiezaEvento = {
  id: number;
  caja_id: number;
  caja_codigo: string | null;
  tecnico_id: number;
  tecnico_nombre: string | null;
  fecha: string | null;
  estado: "pendiente" | "realizada" | "vencida";
  responsable_id: number | null;
  observaciones: string | null;
  creado_en: string | null;
};

export type LimpiezaListResponse = {
  items: LimpiezaEvento[];
  total: number;
};

export type Asignacion = {
  id: number;
  caja_id: number;
  caja_codigo: string | null;
  tecnico_id: number;
  tecnico_nombre: string | null;
  desde: string | null;
  hasta: string | null;
  activa: boolean;
  creado_en: string | null;
};

export type AsignacionListResponse = {
  items: Asignacion[];
  total: number;
};

export async function getLimpieza(
  token: string,
  params?: { caja_id?: number; tecnico_id?: number; estado?: string; limit?: number; offset?: number },
): Promise<LimpiezaListResponse> {
  const sp = new URLSearchParams();
  if (params?.caja_id != null) sp.set("caja_id", String(params.caja_id));
  if (params?.tecnico_id != null) sp.set("tecnico_id", String(params.tecnico_id));
  if (params?.estado) sp.set("estado", params.estado);
  if (params?.limit != null) sp.set("limit", String(params.limit));
  if (params?.offset != null) sp.set("offset", String(params.offset));
  const qs = sp.toString();
  const path = qs ? `/api/cajas/limpieza?${qs}` : "/api/cajas/limpieza";
  const data = await fetchJson<{ items: LimpiezaEvento[]; total: number }>(path, {}, token);
  return { items: data.items ?? [], total: data.total ?? 0 };
}

export async function createLimpieza(
  token: string,
  payload: { caja_id: number; tecnico_id: number; estado?: string; responsable_id?: number | null; observaciones?: string | null; fecha?: string | null },
): Promise<LimpiezaEvento> {
  const data = await fetchJson<LimpiezaEvento>("/api/cajas/limpieza", { method: "POST", body: JSON.stringify(payload) }, token);
  return data;
}

export async function updateLimpiezaEstado(
  token: string,
  id: number,
  payload: { estado?: string; observaciones?: string | null },
): Promise<LimpiezaEvento> {
  const data = await fetchJson<LimpiezaEvento>(`/api/cajas/limpieza/${id}/estado`, { method: "PATCH", body: JSON.stringify(payload) }, token);
  return data;
}

export async function deleteLimpieza(token: string, id: number): Promise<void> {
  await fetchJson<{ ok: boolean }>(`/api/cajas/limpieza/${id}`, { method: "DELETE" }, token);
}

export async function getAsignaciones(
  token: string,
  params?: { caja_id?: number; tecnico_id?: number; activa?: boolean | number | string; limit?: number; offset?: number },
): Promise<AsignacionListResponse> {
  const sp = new URLSearchParams();
  if (params?.caja_id != null) sp.set("caja_id", String(params.caja_id));
  if (params?.tecnico_id != null) sp.set("tecnico_id", String(params.tecnico_id));
  if (params?.activa !== undefined && params?.activa !== null && String(params.activa).trim() !== "") sp.set("activa", String(params.activa));
  if (params?.limit != null) sp.set("limit", String(params.limit));
  if (params?.offset != null) sp.set("offset", String(params.offset));
  const qs = sp.toString();
  const path = qs ? `/api/cajas/asignaciones?${qs}` : "/api/cajas/asignaciones";
  const data = await fetchJson<{ items: Asignacion[]; total: number }>(path, {}, token);
  return { items: data.items ?? [], total: data.total ?? 0 };
}

export async function createAsignacion(
  token: string,
  payload: { caja_id: number; tecnico_id: number; desde: string; hasta?: string | null },
): Promise<Asignacion> {
  const data = await fetchJson<Asignacion>("/api/cajas/asignaciones", { method: "POST", body: JSON.stringify(payload) }, token);
  return data;
}

export async function cerrarAsignacion(token: string, id: number): Promise<Asignacion> {
  const data = await fetchJson<Asignacion>(`/api/cajas/asignaciones/${id}/cerrar`, { method: "PATCH", body: JSON.stringify({}) }, token);
  return data;
}
