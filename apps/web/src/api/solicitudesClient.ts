/**
 * API Solicitud de pedidos.
 * Vacío = proxy Vite /api/solicitudes → :8014
 */
const BASE = (import.meta.env.VITE_SOLICITUDES_API_URL ?? "").replace(/\/$/, "");
const TIMEOUT_MS = 20_000;

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(`${BASE}${path}`, {
      ...init,
      signal: ctrl.signal,
      headers: {
        ...(init?.body instanceof FormData
          ? {}
          : { "Content-Type": "application/json" }),
        ...(init?.headers ?? {}),
      },
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail =
        typeof data.detail === "string" ? data.detail : `Error ${res.status}`;
      throw new Error(detail);
    }
    return data as T;
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") {
      throw new Error("Tiempo de espera agotado al contactar Solicitud de pedidos.");
    }
    if (e instanceof TypeError) {
      throw new Error(
        "No se pudo conectar al servicio de solicitudes. Ejecutá scripts\\INICIAR_TODO.bat en la PC servidor.",
      );
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

export type SolicitudTipo = "normal" | "urgente" | "tr";
export type SolicitudEstado =
  | "borrador"
  | "en_proceso"
  | "parcial"
  | "cumplido"
  | "cancelado";

export type CatalogoItem = { id: string; label: string };

export type CatalogosSolicitudes = {
  estados: CatalogoItem[];
  tipos: CatalogoItem[];
  /** Sugerencias para Área/máquina (texto libre). */
  areas: string[];
  cuentas_contables: string[];
  unidades_medida: string[];
  /** Sugerencias de proveedor (catálogo + aprendido de lo cargado). */
  proveedores: string[];
};

export type SolicitudItem = {
  id?: number;
  orden?: number;
  codigo: string;
  descripcion: string;
  cantidad: number;
  unidad: string;
  area: string;
  imagen_path: string;
};

export type Solicitud = {
  id: number;
  n_pedido: string;
  n_tr: string;
  cuenta_contable: string;
  tipo: SolicitudTipo | string;
  estado: SolicitudEstado | string;
  solicitante: string;
  proveedor: string;
  remito_nro: string;
  remito_archivo: string;
  presupuesto_nro: string;
  presupuesto_archivo: string;
  notas: string;
  creado_por: string;
  creado_en: string;
  actualizado_en: string;
  items: SolicitudItem[];
  items_count: number;
  preview: string;
  areas_resumen: string;
};

export type ResumenSolicitudes = {
  total: number;
  por_estado: Record<string, number>;
  urgentes_activos: number;
  tr_activos: number;
};

export type ItemPayload = {
  codigo?: string;
  descripcion: string;
  cantidad: number;
  unidad?: string;
  area: string;
  imagen_path?: string;
};

export type CrearSolicitudPayload = {
  n_pedido?: string;
  cuenta_contable: string;
  tipo: SolicitudTipo;
  estado?: SolicitudEstado;
  solicitante: string;
  proveedor?: string;
  remito_nro?: string;
  remito_archivo?: string;
  presupuesto_nro?: string;
  presupuesto_archivo?: string;
  notas?: string;
  creado_por?: string;
  rol?: string;
  items: ItemPayload[];
};

export async function fetchCatalogos(): Promise<CatalogosSolicitudes> {
  return fetchJson<CatalogosSolicitudes>("/api/solicitudes/catalogos");
}

export async function fetchResumen(): Promise<ResumenSolicitudes> {
  return fetchJson<ResumenSolicitudes>("/api/solicitudes/resumen");
}

export async function fetchSolicitudes(params?: {
  tipo?: string;
  estado?: string;
  q?: string;
  limite?: number;
}): Promise<Solicitud[]> {
  const sp = new URLSearchParams();
  if (params?.tipo) sp.set("tipo", params.tipo);
  if (params?.estado) sp.set("estado", params.estado);
  if (params?.q) sp.set("q", params.q);
  if (params?.limite) sp.set("limite", String(params.limite));
  const qs = sp.toString();
  const data = await fetchJson<{ solicitudes: Solicitud[] }>(
    `/api/solicitudes${qs ? `?${qs}` : ""}`,
  );
  return data.solicitudes;
}

export async function fetchSolicitud(id: number): Promise<Solicitud> {
  const data = await fetchJson<{ solicitud: Solicitud }>(`/api/solicitudes/${id}`);
  return data.solicitud;
}

export async function crearSolicitud(
  payload: CrearSolicitudPayload,
): Promise<Solicitud> {
  const data = await fetchJson<{ solicitud: Solicitud }>("/api/solicitudes", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return data.solicitud;
}

export async function actualizarSolicitud(
  id: number,
  payload: Partial<CrearSolicitudPayload> & { estado?: string; rol?: string },
): Promise<Solicitud> {
  const data = await fetchJson<{ solicitud: Solicitud }>(`/api/solicitudes/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
  return data.solicitud;
}

export async function eliminarSolicitud(id: number, rol: string): Promise<void> {
  const sp = new URLSearchParams({ rol });
  await fetchJson<{ ok: boolean }>(`/api/solicitudes/${id}?${sp}`, { method: "DELETE" });
}

export async function uploadArchivo(
  file: File,
  kind: string,
): Promise<{ path: string; url: string }> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("kind", kind);
  return fetchJson<{ path: string; url: string }>("/api/solicitudes/upload", {
    method: "POST",
    body: fd,
  });
}

export function urlPdf(id: number): string {
  return `${BASE}/api/solicitudes/${id}/pdf`;
}

export function urlExcel(id: number): string {
  return `${BASE}/api/solicitudes/${id}/excel`;
}

export function urlArchivo(path: string): string {
  if (!path) return "";
  if (path.startsWith("http")) return path;
  return `${BASE}/api/solicitudes/archivos/${path}`;
}

export function labelTipo(tipo: string, tipos?: CatalogoItem[]): string {
  return tipos?.find((t) => t.id === tipo)?.label ?? tipo;
}

export function labelEstado(estado: string, estados?: CatalogoItem[]): string {
  return estados?.find((e) => e.id === estado)?.label ?? estado;
}
