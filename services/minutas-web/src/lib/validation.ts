import type { EntregaForm, SolicitudForm, TemaForm } from "../types/minuta";

export type FieldErrors = Record<string, string>;

export function validarSolicitud(form: SolicitudForm): FieldErrors {
  const e: FieldErrors = {};
  if (!form.numero_referencia.trim()) e.numero_referencia = "Referencia obligatoria.";
  if (!form.solicitante.trim()) e.solicitante = "Solicitante obligatorio.";
  const qty = parseInt(form.cantidad_items, 10);
  if (!form.cantidad_items.trim() || Number.isNaN(qty) || qty < 1) {
    e.cantidad_items = "Cantidad debe ser un entero ≥ 1.";
  }
  return e;
}

export function validarEntrega(
  form: EntregaForm,
  maxPendiente: number
): FieldErrors {
  const e: FieldErrors = {};
  if (!form.fecha.trim()) e.fecha = "Fecha obligatoria.";
  const qty = parseInt(form.cantidad, 10);
  if (!form.cantidad.trim() || Number.isNaN(qty) || qty < 1) {
    e.cantidad = "Cantidad debe ser ≥ 1.";
  } else if (qty > maxPendiente) {
    e.cantidad = `Máximo pendiente: ${maxPendiente}.`;
  }
  return e;
}

export function validarTema(form: TemaForm): FieldErrors {
  const e: FieldErrors = {};
  if (!form.titulo.trim()) e.titulo = "Título obligatorio.";
  return e;
}

export function validarEmails(raw: string): { emails: string[]; error?: string } {
  const parts = raw
    .split(/[,;]/)
    .map((s) => s.trim())
    .filter(Boolean);
  if (!parts.length) return { emails: [], error: "Indicá al menos un destinatario." };
  const invalid = parts.filter((p) => !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(p));
  if (invalid.length) {
    return { emails: [], error: `Email inválido: ${invalid[0]}` };
  }
  return { emails: parts };
}

export function hoyIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function cantidadPendiente(total: number, entregado: number): number {
  return Math.max(0, total - entregado);
}

export function sumEntregas(entregas: { cantidad: number }[]): number {
  return entregas.reduce((s, e) => s + e.cantidad, 0);
}
