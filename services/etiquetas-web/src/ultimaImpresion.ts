/**
 * Buffer de la última impresión enviada a la cola.
 *
 * Persistimos en localStorage del navegador:
 * no hace falta endpoint en la API y sobrevive recargas / cierres de pestaña.
 * Sirve para "Usar última" (rellenar el formulario) y "Reimprimir último"
 * (reenviar el mismo payload a POST /etiquetas).
 */

import type { NuevaEtiqueta, TipoEtiqueta } from "./types";

const STORAGE_KEY = "etiquetas_ultima_impresion";

export type UltimaImpresion = NuevaEtiqueta & {
  /** ISO local de cuándo se guardó (solo informativo en UI). */
  guardado_en: string;
};

export function guardarUltimaImpresion(payload: NuevaEtiqueta): void {
  const registro: UltimaImpresion = {
    ...payload,
    guardado_en: new Date().toISOString(),
  };
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(registro));
  } catch {
    // Quota / modo privado: silencioso; la app sigue funcionando sin buffer.
  }
}

export function leerUltimaImpresion(): UltimaImpresion | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw) as UltimaImpresion;
    if (!data || typeof data !== "object" || !data.tipo) return null;
    return data;
  } catch {
    return null;
  }
}

/** Texto corto para mostrar en la barra de "última impresión". */
export function resumenUltima(u: UltimaImpresion): string {
  if (u.tipo === "simple") {
    const t = u.texto_libre.trim();
    return t.length > 48 ? `${t.slice(0, 48)}…` : t;
  }
  return u.codigo;
}

export function etiquetaTipo(tipo: TipoEtiqueta): string {
  switch (tipo) {
    case "simple":
      return "Rótulo";
    case "codigo":
      return "Código";
    case "mercaderia_nueva":
      return "Mercadería";
  }
}
