# -*- coding: utf-8 -*-
"""
Lectura SOLO LECTURA de master_codes.xlsx — hoja correos.
No escribe ni modifica el archivo bajo ningún concepto.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from openpyxl import load_workbook

from models import Contacto

DEFAULT_DIR = (
    r"G:\Unidades compartidas\Mantenimiento\MANTENIMIENTO  OZLA 2024-2025"
    r"\17. Pañol\pañol v5.0"
)


def _ruta_master_codes() -> Path:
    explicit = os.environ.get("MASTER_CODES_PATH", "").strip()
    if explicit:
        p = Path(explicit)
        if p.is_dir():
            for name in ("master_codes.xlsx", "base_datos.xlsx"):
                cand = p / name
                if cand.is_file():
                    return cand
        if p.is_file():
            return p
    base = Path(os.environ.get("PANOL_DATA_DIR", DEFAULT_DIR))
    for name in ("master_codes.xlsx", "base_datos.xlsx"):
        cand = base / name
        if cand.is_file():
            return cand
    return base / "master_codes.xlsx"


def _norm_header(val: object) -> str:
    return str(val or "").strip().lower()


def _celda_str(val: object) -> str:
    if val is None:
        return ""
    s = str(val).strip()
    return "" if s.lower() in ("nan", "none") else s


def leer_filas_correos() -> list[dict[str, str]]:
    path = _ruta_master_codes()
    if not path.is_file():
        raise FileNotFoundError(f"No se encontró master_codes: {path}")

    wb = load_workbook(path, read_only=True, data_only=True)
    sheet_name = None
    for name in wb.sheetnames:
        if name.strip().lower() == "correos":
            sheet_name = name
            break
    if sheet_name is None:
        wb.close()
        raise ValueError(f"Hoja 'correos' no encontrada en {path.name}")

    ws = wb[sheet_name]
    rows = ws.iter_rows(values_only=True)
    try:
        header_row = next(rows)
    except StopIteration:
        wb.close()
        return []

    headers = [_norm_header(h) for h in header_row]
    if "destinatario" not in headers:
        wb.close()
        raise ValueError("La hoja correos no tiene columna 'destinatario'.")

    idx = {h: i for i, h in enumerate(headers)}
    out: list[dict[str, str]] = []
    for row_num, row in enumerate(rows, start=2):
        if row is None:
            continue
        cells = list(row)
        item = {
            "remitente": _celda_str(cells[idx["remitente"]]) if "remitente" in idx and idx["remitente"] < len(cells) else "",
            "password": _celda_str(cells[idx["password"]]) if "password" in idx and idx["password"] < len(cells) else "",
            "destinatario": _celda_str(cells[idx["destinatario"]]) if idx["destinatario"] < len(cells) else "",
            "tipo": _celda_str(cells[idx["tipo"]]) if "tipo" in idx and idx["tipo"] < len(cells) else "",
            "nombre": _celda_str(cells[idx["nombre"]]) if "nombre" in idx and idx["nombre"] < len(cells) else "",
            "_row": str(row_num),
        }
        out.append(item)
    wb.close()
    return out


def _expandir_emails(celda: str) -> list[str]:
    out: list[str] = []
    for parte in re.split(r"[,;]", celda):
        e = parte.strip()
        if e and "@" in e and e not in out:
            out.append(e)
    return out


def listar_contactos() -> list[Contacto]:
    filas = leer_filas_correos()
    contactos: list[Contacto] = []
    for row in filas:
        celda = row.get("destinatario", "")
        if not celda:
            continue
        tipo = row.get("tipo") or None
        emails = _expandir_emails(celda)
        for email in emails:
            nombre = (row.get("nombre") or "").strip()
            etiqueta = f"{nombre} <{email}>" if nombre else celda
            contactos.append(
                Contacto(
                    id=f"row-{row['_row']}-{email}",
                    email=email,
                    etiqueta=etiqueta,
                    tipo=tipo,
                )
            )
    return contactos


def fila_smtp_excel() -> tuple[str, str] | None:
    """Primera fila con remitente y password (solo lectura)."""
    filas = leer_filas_correos()
    if not filas:
        return None
    row = filas[0]
    remitente = row.get("remitente", "")
    password = row.get("password", "")
    if remitente and password:
        return remitente, password
    return None
