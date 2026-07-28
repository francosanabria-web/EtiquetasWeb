# -*- coding: utf-8 -*-
"""Generación PDF de solicitud de pedido."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from fpdf import FPDF
from fpdf.enums import XPos, YPos


def _safe(s: Any, max_len: int | None = None) -> str:
    text = str(s or "").strip() or "-"
    text = text.encode("latin-1", "replace").decode("latin-1")
    if max_len and len(text) > max_len:
        return text[: max_len - 1] + "."
    return text


def generar_pdf(solicitud: dict[str, Any]) -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    def linea(txt: str) -> None:
        pdf.cell(0, 8, txt, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Solicitud de pedidos - Panol", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 11)
    linea(f"ID interno: #{solicitud.get('id')}")
    if solicitud.get("n_tr"):
        linea(f"Nro TR: {_safe(solicitud.get('n_tr'))}")
    if solicitud.get("n_pedido"):
        linea(f"Nro pedido: {_safe(solicitud.get('n_pedido'))}")
    pdf.ln(2)

    cabecera = [
        ("Tipo", solicitud.get("tipo")),
        ("Estado", solicitud.get("estado")),
        ("Cuenta contable", solicitud.get("cuenta_contable")),
        ("Solicitante", solicitud.get("solicitante")),
        ("Proveedor", solicitud.get("proveedor")),
        ("Remito", solicitud.get("remito_nro")),
        ("Presupuesto", solicitud.get("presupuesto_nro")),
        ("Creado", solicitud.get("creado_en")),
        ("Notas", solicitud.get("notas")),
    ]
    for label, val in cabecera:
        if label in ("Proveedor", "Remito", "Presupuesto", "Notas") and not str(val or "").strip():
            continue
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(45, 7, _safe(label) + ":", border=0, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 7, _safe(val), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    items = solicitud.get("items") or []
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, f"Items ({len(items)})", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    col_w = [26, 70, 16, 16, 52]
    headers = ["Codigo", "Descripcion", "Cant.", "Unid.", "Area / maquina"]
    pdf.set_font("Helvetica", "B", 8)
    for w, h in zip(col_w, headers):
        pdf.cell(w, 7, h, border=1, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.ln()

    pdf.set_font("Helvetica", "", 8)
    for it in items:
        vals = [
            _safe(it.get("codigo"), 14),
            _safe(it.get("descripcion"), 42),
            _safe(it.get("cantidad"), 8),
            _safe(it.get("unidad"), 6),
            _safe(it.get("area"), 28),
        ]
        for w, v in zip(col_w, vals):
            pdf.cell(w, 7, v, border=1, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.ln()

    pdf.ln(6)
    pdf.set_font("Helvetica", "I", 9)
    pdf.multi_cell(0, 5, "Documento de solicitud de pedido - Panol.")

    out = BytesIO()
    pdf.output(out)
    return out.getvalue()
