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

function tablaPedidos(titulo: string, filas: string[][]): string {
  const borde = "#999";
  const th = COLUMNAS_MAIL.map(
    (h) =>
      `<th style="padding:6px;background:#1F4E78;color:#fff;border:1px solid ${borde};">${esc(h)}</th>`,
  ).join("");

  const trs = filas
    .map((fila) => {
      const tds = fila
        .map(
          (c) =>
            `<td style="padding:4px 8px;border:1px solid ${borde};background:#fff;color:#1a1a1a;">${esc(c || "—")}</td>`,
        )
        .join("");
      return `<tr>${tds}</tr>`;
    })
    .join("");

  return (
    `<p style="font-family:Arial,sans-serif;font-size:14px;margin:16px 0 8px 0;color:#222;">` +
    `<b>${esc(titulo)}</b></p>` +
    `<table style="border-collapse:collapse;font-family:Arial,sans-serif;font-size:12px;margin-bottom:16px;border:2px solid ${borde};">` +
    `<thead><tr>${th}</tr></thead><tbody>${trs || `<tr><td colspan="${COLUMNAS_MAIL.length}" style="padding:8px;border:1px solid ${borde};">Sin pedidos</td></tr>`}</tbody></table>`
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

  const filas = pedidos
    .filter((p) => Number(p.activo) === 1)
    .map((p) => {
      const novDb = novedadesReunion.find((n) => n.pedido_id === p.id);
      const novLocal = (sesion.borradoresNovedad[p.id] || "").trim();
      // Prioridad: borrador de esta reunión (lo que se ve en pantalla) → DB
      const novedadTexto = novLocal || novDb?.texto || "";
      return [
        fmtFecha(p.fecha),
        p.n_pedido,
        p.oc,
        p.pedido,
        novedadTexto,
        labelImportancia(p.importancia),
        labelEstado(p.estado),
      ];
    });

  cuerpoTxt += "Pedidos tratados:\n";
  for (const fila of filas) {
    cuerpoTxt +=
      `• ${fila[0]} | Nº ${fila[1] || "—"} | OC ${fila[2] || "—"} | ${fila[3] || "—"}` +
      ` | ${fila[4] || "—"} | ${fila[5]} | ${fila[6]}\n`;
  }
  cuerpoTxt += "\n";
  cuerpoHtml += tablaPedidos("Pedidos tratados en la reunión", filas);

  if (sesion.notasGenerales.trim()) {
    cuerpoTxt += `Notas generales:\n${sesion.notasGenerales.trim()}\n`;
    cuerpoHtml +=
      `<p style="font-family:Arial,sans-serif;font-size:14px;margin:16px 0 8px 0;color:#222;"><b>Notas generales</b></p>` +
      `<p style="font-family:Arial,sans-serif;font-size:12px;white-space:pre-wrap;color:#333;">${esc(sesion.notasGenerales.trim())}</p>`;
  }

  return { asunto, cuerpo_html: cuerpoHtml, cuerpo_texto: cuerpoTxt };
}
