/**
 * URL del servicio de correo.
 * - Dejar vacío (recomendado en LAN): Vite proxy /api/email → :8020 en la PC servidor.
 * - O setear IP explícita: http://10.1.102.8:8020 (solo si no usás npm run dev).
 */
const BASE = (import.meta.env.VITE_EMAIL_API_URL ?? "").replace(/\/$/, "");

const TIMEOUT_MS = 15_000;

export type Contacto = {
  id: string;
  email: string;
  etiqueta: string;
  tipo: string | null;
};

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
        typeof data.detail === "string"
          ? data.detail
          : `Error ${res.status}`;
      throw new Error(detail);
    }
    return data as T;
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") {
      throw new Error("Tiempo de espera agotado al contactar el servicio de correo.");
    }
    if (e instanceof TypeError) {
      throw new Error(
        "No se pudo conectar al servicio de correo. Ejecutá scripts\\INICIAR_TODO.bat en la PC servidor.",
      );
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

export async function fetchContactos(): Promise<Contacto[]> {
  const data = await fetchJson<{ contactos: Contacto[] }>("/api/email/contacts");
  return data.contactos;
}

export async function enviarCorreo(payload: {
  destinatarios: string[];
  asunto: string;
  cuerpo_html: string;
  cuerpo_texto?: string;
}): Promise<void> {
  await fetchJson("/api/email/send", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
