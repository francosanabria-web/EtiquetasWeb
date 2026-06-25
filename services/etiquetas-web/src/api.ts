import type { CatalogoItem, NuevaEtiqueta, Pedido, PedidoCreado } from "./types";

// URL base de la API. Configurable con VITE_API_URL (ej. http://192.168.1.50:8000).
export const API_URL = (
  import.meta.env.VITE_API_URL ?? "http://localhost:8000"
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

/** Busca un código en el catálogo. Devuelve null si no existe (404). */
export async function buscarCatalogo(codigo: string): Promise<CatalogoItem | null> {
  const resp = await fetch(`${API_URL}/catalogo/${encodeURIComponent(codigo)}`);
  if (resp.status === 404) return null;
  if (!resp.ok) throw new ApiError(resp.status, await leerError(resp));
  return (await resp.json()) as CatalogoItem;
}

export async function crearEtiqueta(payload: NuevaEtiqueta): Promise<PedidoCreado> {
  const resp = await fetch(`${API_URL}/etiquetas`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) throw new ApiError(resp.status, await leerError(resp));
  return (await resp.json()) as PedidoCreado;
}

export async function getPendientes(): Promise<Pedido[]> {
  const resp = await fetch(`${API_URL}/etiquetas/pendientes`);
  if (!resp.ok) throw new ApiError(resp.status, await leerError(resp));
  return (await resp.json()) as Pedido[];
}
