/**
 * API minuta por sector (SQLite en PC servidor).
 * Vacío = proxy Vite /api/minuta → :8013
 */
const BASE = (import.meta.env.VITE_MINUTA_API_URL ?? "").replace(/\/$/, "");
const TIMEOUT_MS = 15_000;

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(`${BASE}${path}`, {
      ...init,
      signal: ctrl.signal,
      headers: {
        "Content-Type": "application/json",
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
      throw new Error("Tiempo de espera agotado al contactar el servicio de minutas.");
    }
    if (e instanceof TypeError) {
      throw new Error(
        "No se pudo conectar al servicio de minutas. Ejecutá scripts\\INICIAR_TODO.bat en la PC servidor.",
      );
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

export type Importancia = "critico" | "urgente" | "normal";
export type EstadoItem = "sin_oc" | "en_proceso" | "parcial" | "completado";
export type TipoReunion = "semanal" | "diaria" | "ocasion";
export type VisibilidadReunion = "individual" | "compartida";

export const IMPORTANCIAS: { value: Importancia; label: string }[] = [
  { value: "critico", label: "Crítico" },
  { value: "urgente", label: "Urgente" },
  { value: "normal", label: "Normal" },
];

export const ESTADOS: { value: EstadoItem; label: string }[] = [
  { value: "sin_oc", label: "Sin OC" },
  { value: "en_proceso", label: "En proceso" },
  { value: "parcial", label: "Parcial" },
  { value: "completado", label: "Completado" },
];

export const TIPOS_REUNION: { value: TipoReunion; label: string }[] = [
  { value: "semanal", label: "Semanal" },
  { value: "diaria", label: "Diaria" },
  { value: "ocasion", label: "De ocasión" },
];

export function labelImportancia(v: string): string {
  return IMPORTANCIAS.find((i) => i.value === v)?.label ?? "Normal";
}

/** Orden de negocio: Crítico → Urgente → Normal (menor = más prioritario). */
export function rankImportancia(v: string): number {
  const idx = IMPORTANCIAS.findIndex((i) => i.value === v);
  return idx >= 0 ? idx : IMPORTANCIAS.length;
}

export function labelEstado(v: string): string {
  return ESTADOS.find((e) => e.value === v)?.label ?? "En proceso";
}

export function labelTipo(v: string): string {
  return TIPOS_REUNION.find((t) => t.value === v)?.label ?? v;
}

export type Pedido = {
  id: number;
  pedido: string;
  n_pedido: string;
  fecha: string;
  oc: string;
  sector: string;
  reunion_id?: number;
  activo: number;
  consultas: string;
  importancia: Importancia;
  estado: EstadoItem;
  orden: number;
  fecha_esperada?: string | null;
  ultima_novedad?: string | null;
  ultima_novedad_fecha?: string | null;
  novedad_actual?: string | null;
  total_novedades?: number;
  novedades?: Novedad[];
  movimientos?: MovimientoPedido[];
};

export type PedidoPatch = Partial<
  Pick<
    Pedido,
    | "pedido"
    | "n_pedido"
    | "fecha"
    | "oc"
    | "consultas"
    | "importancia"
    | "estado"
    | "fecha_esperada"
  >
>;

export type Novedad = {
  id: number;
  pedido_id: number;
  fecha_reunion: string;
  texto: string;
  sector: string;
  creado_en: string;
  pedido?: string;
  n_pedido?: string;
  pedido_fecha?: string;
  oc?: string;
};

export type MovimientoPedido = {
  id: number;
  pedido_id: number;
  sector_origen: string;
  sector_destino: string;
  fecha: string;
  notas: string;
  creado_en: string;
};

export type Reunion = {
  id: number;
  sector: string;
  fecha: string;
  notas_generales: string;
  email_enviado_en: string | null;
  titulo: string;
  tipo: TipoReunion;
  visibilidad: VisibilidadReunion;
  owner_email: string;
  sectores_comprometidos: string;
  archivada?: number;
  creado_en: string;
  actualizado_en: string;
};

export async function fetchSectores(): Promise<string[]> {
  const data = await fetchJson<{ sectores: string[] }>("/api/minuta/sectores");
  return data.sectores;
}

export async function fetchPedidosReunion(
  reunionId: number,
  soloActivos = true,
): Promise<Pedido[]> {
  const q = new URLSearchParams({
    reunion_id: String(reunionId),
    activos: soloActivos ? "1" : "0",
  });
  const data = await fetchJson<{ pedidos: Pedido[] }>(`/api/minuta/pedidos?${q}`);
  return data.pedidos;
}

export async function fetchPedidosSector(
  sector: string,
  soloActivos = true,
): Promise<Pedido[]> {
  const q = new URLSearchParams({
    sector,
    activos: soloActivos ? "1" : "0",
  });
  const data = await fetchJson<{ pedidos: Pedido[] }>(`/api/minuta/pedidos?${q}`);
  return data.pedidos;
}

export async function fetchPedido(id: number): Promise<Pedido> {
  const data = await fetchJson<{ pedido: Pedido }>(`/api/minuta/pedidos/${id}`);
  return data.pedido;
}

export async function crearPedido(payload: {
  sector?: string;
  reunion_id: number;
  pedido?: string;
  n_pedido?: string;
  fecha?: string;
  oc?: string;
}): Promise<Pedido> {
  const data = await fetchJson<{ pedido: Pedido }>("/api/minuta/pedidos", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return data.pedido;
}

export async function actualizarPedido(
  id: number,
  patch: PedidoPatch,
): Promise<Pedido> {
  const data = await fetchJson<{ pedido: Pedido }>(`/api/minuta/pedidos/${id}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
  return data.pedido;
}

export async function eliminarPedido(id: number): Promise<void> {
  await fetchJson<{ ok: boolean }>(`/api/minuta/pedidos/${id}`, { method: "DELETE" });
}

export async function reordenarPedidos(
  reunionId: number,
  ids: number[],
): Promise<Pedido[]> {
  const data = await fetchJson<{ pedidos: Pedido[] }>("/api/minuta/pedidos/reordenar", {
    method: "POST",
    body: JSON.stringify({ reunion_id: reunionId, ids }),
  });
  return data.pedidos;
}

export async function limpiarConsultas(reunionId: number): Promise<number> {
  const data = await fetchJson<{ afectados: number }>(
    "/api/minuta/pedidos/limpiar-consultas",
    { method: "POST", body: JSON.stringify({ reunion_id: reunionId }) },
  );
  return data.afectados;
}

export async function agregarNovedad(
  pedidoId: number,
  payload: { fecha_reunion: string; texto: string },
): Promise<Pedido> {
  const data = await fetchJson<{ pedido: Pedido }>(
    `/api/minuta/pedidos/${pedidoId}/novedades`,
    { method: "POST", body: JSON.stringify(payload) },
  );
  return data.pedido;
}

/** Upsert novedad de la fecha de reunion (fuente de verdad para sync multi-PC). */
export async function upsertNovedad(
  pedidoId: number,
  payload: { fecha_reunion: string; texto: string },
): Promise<Pedido> {
  const data = await fetchJson<{ pedido: Pedido }>(
    `/api/minuta/pedidos/${pedidoId}/novedades`,
    { method: "PUT", body: JSON.stringify(payload) },
  );
  return data.pedido;
}

export async function finalizarPedido(
  pedidoId: number,
  payload: { fecha?: string; notas?: string } = {},
): Promise<Pedido> {
  const data = await fetchJson<{ pedido: Pedido }>(
    `/api/minuta/pedidos/${pedidoId}/finalizar`,
    { method: "POST", body: JSON.stringify(payload) },
  );
  return data.pedido;
}

export async function reactivarPedido(pedidoId: number): Promise<Pedido> {
  const data = await fetchJson<{ pedido: Pedido }>(
    `/api/minuta/pedidos/${pedidoId}/reactivar`,
    { method: "POST", body: "{}" },
  );
  return data.pedido;
}

export async function fetchReuniones(opts: {
  sector?: string;
  owner?: string;
  soloEnviadas?: boolean;
  archivadas?: boolean | "all";
  limite?: number;
} = {}): Promise<Reunion[]> {
  const q = new URLSearchParams();
  if (opts.sector) q.set("sector", opts.sector);
  if (opts.owner) q.set("owner", opts.owner);
  if (opts.soloEnviadas) q.set("enviadas", "1");
  if (opts.archivadas === true) q.set("archivadas", "1");
  if (opts.archivadas === "all") q.set("archivadas", "all");
  if (opts.limite) q.set("limite", String(opts.limite));
  const data = await fetchJson<{ reuniones: Reunion[] }>(`/api/minuta/reuniones?${q}`);
  return data.reuniones;
}

/** @deprecated usar fetchReuniones */
export async function fetchReunionesSector(sector: string): Promise<Reunion[]> {
  return fetchReuniones({ sector });
}

export async function fetchReunion(id: number): Promise<Reunion> {
  const data = await fetchJson<{ reunion: Reunion }>(`/api/minuta/reuniones/${id}`);
  return data.reunion;
}

export async function crearReunion(payload: {
  sector: string;
  fecha: string;
  titulo?: string;
  tipo?: TipoReunion;
  visibilidad?: VisibilidadReunion;
  owner_email?: string;
  sectores_comprometidos?: string;
}): Promise<Reunion> {
  const data = await fetchJson<{ reunion: Reunion }>("/api/minuta/reuniones", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return data.reunion;
}

export async function obtenerReunion(sector: string, fecha: string): Promise<Reunion> {
  const data = await fetchJson<{ reunion: Reunion }>("/api/minuta/reuniones", {
    method: "POST",
    body: JSON.stringify({ sector, fecha }),
  });
  return data.reunion;
}

export async function actualizarReunion(
  id: number,
  patch: Partial<
    Pick<
      Reunion,
      | "notas_generales"
      | "email_enviado_en"
      | "titulo"
      | "tipo"
      | "visibilidad"
      | "sectores_comprometidos"
      | "fecha"
      | "archivada"
      | "sector"
    >
  >,
): Promise<Reunion> {
  const data = await fetchJson<{ reunion: Reunion }>(`/api/minuta/reuniones/${id}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
  return data.reunion;
}

export async function eliminarReunion(id: number): Promise<void> {
  await fetchJson<{ ok: boolean }>(`/api/minuta/reuniones/${id}`, { method: "DELETE" });
}

export async function moverPedidosReunion(
  origenId: number,
  destinoId: number,
): Promise<number> {
  const data = await fetchJson<{ movidos: number }>("/api/minuta/reuniones/mover-pedidos", {
    method: "POST",
    body: JSON.stringify({ origen_id: origenId, destino_id: destinoId }),
  });
  return data.movidos;
}

export async function fetchNovedadesReunion(
  sector: string,
  fecha: string,
): Promise<Novedad[]> {
  const q = new URLSearchParams({ sector, fecha });
  const data = await fetchJson<{ novedades: Novedad[] }>(
    `/api/minuta/novedades-reunion?${q}`,
  );
  return data.novedades;
}

export async function exportarMinutaExcel(
  reunionId: number,
  opts?: { ids?: number[]; cols?: string[] },
): Promise<Blob> {
  const q = new URLSearchParams();
  if (opts?.ids?.length) q.set("ids", opts.ids.join(","));
  if (opts?.cols?.length) q.set("cols", opts.cols.join(","));
  const qs = q.toString() ? `?${q}` : "";
  const url = `${BASE}/api/minuta/reuniones/${reunionId}/exportar-excel${qs}`;
  const res = await fetch(url, { method: "GET" });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    const detail = typeof data.detail === "string" ? data.detail : `Error ${res.status}`;
    throw new Error(detail);
  }
  return await res.blob();
}

export function descargarBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function importarNovedadesMinuta(
  reunionId: number,
  file: File,
): Promise<{ procesadas: number; omitidas_duplicadas: number; pendientes_consulta: number; no_reconocidas: number; total_leidas: number; total_importadas: number }> {
  const fd = new FormData();
  fd.append("archivo", file);
  const url = `${BASE}/api/minuta/reuniones/${reunionId}/importar-novedades`;
  const res = await fetch(url, { method: "POST", body: fd });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof data.detail === "string" ? data.detail : `Error ${res.status}`;
    throw new Error(detail);
  }
  return data as { procesadas: number; omitidas_duplicadas: number; pendientes_consulta: number; no_reconocidas: number; total_leidas: number; total_importadas: number };
}
