/** Campos que el motor KPI entiende a partir del Excel. */
export type CampoDato =
  | "fecha"
  | "linea"
  | "obra"
  | "concepto"
  | "importe"
  | "categoria";

export const CAMPOS_DATO: CampoDato[] = [
  "fecha",
  "linea",
  "obra",
  "concepto",
  "importe",
  "categoria",
];

export const ETIQUETAS_CAMPO: Record<CampoDato, string> = {
  fecha: "Fecha",
  linea: "Línea / centro de costo",
  obra: "Obra / proyecto",
  concepto: "Concepto / descripción",
  importe: "Importe / monto",
  categoria: "Categoría (opcional)",
};

export type RegistroGasto = {
  id: string;
  fecha: string;
  linea: string;
  obra: string;
  concepto: string;
  importe: number;
  categoria: string;
};

export type ConfigImportacion = {
  version: 1;
  hoja: string;
  filaEncabezado: number;
  /** campo lógico → nombre de columna en el Excel */
  mapeo: Partial<Record<CampoDato, string>>;
};

export type MetaImportacion = {
  nombreArchivo: string;
  importadoEn: string;
  filasValidas: number;
  filasDescartadas: number;
};

export type FiltrosDashboard = {
  fechaDesde: string;
  fechaHasta: string;
  lineas: string[];
  obras: string[];
};

export type ResumenKpi = {
  total: number;
  cantidad: number;
  promedioDiario: number;
  diasConDatos: number;
  lineaTop: { nombre: string; total: number } | null;
  obraTop: { nombre: string; total: number } | null;
};

export type Agrupacion = {
  clave: string;
  total: number;
  cantidad: number;
};

export type PuntoSerie = {
  fecha: string;
  total: number;
  cantidad: number;
};

export type VistaActiva = "dashboard" | "datos" | "config";

export type HojaExcel = {
  nombre: string;
  encabezados: string[];
  filasPreview: Record<string, unknown>[];
  totalFilas: number;
};

export type ResultadoParseo = {
  hojas: HojaExcel[];
};
