import type { CatalogoItem, NuevaEtiqueta, Pedido, PedidoCreado } from "./types";

// URL base de la API (solo LAN / localhost). Configurar en .env.local en la PC servidor.
export const API_URL = (
  import.meta.env.VITE_API_URL ?? "http://localhost:8010"
).replace(/\/$/, "");

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function leerError(resp: Response): Promise<string> {
  try {
    const data = await resp.json();
    if (typeof data?.detail === "string") return data.detail;
    return JSON.stringify(data);
  } catch {
    return resp.statusText || `Error ${resp.status}`;
  }
}

/**
 * fetch con mensaje de error claro: si falla la conexión (no hay red, API
 * apagada o URL equivocada) avisa contra qué dirección se intentó. Esto evita
 * el críptico "Failed to fetch" y deja ver si la web apunta a la API correcta.
 */
async function fetchApi(path: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(`${API_URL}${path}`, init);
  } catch {
    throw new ApiError(
      0,
      `No se pudo contactar la API en ${API_URL}. ¿Está encendida y es la dirección correcta?`
    );
  }
}

/** Busca un código en el catálogo. Devuelve null si no existe (404). */
export async function buscarCatalogo(codigo: string): Promise<CatalogoItem | null> {
  const resp = await fetchApi(`/catalogo/${encodeURIComponent(codigo)}`);
  if (resp.status === 404) return null;
  if (!resp.ok) throw new ApiError(resp.status, await leerError(resp));
  return (await resp.json()) as CatalogoItem;
}

export async function crearEtiqueta(payload: NuevaEtiqueta): Promise<PedidoCreado> {
  const resp = await fetchApi(`/etiquetas`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) throw new ApiError(resp.status, await leerError(resp));
  return (await resp.json()) as PedidoCreado;
}

export async function getPendientes(): Promise<Pedido[]> {
  const resp = await fetchApi(`/etiquetas/pendientes`);
  if (!resp.ok) throw new ApiError(resp.status, await leerError(resp));
  return (await resp.json()) as Pedido[];
}
