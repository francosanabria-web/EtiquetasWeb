import type {
  Actualizacion,
  EntregaParcial,
  SesionDetalle,
  SesionResumen,
  Solicitud,
  Tema,
  Urgencia,
} from "../types/minuta";

export const API_URL = (
  import.meta.env.VITE_API_URL ?? "http://localhost:8012"
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
    if (Array.isArray(data?.detail)) {
      return data.detail.map((d: { msg?: string }) => d.msg ?? JSON.stringify(d)).join("; ");
    }
    return JSON.stringify(data);
  } catch {
    return resp.statusText || `Error ${resp.status}`;
  }
}

async function fetchApi(path: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(`${API_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...init?.headers,
      },
    });
  } catch {
    throw new ApiError(
      0,
      `No se pudo contactar la API en ${API_URL}. ¿Está encendida minutas-api?`
    );
  }
}

async function json<T>(resp: Response): Promise<T> {
  if (!resp.ok) throw new ApiError(resp.status, await leerError(resp));
  return (await resp.json()) as T;
}

export async function healthCheck(): Promise<boolean> {
  try {
    const r = await fetchApi("/health");
    return r.ok;
  } catch {
    return false;
  }
}

export async function getSesionActual(): Promise<SesionDetalle | null> {
  const resp = await fetchApi("/sesiones/actual");
  if (resp.status === 404) return null;
  return json<SesionDetalle | null>(resp);
}

export async function listarSesiones(limite = 15): Promise<SesionResumen[]> {
  return json(await fetchApi(`/sesiones?limite=${limite}`));
}

export async function getSesion(id: number): Promise<SesionDetalle> {
  return json(await fetchApi(`/sesiones/${id}`));
}

export async function iniciarSesion(payload: {
  responsable?: string;
  notas_generales?: string;
}): Promise<SesionDetalle> {
  return json(
    await fetchApi("/sesiones/iniciar", {
      method: "POST",
      body: JSON.stringify(payload),
    })
  );
}

export async function actualizarSesion(
  id: number,
  payload: { responsable?: string; notas_generales?: string }
): Promise<SesionResumen> {
  return json(
    await fetchApi(`/sesiones/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    })
  );
}

export async function crearSolicitud(
  sesionId: number,
  payload: {
    numero_referencia: string;
    solicitante: string;
    urgencia: Urgencia;
    cantidad_items: number;
    descripcion?: string;
  }
): Promise<Solicitud> {
  return json(
    await fetchApi(`/sesiones/${sesionId}/solicitudes`, {
      method: "POST",
      body: JSON.stringify(payload),
    })
  );
}

export async function cerrarSolicitud(
  sesionId: number,
  solicitudId: number
): Promise<Solicitud> {
  return json(
    await fetchApi(`/sesiones/${sesionId}/solicitudes/${solicitudId}`, {
      method: "PATCH",
      body: JSON.stringify({ cerrado: true }),
    })
  );
}

export async function agregarEntrega(
  sesionId: number,
  solicitudId: number,
  payload: { fecha: string; cantidad: number; observacion?: string }
): Promise<Solicitud> {
  return json(
    await fetchApi(`/sesiones/${sesionId}/solicitudes/${solicitudId}/entregas`, {
      method: "POST",
      body: JSON.stringify(payload),
    })
  );
}

export async function agregarActualizacion(
  sesionId: number,
  solicitudId: number,
  payload: { texto: string; autor?: string }
): Promise<Actualizacion> {
  return json(
    await fetchApi(
      `/sesiones/${sesionId}/solicitudes/${solicitudId}/actualizaciones`,
      { method: "POST", body: JSON.stringify(payload) }
    )
  );
}

export async function crearTema(
  sesionId: number,
  payload: { titulo: string; descripcion?: string }
): Promise<Tema> {
  return json(
    await fetchApi(`/sesiones/${sesionId}/temas`, {
      method: "POST",
      body: JSON.stringify(payload),
    })
  );
}

export async function toggleTemaResuelto(
  temaId: number,
  resuelto: boolean
): Promise<Tema> {
  return json(
    await fetchApi(`/temas/${temaId}`, {
      method: "PATCH",
      body: JSON.stringify({ resuelto }),
    })
  );
}

export type PreviewEmail = {
  asunto: string;
  cuerpo_texto: string;
  cuerpo_html: string;
};

export async function previewEmail(
  sesionId: number,
  asunto?: string
): Promise<PreviewEmail> {
  const q = asunto ? `?asunto=${encodeURIComponent(asunto)}` : "";
  return json(await fetchApi(`/sesiones/${sesionId}/preview-email${q}`));
}

export async function enviarMinuta(
  sesionId: number,
  payload: { destinatarios: string[]; asunto?: string }
): Promise<{ ok: boolean; mensaje: string }> {
  return json(
    await fetchApi(`/sesiones/${sesionId}/enviar`, {
      method: "POST",
      body: JSON.stringify(payload),
    })
  );
}

export type EntregaParcialExport = EntregaParcial;
