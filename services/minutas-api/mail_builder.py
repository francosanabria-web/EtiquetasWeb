# -*- coding: utf-8 -*-
"""Plantillas HTML de mail (mismo estilo que almacen_gui.py)."""

from __future__ import annotations

from html import escape
from typing import Any, Optional


def tabla_html_coloreada(
    titulo: str,
    cabeceras: list[str],
    filas: list[tuple[str, tuple[Any, ...]]],
) -> str:
    borde = "#999"
    th = "".join(
        f'<th style="padding:6px;background:#1F4E78;color:#fff;border:1px solid {borde};">'
        f"{escape(str(h))}</th>"
        for h in cabeceras
    )
    trs = []
    for bg, fila in filas:
        tds = "".join(
            f'<td style="padding:4px 8px;border:1px solid {borde};background:{bg};color:#1a1a1a;">'
            f"{escape(str(c))}</td>"
            for c in fila
        )
        trs.append(f"<tr>{tds}</tr>")
    return (
        f'<p style="font-family:Arial,sans-serif;font-size:14px;margin:16px 0 8px 0;color:#222;">'
        f"<b>{escape(titulo)}</b></p>"
        f'<table style="border-collapse:collapse;font-family:Arial,sans-serif;font-size:12px;'
        f'margin-bottom:16px;border:2px solid {borde};">'
        f"<thead><tr>{th}</tr></thead><tbody>{''.join(trs)}</tbody></table>"
    )


def color_estado_item(estado_item: str, estado_solicitud: str) -> str:
    ei = (estado_item or "").lower()
    es = (estado_solicitud or "").lower()
    if "anulado" in ei:
        return "#E7E6E6"
    if "recibido" in ei and "pendiente" in es:
        return "#C6EFCE"
    if "pendiente" in es:
        return "#FFEB9C"
    if "cumplid" in es:
        return "#D9D9D9"
    return "#FFFFFF"


def construir_mail_minuta_excel(
    semana_iso: str,
    fecha: str,
    responsable: Optional[str],
    pedidos: list[dict[str, Any]],
    notas: list[dict[str, Any]],
    notas_generales: Optional[str],
) -> tuple[str, str]:
    intro_txt = [
        "MINUTA DE REUNIÓN — SEGUIMIENTO DE PEDIDOS",
        f"Semana: {semana_iso}",
        f"Fecha: {fecha}",
    ]
    if responsable:
        intro_txt.append(f"Responsable: {responsable}")
    intro_txt.extend(["", f"Pedidos tratados: {len(pedidos)}", ""])

    notas_por_fila = {n["fila_id"]: n for n in notas}
    filas_html: list[tuple[str, tuple[Any, ...]]] = []
    cab = [
        "Fecha sol.",
        "Pedido",
        "Solicitante",
        "Tipo",
        "Código",
        "Descripción",
        "Cant.",
        "Estado ítem",
        "Estado solicitud",
        "OC/RQ",
        "Actualización reunión",
    ]

    for ped in pedidos:
        for f in ped.get("filas", []):
            nota = notas_por_fila.get(f["id"])
            act = f"{nota.get('autor') or '—'}: {nota['texto']}" if nota else ""
            intro_txt.append(
                f"• {f.get('ref_pedido')} | {f.get('codigo')} | W={f.get('estado_item')} X={f.get('estado_solicitud')}"
            )
            if act:
                intro_txt.append(f"    → {act}")
            bg = color_estado_item(str(f.get("estado_item", "")), str(f.get("estado_solicitud", "")))
            filas_html.append(
                (
                    bg,
                    (
                        f.get("fecha_solicitud"),
                        f.get("ref_pedido"),
                        f.get("solicitante"),
                        f.get("tipo_solicitud"),
                        f.get("codigo"),
                        f.get("descripcion"),
                        f.get("cantidad"),
                        f.get("estado_item"),
                        f.get("estado_solicitud"),
                        f.get("oc_rq"),
                        act or "—",
                    ),
                )
            )

    if notas_generales:
        intro_txt.extend(["", "Notas generales:", notas_generales])

    intro_html = (
        f'<p style="font-family:Arial,sans-serif;font-size:13px;color:#1a5276;">'
        f"Minuta de reunión — <b>{escape(semana_iso)}</b> ({escape(fecha)})"
        f"{f' — {escape(responsable)}' if responsable else ''}</p>"
    )
    tabla = tabla_html_coloreada("Pedidos tratados en la reunión", cab, filas_html)
    notas_html = ""
    if notas_generales:
        notas_html = (
            f'<p style="font-family:Arial,sans-serif;"><b>Notas generales</b><br/>'
            f"{escape(notas_generales)}</p>"
        )
    html = (
        f'<html><body style="font-family:Arial,sans-serif;color:#1a1a1a;">'
        f"{intro_html}{tabla}{notas_html}"
        f'<p style="font-size:11px;color:#666;">SistemasPañol — Módulo Minutas</p></body></html>'
    )
    return "\n".join(intro_txt), html
