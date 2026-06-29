import type {
  ConfigImportacion,
  FiltrosDashboard,
  RegistroGasto,
  ResumenKpi,
  Agrupacion,
  PuntoSerie,
} from "../types/kpi";

function parsearFecha(val: unknown): string | null {
  if (val == null || val === "") return null;
  if (val instanceof Date && !Number.isNaN(val.getTime())) {
    return val.toISOString().slice(0, 10);
  }
  const s = String(val).trim();
  const iso = /^\d{4}-\d{2}-\d{2}/.exec(s);
  if (iso) return iso[0];
  const dmy = /^(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{2,4})/.exec(s);
  if (dmy) {
    const dd = dmy[1].padStart(2, "0");
    const mm = dmy[2].padStart(2, "0");
    let yy = dmy[3];
    if (yy.length === 2) yy = `20${yy}`;
    return `${yy}-${mm}-${dd}`;
  }
  const n = Number(s);
  if (!Number.isNaN(n) && n > 30000 && n < 60000) {
    const epoch = new Date(Date.UTC(1899, 11, 30));
    epoch.setUTCDate(epoch.getUTCDate() + Math.floor(n));
    return epoch.toISOString().slice(0, 10);
  }
  const d = new Date(s);
  if (!Number.isNaN(d.getTime())) return d.toISOString().slice(0, 10);
  return null;
}

function parsearImporte(val: unknown): number | null {
  if (val == null || val === "") return null;
  if (typeof val === "number" && !Number.isNaN(val)) return val;
  let s = String(val).trim();
  s = s.replace(/[^\d,.\-]/g, "");
  if (!s) return null;
  if (s.includes(",") && s.includes(".")) {
    s = s.replace(/\./g, "").replace(",", ".");
  } else if (s.includes(",")) {
    s = s.replace(",", ".");
  }
  const n = parseFloat(s);
  return Number.isNaN(n) ? null : n;
}

function texto(val: unknown): string {
  if (val == null) return "";
  return String(val).trim();
}

export function transformarFilas(
  filas: Record<string, unknown>[],
  config: ConfigImportacion
): { validos: RegistroGasto[]; descartados: number } {
  const m = config.mapeo;
  const validos: RegistroGasto[] = [];
  let descartados = 0;

  filas.forEach((fila, idx) => {
    const fecha = m.fecha ? parsearFecha(fila[m.fecha]) : null;
    const importe = m.importe ? parsearImporte(fila[m.importe]) : null;
    if (!fecha || importe == null) {
      descartados++;
      return;
    }
    validos.push({
      id: `${fecha}-${idx}-${importe}`,
      fecha,
      linea: m.linea ? texto(fila[m.linea]) || "Sin línea" : "Sin línea",
      obra: m.obra ? texto(fila[m.obra]) || "Sin obra" : "Sin obra",
      concepto: m.concepto ? texto(fila[m.concepto]) : "",
      importe,
      categoria: m.categoria ? texto(fila[m.categoria]) || "General" : "General",
    });
  });

  return { validos, descartados };
}

export function filtrarRegistros(
  registros: RegistroGasto[],
  filtros: FiltrosDashboard
): RegistroGasto[] {
  return registros.filter((r) => {
    if (filtros.fechaDesde && r.fecha < filtros.fechaDesde) return false;
    if (filtros.fechaHasta && r.fecha > filtros.fechaHasta) return false;
    if (filtros.lineas.length && !filtros.lineas.includes(r.linea)) return false;
    if (filtros.obras.length && !filtros.obras.includes(r.obra)) return false;
    return true;
  });
}

function topPor(
  registros: RegistroGasto[],
  campo: "linea" | "obra"
): { nombre: string; total: number } | null {
  const map = new Map<string, number>();
  for (const r of registros) {
    map.set(r[campo], (map.get(r[campo]) ?? 0) + r.importe);
  }
  let best: { nombre: string; total: number } | null = null;
  for (const [nombre, total] of map) {
    if (!best || total > best.total) best = { nombre, total };
  }
  return best;
}

export function calcularResumen(registros: RegistroGasto[]): ResumenKpi {
  const total = registros.reduce((s, r) => s + r.importe, 0);
  const dias = new Set(registros.map((r) => r.fecha));
  const diasConDatos = dias.size || 1;
  return {
    total,
    cantidad: registros.length,
    promedioDiario: total / diasConDatos,
    diasConDatos,
    lineaTop: topPor(registros, "linea"),
    obraTop: topPor(registros, "obra"),
  };
}

export function agruparPor(
  registros: RegistroGasto[],
  campo: "linea" | "obra" | "categoria"
): Agrupacion[] {
  const map = new Map<string, { total: number; cantidad: number }>();
  for (const r of registros) {
    const k = r[campo];
    const prev = map.get(k) ?? { total: 0, cantidad: 0 };
    prev.total += r.importe;
    prev.cantidad += 1;
    map.set(k, prev);
  }
  return [...map.entries()]
    .map(([clave, v]) => ({ clave, ...v }))
    .sort((a, b) => b.total - a.total);
}

export function seriePorFecha(registros: RegistroGasto[]): PuntoSerie[] {
  const map = new Map<string, { total: number; cantidad: number }>();
  for (const r of registros) {
    const prev = map.get(r.fecha) ?? { total: 0, cantidad: 0 };
    prev.total += r.importe;
    prev.cantidad += 1;
    map.set(r.fecha, prev);
  }
  return [...map.entries()]
    .map(([fecha, v]) => ({ fecha, ...v }))
    .sort((a, b) => a.fecha.localeCompare(b.fecha));
}

export function rangoFechasDefault(registros: RegistroGasto[]): {
  desde: string;
  hasta: string;
} {
  if (!registros.length) {
    const hoy = new Date().toISOString().slice(0, 10);
    return { desde: hoy, hasta: hoy };
  }
  const fechas = registros.map((r) => r.fecha).sort();
  return { desde: fechas[0], hasta: fechas[fechas.length - 1] };
}

export function valoresUnicos(
  registros: RegistroGasto[],
  campo: "linea" | "obra"
): string[] {
  return [...new Set(registros.map((r) => r[campo]))].sort((a, b) =>
    a.localeCompare(b, "es")
  );
}

export function formatearMoneda(n: number): string {
  return new Intl.NumberFormat("es-AR", {
    style: "currency",
    currency: "ARS",
    maximumFractionDigits: 0,
  }).format(n);
}

export function formatearFecha(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
}

export function formatearFechaHora(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("es-AR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
