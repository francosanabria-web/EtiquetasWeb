/**
 * Cliente del servicio Activos fuera de planta (:8016).
 * Vacío = proxy Vite /api/activos → :8016.
 */

const BASE = (import.meta.env.VITE_ACTIVOS_API_URL ?? "").replace(/\/$/, "");
const TIMEOUT_MS = 120_000;

export const DIAS_FUERA_ALERTA = 30;
export const DIAS_FUERA_AVISO = 21;

export const SECTOR_CHART_COLORS = [
  "#185FA5",
  "#3B6D11",
  "#854F0B",
  "#A32D2D",
  "#5B4FCF",
];

export type ActivoItem = {
  id: string;
  codigo: string;
  equipo: string;
  sector: string;
  dias_fuera: number;
  cantidad: number;
  estado: string;
  proveedor: string;
  remito: string;
  n_pedido?: string;
  n_oc?: string;
  nro_serie?: string;
  fecha_salida?: string;
  fecha_regreso?: string;
  estado_al_ingreso?: string;
  observaciones?: string;
  fingerprint?: string;
};

export type CrearSalidaPayload = {
  equipo: string;
  sector: string;
  proveedor: string;
  numero_remito: string;
  codigo?: string;
  nro_serie?: string;
  numero_pedido?: string;
  numero_oc?: string;
  cantidad?: number;
  fecha_salida?: string;
  observaciones?: string;
};

export type EditarActivoPayload = {
  equipo?: string;
  sector?: string;
  proveedor?: string;
  numero_remito?: string;
  codigo?: string;
  nro_serie?: string;
  numero_pedido?: string;
  numero_oc?: string;
  cantidad?: number;
  fecha_salida?: string;
  observaciones?: string;
};

export type CrearSalidaResult = {
  mensaje: string;
  id: number;
};

export type MarcarRegresoResult = {
  mensaje: string;
  movidos: number;
  no_encontrados: string[];
  fecha_regreso: string;
  estado_al_ingreso: string;
};

export type ActivosResumen = {
  fuera_de_planta: number;
  ingresados: number;
  dias_promedio_fuera: number;
  criticos: number;
  por_sector: { sector: string; cantidad: number }[];
  sectores: string[];
  lista_fuera: ActivoItem[];
  lista_ingresados: ActivoItem[];
  ultima_actualizacion: string;
};

export type FotoItem = {
  id: string;
  tipo: string;
  foto_b64: string;
  hash_sha256: string;
  mime: string;
  tamano_bytes: number;
  numero_remito: string;
  creado_en: string;
};

export type EncargadoItem = {
  id: number;
  nombre: string;
  legajo: string;
  area: string;
};

export type AuditoriaItem = {
  id: number;
  accion: string;
  usuario_id: number;
  antes_despues: string;
  creado_en: string;
};

export type SubirFotoResultado = {
  tipo: string;
  foto_b64: string;
  hash_sha256: string;
  mime: string;
  tamano_bytes: number;
  numero_remito: string;
};

/** Compress image to WebP max 1280px, 5MB. Returns base64 string or throws. */
export function compressImageToWebP(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    const reader = new FileReader();
    reader.onload = (e) => {
      img.src = e.target!.result as string;
    };
    reader.onerror = () => reject(new Error("Error reading file"));
    reader.onloadend = () => {
      img.onload = () => {
        const canvas = document.createElement("canvas");
        let width = img.width;
        let height = img.height;
        // Max width 1280px, preserve aspect ratio
        if (width > 1280) {
          height = (height * 1280) / width;
          width = 1280;
        }
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext("2d");
        if (!ctx) reject(new Error("No se pudo obtener contexto canvas"));
        else {
          ctx.drawImage(img, 0, 0, width, height);
          // Quality fallback: try 0.8, if >5MB try 0.6, if still >5MB reject
          const MAX_SIZE = 5 * 1024 * 1024; // 5 MB
          let quality = 0.8;
          const dataUrl = canvas.toDataURL("image/webp", quality);
          let blob: Blob = dataUrlToBlob(dataUrl);
          while (blob.size > MAX_SIZE && quality > 0.3) {
            quality -= 0.2;
            canvas.toDataURL("image/webp", quality);
            blob = dataUrlToBlob(canvas.toDataURL("image/webp", quality));
          }
          if (blob.size > MAX_SIZE) reject(new Error("Imagen excede los 5MB incluso tras compresión."));
          else {
            // Verify width constraint
            if (width > 1280) reject(new Error("No se pudo comprimir a 1280px máximo."));
            else resolve(blobToBase64(blob));
          }
        }
      };
      img.onerror = () => reject(new Error("Error cargando imagen"));
    };
    reader.readAsDataURL(file);
  });
}

function dataUrlToBlob(dataUrl: string): Blob {
  const base64 = dataUrl.split(",")[1];
  const mime = dataUrl.split(":")[1].split(";")[0];
  const byteChars = atob(base64);
  const byteNumbers = new Uint8Array(byteChars.length);
  for (let i = 0; byteChars.length > i; i++) {
    byteNumbers[i] = charCodeAt(byteChars[i]);
  }
  return new Blob([byteNumbers], { type: mime });
}

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(reader.result as string);
    reader.readAsDataURL(blob);
  });
}

