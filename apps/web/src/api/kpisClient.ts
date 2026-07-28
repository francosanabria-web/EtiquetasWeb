/**
 * URL del servicio KPIs.
 * Vacío = proxy Vite /api/kpis → :8001 (recomendado en LAN).
 */
const BASE = (import.meta.env.VITE_KPIS_API_URL ?? "").replace(/\/$/, "");
const TIMEOUT_MS = 120_000;

export const KPI_COLORS = {
  stock: "#185FA5",
  consumo: "#3B6D11",
  reposicion: "#854F0B",
  activos: "#A32D2D",
} as const;

export const SECTOR_CHART_COLORS = [
  "#185FA5",
  "#3B6D11",
  "#854F0B",
  "#A32D2D",
  "#5B4FCF",
];

/** Umbral almacen_gui._color_dias_fuera — rojo si > 30 días */
export const DIAS_FUERA_ALERTA = 30;
export const DIAS_FUERA_AVISO = 21;

export type StockResumen = {
  total_articulos: number;
  bajo_minimo: { cantidad: number; porcentaje: number; valor_pesos: number };
  sobre_minimo: { cantidad: number; porcentaje: number; valor_pesos: number };
  en_cero: { cantidad: number; valor_reposicion_estimado: number };
  stock_valorizado_total: number;
  por_criticidad: { criticidad: string; cantidad: number; valor: number }[];
  ultima_actualizacion: string;
};

export type ArticuloStock = {
  codigo: string;
  desc: string;
  stock: number;
  stk_min: number;
  precio_unitario: number;
  faltante?: number;
  valor_faltante?: number;
  valor_reposicion?: number;
  criticidad: string;
};

export type ConsumoMensual = {
  datos: { periodo: string; total: number }[];
  ultima_actualizacion: string;
};

export type ConsumoSector = {
  periodo: string;
  datos: { sector: string; total: number }[];
  ultima_actualizacion: string;
};

export type ConsumoLinea = {
  periodo: string;
  sector_filtro: string;
  datos: { linea: string; total: number }[];
  ultima_actualizacion: string;
};

export type ConsumoTop = {
  periodo: string;
  por_monto: { codigo: string; descripcion: string; monto: number }[];
  por_cantidad: { codigo: string; descripcion: string; cantidad: number }[];
  ultima_actualizacion: string;
};

export type ConsumoTendenciaAnual = {
  datos: Record<string, string | number>[];
  sectores: string[];
  ultima_actualizacion: string;
};

export type ReposicionResumen = {
  articulos_a_reponer: number;
  criticos_bajo_minimo: number;
  valor_total_reposicion: number;
  lista: ArticuloStock[];
  ultima_actualizacion: string;
};

export type ActivosResumen = {
  fuera_de_planta: number;
  dias_promedio_fuera: number;
  por_sector: { sector: string; cantidad: number }[];
  lista: {
    codigo: string;
    equipo: string;
    sector: string;
    dias_fuera: number;
    estado: string;
    proveedor: string;
    remito: string;
    n_pedido?: string;
    n_oc?: string;
  }[];
  ultima_actualizacion: string;
};

export type KpisHealth = {
  estado: string;
  archivos: Record<string, boolean>;
  sectores: string[];
  ultima_actualizacion: string;
};

async function fetchJson<T>(path: string): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(`${BASE}${path}`, { signal: ctrl.signal });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = typeof data.detail === "string" ? data.detail : `Error ${res.status}`;
      if (res.status === 503) {
        throw new Error(`${detail} (servicio iniciando o Excel en carga — espere y reintente).`);
      }
      throw new Error(detail);
    }
    return data as T;
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") {
      throw new Error("Tiempo de espera agotado al contactar el servicio KPIs.");
    }
    if (e instanceof TypeError) {
      throw new Error(
        "No se pudo conectar con el servicio KPIs. Ejecutá scripts\\INICIAR_TODO.bat en la PC servidor.",
      );
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

export function mesActual(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export function fmtPesos(n: number): string {
  return `$ ${n.toLocaleString("es-AR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function fmtNum(n: number): string {
  return n.toLocaleString("es-AR");
}

export function fmtPct(n: number): string {
  return `${n.toLocaleString("es-AR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`;
}

export function fmtFecha(iso: string): string {
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

export function claseFilaDiasFuera(dias: number): string {
  if (dias > DIAS_FUERA_ALERTA) return "kpi-row-dias-critico";
  if (dias > DIAS_FUERA_AVISO) return "kpi-row-dias-aviso";
  return "kpi-row-dias-ok";
}

/** Colores alineados al mail del escritorio (#C6EFCE / #FFEB9C / #FFC7CE), versión sutil en UI */
export const DIAS_FUERA_ESTILOS = {
  ok: { mail: "#C6EFCE", ui: "#e8f8ec" },
  aviso: { mail: "#FFEB9C", ui: "#fff9e6" },
  critico: { mail: "#FFC7CE", ui: "#fde8ea" },
} as const;

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

export const fetchKpisHealth = () => fetchJson<KpisHealth>("/api/kpis/health");
export const refreshKpis = () =>
  fetchJson<{ mensaje: string; timestamp: string }>("/api/kpis/refresh");
export const fetchStockResumen = () => fetchJson<StockResumen>("/api/kpis/stock/resumen");
export const fetchStockEnCero = (top = 20) =>
  fetchJson<{ articulos: ArticuloStock[]; total: number; ultima_actualizacion: string }>(
    `/api/kpis/stock/en-cero?top=${top}`,
  );
export const fetchConsumoMensual = (meses = 12) =>
  fetchJson<ConsumoMensual>(`/api/kpis/consumo/mensual?meses=${meses}`);
export const fetchConsumoSector = (mes: string) =>
  fetchJson<ConsumoSector>(`/api/kpis/consumo/por-sector?mes=${mes}`);
export const fetchConsumoLinea = (mes: string) =>
  fetchJson<ConsumoLinea>(`/api/kpis/consumo/por-linea?mes=${mes}`);
export const fetchConsumoTop = (mes: string, top = 10) =>
  fetchJson<ConsumoTop>(`/api/kpis/consumo/top-articulos?mes=${mes}&top=${top}`);
export const fetchConsumoTendenciaAnual = () =>
  fetchJson<ConsumoTendenciaAnual>("/api/kpis/consumo/tendencia-anual");
export const fetchReposicion = () => fetchJson<ReposicionResumen>("/api/kpis/reposicion/resumen");
export const fetchActivos = () => fetchJson<ActivosResumen>("/api/kpis/activos/resumen");

export function urlActivosExcel(): string {
  return `${BASE}/api/kpis/activos/export.xlsx`;
}

export function urlActivosPdf(): string {
  return `${BASE}/api/kpis/activos/export.pdf`;
}
