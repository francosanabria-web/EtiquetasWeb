import { labelEstado, labelImportancia, type Pedido } from "../../api/minutaClient";
import type { MinutaSesionLocal } from "./types";
import { fmtFecha } from "./types";

function esc(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

const COLUMNAS_MAIL = [
  "Fecha solicitud",
  "Nº solicitud",
  "Nº OC",
  "Descripción",
  "Novedades",
  "Importancia",
  "Estado",
];

function colorImportancia(imp: string): { bg: string; color: string; border: string } {
  const v = (imp || "").toLowerCase();
  if (v === "critico") return { bg: "#fef2f2", color: "#991b1b", border: "#fecaca" };
  if (v === "urgente") return { bg: "#fffbeb", color: "#92400e", border: "#fde68a" };
  return { bg: "#ecfdf5", color: "#065f46", border: "#a7f3d0" };
}

function tablaPedidos(titulo: string, filas: string[][], importancias: string[]): string {
  const borde = "#d1d5db";
  const th = COLUMNAS_MAIL.map(
    (h) =>
      `<th style="padding:8px 10px;background:#1F4E78;color:#fff;border:1px solid ${borde};font-weight:700;white-space:nowrap;font-size:12px;text-align:left;">${esc(h)}</th>`,
  ).join("");

  const trs = filas
    .map((fila, idx) => {
      const imp = (importancias[idx] || "").toLowerCase();
      const c = colorImportancia(imp);
      const tds = fila
        .map((cell, colIdx) => {
          const isImpCol = colIdx === 5;
          const bg = isImpCol ? c.bg : "#fff";
          const col = isImpCol ? c.color : "#1a202c";
          const bdr = isImpCol ? c.border : borde;
          const fw = isImpCol ? "font-weight:700;" : "";
          return `<td style="padding:6px 10px;border:1px solid ${bdr};background:${bg};color:${col};${fw}font-size:12px;vertical-align:top;">${esc(cell || "—")}</td>`;
        })
        .join("");
      const leftBorder = `border-left:4px solid ${c.border};`;
      return `<tr style="${leftBorder}">${tds}</tr>`;
    })
    .join("");

  return (
    `<p style="font-family:Arial,sans-serif;font-size:13px;margin:14px 0 8px 0;color:#1a5276;"><b>${esc(titulo)}</b></p>` +
    `<table style="border-collapse:collapse;font-family:Arial,sans-serif;font-size:12px;margin-bottom:16px;border:2px solid ${borde};width:100%;background:#fff;">` +
    `<thead><tr>${th}</tr></thead><tbody>${trs || `<tr><td colspan="${COLUMNAS_MAIL.length}" style="padding:12px;border:1px solid ${borde};text-align:center;color:#64748b;">Sin pedidos</td></tr>`}</tbody></table>`
  );
}

export function buildMinutaMail(
  sesion: MinutaSesionLocal,
  pedidos: Pedido[],
  novedadesReunion: { pedido_id: number; texto: string }[],
  meta?: { titulo?: string; sector?: string },
): {
  asunto: string;
  cuerpo_html: string;
  cuerpo_texto: string;
} {
  const comprometidos = sesion.sectoresComprometidos.trim() || meta?.sector || "—";
  const fecha = sesion.fecha.trim() || "—";
  const titulo = meta?.titulo?.trim() || "Minuta de reunión";
  const asunto = `${titulo} — ${comprometidos} (${fmtFecha(fecha)})`;

  const introTxt = [
    "MINUTA DE REUNIÓN — PAÑOL",
    `Título: ${titulo}`,
    `Fecha reunión: ${fmtFecha(fecha)}`,
    `Sectores comprometidos: ${comprometidos}`,
    "",
  ];

  const introHtml =
    `<p style="font-family:Arial,sans-serif;font-size:13px;color:#1a5276;">` +
    `<b>${esc(titulo)}</b> — <b>${esc(fmtFecha(fecha))}</b>` +
    ` — Sectores comprometidos: <b>${esc(comprometidos)}</b></p>`;

  let cuerpoTxt = introTxt.join("\n");
  let cuerpoHtml = introHtml;

  // Ordenar exactamente como está en el módulo (por orden manual, drag)
  const pedidosOrdenados = [...pedidos].sort((a, b) => (Number((a as unknown as { orden?: number }).orden) || 0) - (Number((b as unknown as { orden?: number }).orden) || 0));
  const importancias: string[] = [];
  const filas = pedidosOrdenados
    .filter((p) => Number(p.activo) === 1)
    // Filtrar filas completamente vacías (sin pedido, sin n_pedido, sin oc y sin consultas) para no mandar renglones vacíos
    .filter((p) => {
      const hasPedido = (p.pedido || "").trim().length > 0;
      const hasNPedido = (p.n_pedido || "").trim().length > 0;
      const hasOC = (p.oc || "").trim().length > 0;
      const hasConsultas = (p.consultas || "").trim().length > 0;
      const hasNovedad = (p as unknown as { ultima_novedad?: string }).ultima_novedad?.trim() || (sesion.borradoresNovedad[p.id] || "").trim();
      return hasPedido || hasNPedido || hasOC || hasConsultas || Boolean(hasNovedad);
    })
    .map((p) => {
      importancias.push(p.importancia);
      const novDb = novedadesReunion.find((n) => n.pedido_id === p.id);
      const novLocal = (sesion.borradoresNovedad[p.id] || "").trim();
      const novedadTexto = novLocal || novDb?.texto || "";
      // Si pedido está vacío pero hay consultas, usar consultas como descripción para no mandar vacío
      const descripcion = (p.pedido || "").trim() || (p.consultas || "").trim() || "—";
      return [
        fmtFecha(p.fecha),
        p.n_pedido,
        p.oc,
        descripcion,
        novedadTexto,
        labelImportancia(p.importancia),
        labelEstado(p.estado),
      ];
    });

  cuerpoTxt += "Pedidos tratados (orden del módulo):\n";
  for (const fila of filas) {
    cuerpoTxt += `• ${fila[0]} | Nº ${fila[1] || "—"} | OC ${fila[2] || "—"} | ${fila[3] || "—"} | ${fila[4] || "—"} | ${fila[5]} | ${fila[6]}\n`;
  }
  cuerpoTxt += "\n";
  cuerpoHtml += tablaPedidos("Pedidos tratados en la reunión", filas, importancias);

  if (sesion.notasGenerales.trim()) {
    cuerpoTxt += `Notas generales:\n${sesion.notasGenerales.trim()}\n`;
    cuerpoHtml +=
      `<p style="font-family:Arial,sans-serif;font-size:13px;margin:14px 0 8px 0;color:#1a5276;"><b>Notas generales</b></p>` +
      `<p style="font-family:Arial,sans-serif;font-size:12px;white-space:pre-wrap;color:#2d3748;background:#f7fafc;border:1px solid #e2e8f0;border-radius:8px;padding:12px;">${esc(sesion.notasGenerales.trim())}</p>`;
  }

  return { asunto, cuerpo_html: cuerpoHtml, cuerpo_texto: cuerpoTxt };
}
