import type { CampoDato, ConfigImportacion } from "../types/kpi";
import { CAMPOS_DATO } from "../types/kpi";

const SINONIMOS: Record<CampoDato, string[]> = {
  fecha: ["fecha", "date", "fec", "dia", "día", "periodo"],
  linea: ["linea", "línea", "line", "centro", "cc", "centro costo", "centro de costo"],
  obra: ["obra", "proyecto", "project", "ot", "orden", "trabajo"],
  concepto: ["concepto", "descripcion", "descripción", "detalle", "item", "rubro"],
  importe: ["importe", "monto", "gasto", "valor", "amount", "total", "costo", "coste"],
  categoria: ["categoria", "categoría", "tipo", "rubro", "clase", "familia"],
};

function normalizar(texto: string): string {
  return texto
    .toLowerCase()
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function puntajeColumna(encabezado: string, sinonimos: string[]): number {
  const n = normalizar(encabezado);
  for (const s of sinonimos) {
    if (n === s) return 100;
    if (n.includes(s) || s.includes(n)) return 70;
    const palabras = s.split(" ");
    if (palabras.every((p) => n.includes(p))) return 50;
  }
  return 0;
}

/** Sugiere mapeo automático campo → columna Excel. */
export function sugerirMapeo(encabezados: string[]): Partial<Record<CampoDato, string>> {
  const usadas = new Set<string>();
  const mapeo: Partial<Record<CampoDato, string>> = {};

  for (const campo of CAMPOS_DATO) {
    let mejor: { col: string; score: number } | null = null;
    for (const col of encabezados) {
      if (usadas.has(col)) continue;
      const score = puntajeColumna(col, SINONIMOS[campo]);
      if (score > 0 && (!mejor || score > mejor.score)) {
        mejor = { col, score };
      }
    }
    if (mejor && mejor.score >= 50) {
      mapeo[campo] = mejor.col;
      usadas.add(mejor.col);
    }
  }
  return mapeo;
}

export function configValida(cfg: ConfigImportacion): boolean {
  const req: CampoDato[] = ["fecha", "importe"];
  return req.every((c) => !!cfg.mapeo[c]);
}

export function crearConfigInicial(
  hoja: string,
  encabezados: string[],
  filaEncabezado = 0
): ConfigImportacion {
  return {
    version: 1,
    hoja,
    filaEncabezado,
    mapeo: sugerirMapeo(encabezados),
  };
}

export function columnasSinMapear(
  encabezados: string[],
  mapeo: Partial<Record<CampoDato, string>>
): string[] {
  const usadas = new Set(Object.values(mapeo).filter(Boolean));
  return encabezados.filter((c) => !usadas.has(c));
}
