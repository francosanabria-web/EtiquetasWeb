import type { PedidoPatch } from "../../api/minutaClient";

export function fechaHoyIso(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function fmtFecha(iso: string): string {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-");
  if (!y || !m || !d) return iso;
  return `${d}/${m}/${y}`;
}

/** Borrador local hasta enviar mail (excepto consultas, que van a DB). */
export type MinutaSesionLocal = {
  reunionId: number | null;
  sectoresComprometidos: string;
  fecha: string;
  notasGenerales: string;
  destinatarios: string[];
  borradoresNovedad: Record<number, string>;
  /** Campos editables en cache hasta enviar mail */
  borradoresCampos: Record<number, PedidoPatch>;
  /** Ítems ya vistos en esta reunión; se reinicia al enviar el mail. */
  vistosEnReunion: Record<number, boolean>;
};

export function sesionInicial(reunionId: number | null = null): MinutaSesionLocal {
  return {
    reunionId,
    sectoresComprometidos: "Mantenimiento",
    fecha: fechaHoyIso(),
    notasGenerales: "",
    destinatarios: [],
    borradoresNovedad: {},
    borradoresCampos: {},
    vistosEnReunion: {},
  };
}

function storageKey(scope: string, reunionId: number | null): string {
  return `panol_minuta_sesion:${scope || "anon"}:r${reunionId ?? "new"}`;
}

export function cargarSesionLocal(
  scope: string,
  reunionId: number | null,
): MinutaSesionLocal | null {
  try {
    const raw = localStorage.getItem(storageKey(scope, reunionId));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as MinutaSesionLocal;
    return {
      ...sesionInicial(reunionId),
      ...parsed,
      borradoresCampos: parsed.borradoresCampos ?? {},
      borradoresNovedad: parsed.borradoresNovedad ?? {},
      vistosEnReunion: parsed.vistosEnReunion ?? {},
    };
  } catch {
    return null;
  }
}

export function guardarSesionLocal(
  scope: string,
  reunionId: number | null,
  sesion: MinutaSesionLocal,
): void {
  localStorage.setItem(storageKey(scope, reunionId), JSON.stringify(sesion));
}

export function limpiarSesionLocal(scope: string, reunionId: number | null): void {
  localStorage.removeItem(storageKey(scope, reunionId));
}
