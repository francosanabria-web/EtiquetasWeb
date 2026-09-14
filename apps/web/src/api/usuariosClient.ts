/**
 * API Usuarios / accesos.
 * Vacío = proxy Vite /api/usuarios → :8015
 */
import type { NivelPermiso, PermisosUsuario, Rol, Usuario } from "../config/navegacion";

const BASE = (import.meta.env.VITE_USUARIOS_API_URL ?? "").replace(/\/$/, "");
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
      throw new Error("Tiempo de espera agotado al contactar el servicio de usuarios.");
    }
    if (e instanceof TypeError) {
      throw new Error(
        "No se pudo conectar al servicio de usuarios. Verificá que esté corriendo (puerto 8015).",
      );
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

export type CatalogoUsuarios = {
  modulos: string[];
  roles: Rol[];
  niveles: NivelPermiso[];
  plantillas: Record<Rol, PermisosUsuario>;
};

export type CrearUsuarioPayload = {
  usuario: string;
  nombre: string;
  clave: string;
  rol: Rol;
  permisos?: PermisosUsuario;
};

export type ActualizarUsuarioPayload = {
  nombre?: string;
  email?: string;
  rol?: Rol;
  activo?: boolean;
  permisos?: PermisosUsuario;
};

export async function login(usuario: string, clave: string): Promise<{ token: string; usuario: Usuario }> {
  return fetchJson<{ token: string; usuario: Usuario }>("/api/usuarios/login", {
    method: "POST",
    body: JSON.stringify({ usuario, clave }),
  });
}

export async function logout(token: string): Promise<void> {
  await fetchJson<{ ok: boolean }>("/api/usuarios/logout", { method: "POST" }, token).catch(() => {});
}

export async function me(token: string): Promise<Usuario> {
  const data = await fetchJson<{ usuario: Usuario }>("/api/usuarios/me", {}, token);
  return data.usuario;
}

export async function cambiarMiPassword(token: string, actual: string, nueva: string): Promise<void> {
  await fetchJson<{ ok: boolean }>(
    "/api/usuarios/mi-password",
    { method: "POST", body: JSON.stringify({ actual, nueva }) },
    token,
  );
}

export async function fetchCatalogo(): Promise<CatalogoUsuarios> {
  return fetchJson<CatalogoUsuarios>("/api/usuarios/catalogo");
}

export async function listarUsuarios(token: string): Promise<Usuario[]> {
  const data = await fetchJson<{ usuarios: Usuario[] }>("/api/usuarios", {}, token);
  return data.usuarios;
}

export async function crearUsuario(token: string, payload: CrearUsuarioPayload): Promise<Usuario> {
  const data = await fetchJson<{ usuario: Usuario }>(
    "/api/usuarios",
    { method: "POST", body: JSON.stringify(payload) },
    token,
  );
  return data.usuario;
}

export async function actualizarUsuario(
  token: string,
  id: number,
  payload: ActualizarUsuarioPayload,
): Promise<Usuario> {
  const data = await fetchJson<{ usuario: Usuario }>(
    `/api/usuarios/${id}`,
    { method: "PATCH", body: JSON.stringify(payload) },
    token,
  );
  return data.usuario;
}

export async function setPassword(token: string, id: number, nueva: string): Promise<void> {
  await fetchJson<{ ok: boolean }>(
    `/api/usuarios/${id}/password`,
    { method: "POST", body: JSON.stringify({ nueva }) },
    token,
  );
}

export async function eliminarUsuario(token: string, id: number): Promise<void> {
  await fetchJson<{ ok: boolean }>(`/api/usuarios/${id}`, { method: "DELETE" }, token);
}