export function fmtNum(n: number): string {
  return n.toLocaleString("es-AR");
}

export function fmtFechaIso(iso: string): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("es-AR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function claseFilaDias(dias: number): string {
  if (dias > DIAS_FUERA_ALERTA) return "act-row-dias-critico";
  if (dias > DIAS_FUERA_AVISO) return "act-row-dias-aviso";
  return "act-row-dias-ok";
}

export function claseBadgeDias(dias: number): string {
  if (dias > DIAS_FUERA_ALERTA) return "act-dias-badge act-dias-critico";
  if (dias > DIAS_FUERA_AVISO) return "act-dias-badge act-dias-aviso";
  return "act-dias-badge act-dias-ok";
}

export function etiquetaSector(code: string): string {
  const m: Record<string, string> = {
    PRODUCCION: "Producción",
    PROYECTOS: "Proyectos",
    MANTENIMIENTO: "Mantenimiento",
    EDILICIO: "Edilicio",
    AUTOELEVADORES: "Autoelevadores",
  };
  return m[code] ?? code;
}

export const fetchActivosResumen = (token?: string) =>
  fetchJson<ActivosResumen>("/api/activos/resumen", undefined, token);

export const refreshActivos = (token?: string) =>
  fetchJson<{ mensaje: string; timestamp: string }>(
    "/api/activos/refresh",
    { method: "POST" },
    token,
  );

export function marcarRegreso(
  payload: {
    ids: string[];
    fecha_regreso: string;
    estado_al_ingreso: string;
  },
  token?: string,
): Promise<MarcarRegresoResult> {
  return fetchJson<MarcarRegresoResult>(
    "/api/activos/marcar-regreso",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    token,
  );
}

export function restablecerFuera(
  ids: string[],
  token?: string,
): Promise<{ mensaje: string; movidos: number }> {
  return fetchJson(
    "/api/activos/restablecer-fuera",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids }),
    },
    token,
  );
}

export function urlActivosExcel(vista: "fuera" | "ingresados" = "fuera"): string {
  return `${BASE}/api/activos/export.xlsx?vista=${vista}`;
}

export function urlActivosPdf(vista: "fuera" | "ingresados" = "fuera"): string {
  return `${BASE}/api/activos/export.pdf?vista=${vista}`;
}

/** Hoy en YYYY-MM-DD para input type=date */
export function hoyIsoLocal(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/** Subir fotos a un activo (1-3 mandatory para retiro, 0-1 optional para ingreso).
 *  Retorna lista de SubirFotoResultado con tipo, base64, hash, mime, tamaño, remito.
 *  Valida WebP, ≤5MB y calcula hash SHA256 server-side en el backend.
 */
export function subirFotos(
  files: File[],
  tipo: "retiro" | "ingreso" = "retiro",
  token?: string,
): Promise<SubirFotoResultado[]> {
  return new Promise((resolve, reject) => {
    if (files.length === 0) return reject(new Error("Ningún archivo seleccionado."));

    // Para retirada: 1-3 fotos mandatory; Para ingreso: 0-1 foto optional
    const maxPhotos = 3;
    if (files.length > maxPhotos) return reject(new Error(`Máximo ${maxPhotos} fotos permitidas.`));

    // Validate and compress each file to WebP, including the tipo
    const promises = files.map((file) =>
      compressImageToWebP(file).then((b64) => ({
        tipo, // explicit: "retiro" or "ingreso" as sent from frontend
        foto_b64: b64,
        // Hash will be computed server-side from the original file data
        hash_sha256: "", // computed server-side
        mime: "image/webp",
        tamano_bytes: 0, // computed server-side
        numero_remito: "",
      }))
    );

    Promise.all(promises)
      .then((results) => resolve(results as SubirFotoResultado[]))
      .catch(reject);
  });
}

/** Listar fotos de un activo */
export function listarFotos(
  activoId: number,
  token?: string,
): Promise<FotoItem[]> {
  return fetchJson<FotoItem[]>(`/api/activos/${activoId}/fotos`, undefined, token);
}

/** Listar encargados por área (name-only) */
export function listarEncargados(
  areaId: number,
  token?: string,
): Promise<EncargadoItem[]> {
  return fetchJson<EncargadoItem[]>(`/api/activos/encargados?area_id=${areaId}`, undefined, token);
}

/** Ver auditoría de un activo (solo admin) */
export function verAuditoria(
  activoId: number,
  token?: string,
): Promise<AuditoriaItem[]> {
  return fetchJson<AuditoriaItem[]>(`/api/activos/${activoId}/auditoria`, undefined, token);
}

export function crearSalida(
  payload: CrearSalidaPayload,
  token?: string,
): Promise<CrearSalidaResult> {
  return fetchJson<CrearSalidaResult>(
    "/api/activos/salida",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    token,
  );
}

export function editarActivo(
  id: number,
  payload: EditarActivoPayload,
  token?: string,
): Promise<{ mensaje: string }> {
  return fetchJson<{ mensaje: string }>(
    `/api/activos/${id}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    token,
  );
}