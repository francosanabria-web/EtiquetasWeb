/**
 * API Personal (:8019).
 * Vacío = proxy Vite /api/personal → :8019.
 */

const BASE = (import.meta.env.VITE_PERSONAL_API_URL ?? "").replace(/\/$/, "");
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
      throw new Error("Tiempo de espera agotado al contactar el servicio de personal.");
    }
    if (e instanceof TypeError) {
      throw new Error(
        "No se pudo conectar al servicio de personal. Verificá que esté corriendo (puerto 8019).",
      );
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

export type PersonalTipo = "tecnico" | "supervisor" | "produccion" | "generico" | "panol";

export type Personal = {
  id: number;
  legajo: string | null;
  nombre: string;
  email: string | null;
  area_id: number | null;
  tipo: PersonalTipo;
  activo: boolean;
  prefs?: Record<string, boolean>;
};

export type PersonalListResponse = {
  items: Personal[];
  total: number;
};

export type Area = {
  id: number;
  nombre: string;
};

export type PersonalListParams = {
  q?: string;
  area_id?: number;
  tipo?: string;
  activo?: boolean;
  limit?: number;
  offset?: number;
};

export async function getPersonal(token: string, params?: PersonalListParams): Promise<PersonalListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.q) searchParams.set("q", params.q);
  if (params?.area_id != null) searchParams.set("area_id", String(params.area_id));
  if (params?.tipo) searchParams.set("tipo", params.tipo);
  if (params?.activo != null) searchParams.set("activo", String(params.activo ? 1 : 0));
  if (params?.limit) searchParams.set("limit", String(params.limit));
  if (params?.offset) searchParams.set("offset", String(params.offset));
  const qs = searchParams.toString();
  const path = qs ? `/api/personal?${qs}` : "/api/personal";
  const data = await fetchJson<{ items: Personal[]; total: number }>(path, {}, token);
  return { items: data.items ?? data, total: data.total ?? 0 };
}

export async function getPersonalById(token: string, id: number): Promise<Personal> {
  const data = await fetchJson<Personal>(`/api/personal/${id}`, {}, token);
  return data;
}

export async function createPersonal(token: string, data: Omit<Personal, "id">): Promise<Personal> {
  const payload = {
    nombre: data.nombre,
    legajo: data.legajo ?? null,
    email: data.email ?? null,
    area_id: data.area_id ?? null,
    tipo: data.tipo,
    activo: data.activo ?? true,
  };
  const result = await fetchJson<Personal>("/api/personal", {
    method: "POST",
    body: JSON.stringify(payload),
  }, token);
  return result;
}

export async function updatePersonal(token: string, id: number, data: Partial<Omit<Personal, "id">>): Promise<Personal> {
  const payload: Record<string, unknown> = {};
  if (data.nombre !== undefined) payload.nombre = data.nombre;
  if (data.legajo !== undefined) payload.legajo = data.legajo ?? null;
  if (data.email !== undefined) payload.email = data.email ?? null;
  if (data.area_id !== undefined) payload.area_id = data.area_id ?? null;
  if (data.tipo !== undefined) payload.tipo = data.tipo;
  if (data.activo !== undefined) payload.activo = data.activo;
  const result = await fetchJson<Personal>(`/api/personal/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  }, token);
  return result;
}

export async function deletePersonal(token: string, id: number): Promise<void> {
  await fetchJson<{ ok: boolean }>(`/api/personal/${id}`, { method: "DELETE" }, token);
}

export async function getAreas(token: string): Promise<Area[]> {
  const data = await fetchJson<{ areas: Area[] }>("/api/areas", {}, token);
  return data.areas ?? [];
}

export type MailPrefs = Record<string, boolean>;

export async function getPersonalMailPrefs(token: string, id: number): Promise<MailPrefs> {
  const data = await fetchJson<MailPrefs>(`/api/personal/${id}/mail-prefs`, {}, token);
  return data;
}

export async function setPersonalMailPrefs(token: string, id: number, prefs: MailPrefs): Promise<MailPrefs> {
  const data = await fetchJson<MailPrefs>(`/api/personal/${id}/mail-prefs`, {
    method: "PUT",
    body: JSON.stringify(prefs),
  }, token);
  return data;
}

export async function listAllPersonalMailPrefs(token: string): Promise<{ items: Array<{ id: number; nombre: string; prefs: Record<string, boolean> }>; total: number }> {
  const data = await fetchJson<{ items: Array<{ id: number; nombre: string; prefs: Record<string, boolean> }>; total: number }>("/api/personal/mail-prefs", {}, token);
  return data;
}
