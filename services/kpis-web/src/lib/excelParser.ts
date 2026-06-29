import * as XLSX from "xlsx";
import type { HojaExcel, ResultadoParseo } from "../types/kpi";

function celdaAString(val: unknown): string {
  if (val == null) return "";
  if (val instanceof Date) return val.toISOString().slice(0, 10);
  return String(val).trim();
}

function filaComoObjeto(
  encabezados: string[],
  fila: unknown[]
): Record<string, unknown> {
  const obj: Record<string, unknown> = {};
  encabezados.forEach((h, i) => {
    if (h) obj[h] = fila[i] ?? "";
  });
  return obj;
}

function detectarFilaEncabezado(filas: unknown[][]): number {
  for (let i = 0; i < Math.min(filas.length, 15); i++) {
    const celdas = (filas[i] ?? []).map(celdaAString);
    const noVacias = celdas.filter(Boolean).length;
    if (noVacias >= 3) return i;
  }
  return 0;
}

function parsearHoja(sheet: XLSX.WorkSheet, nombre: string): HojaExcel {
  const matriz = XLSX.utils.sheet_to_json<unknown[]>(sheet, {
    header: 1,
    defval: "",
    raw: false,
  }) as unknown[][];

  const filaEnc = detectarFilaEncabezado(matriz);
  const encRaw = (matriz[filaEnc] ?? []).map(celdaAString);
  const encabezados = encRaw.map((h, idx) => h || `Col_${idx + 1}`);

  const datos = matriz.slice(filaEnc + 1).filter((fila) => {
    const vals = (fila ?? []).map(celdaAString);
    return vals.some(Boolean);
  });

  const filasPreview = datos.slice(0, 8).map((fila) =>
    filaComoObjeto(encabezados, fila as unknown[])
  );

  return {
    nombre,
    encabezados,
    filasPreview,
    totalFilas: datos.length,
  };
}

export async function leerArchivoExcel(file: File): Promise<ResultadoParseo> {
  const buffer = await file.arrayBuffer();
  const libro = XLSX.read(buffer, { type: "array", cellDates: true });
  const hojas = libro.SheetNames.map((nombre) =>
    parsearHoja(libro.Sheets[nombre], nombre)
  );
  return { hojas };
}

export function obtenerMatrizHoja(
  file: ArrayBuffer,
  hoja: string,
  filaEncabezado: number
): { encabezados: string[]; filas: Record<string, unknown>[] } {
  const libro = XLSX.read(file, { type: "array", cellDates: true });
  const sheet = libro.Sheets[hoja];
  if (!sheet) throw new Error(`Hoja "${hoja}" no encontrada`);

  const matriz = XLSX.utils.sheet_to_json<unknown[]>(sheet, {
    header: 1,
    defval: "",
    raw: false,
  }) as unknown[][];

  const encRaw = (matriz[filaEncabezado] ?? []).map(celdaAString);
  const encabezados = encRaw.map((h, idx) => h || `Col_${idx + 1}`);

  const filas = matriz
    .slice(filaEncabezado + 1)
    .filter((fila) => (fila ?? []).map(celdaAString).some(Boolean))
    .map((fila) => filaComoObjeto(encabezados, fila as unknown[]));

  return { encabezados, filas };
}
