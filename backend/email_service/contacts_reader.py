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


def _listar_desde_personal() -> list[Contacto] | None:
    """Intenta leer contactos desde el módulo Personal (MariaDB panol.personal).

    Retorna None si no hay DB o si falla, para que el caller haga fallback a Excel.
    """
    try:
        import pymysql
        from pymysql.cursors import DictCursor

        # Reutilizar credenciales del servicio personal (mismo DB_HOST/PORT/USER/PASS/NAME)
        import os

        host = os.environ.get("DB_HOST", os.environ.get("PERSONAL_DB_HOST", "127.0.0.1"))
        port = int(os.environ.get("DB_PORT", os.environ.get("PERSONAL_DB_PORT", "3306")))
        user = os.environ.get("DB_USER", os.environ.get("PERSONAL_DB_USER", "root"))
        password = os.environ.get("DB_PASSWORD", os.environ.get("PERSONAL_DB_PASSWORD", ""))
        name = os.environ.get("DB_NAME", os.environ.get("PERSONAL_DB_NAME", "panol"))
        conn = pymysql.connect(
            host=host, port=port, user=user, password=password, database=name, charset="utf8mb4", cursorclass=DictCursor
        )
        try:
            with conn.cursor() as cur:
                # Personal activo con email, ordenado por nombre
                cur.execute(
                    """
                    SELECT p.id, p.nombre, p.email, p.tipo, a.nombre AS area_nombre
                    FROM personal p
                    LEFT JOIN areas a ON a.id = p.area_id
                    WHERE p.activo = 1 AND p.email IS NOT NULL AND TRIM(p.email) <> ''
                    ORDER BY p.nombre ASC
                    """
                )
                rows = cur.fetchall()
                if not rows:
                    return []
                contactos: list[Contacto] = []
                for r in rows:
                    email_raw = (r.get("email") or "").strip()
                    # Soportar múltiples emails separados por coma/punto y coma en el mismo campo
                    for email in _expandir_emails(email_raw):
                        nombre = (r.get("nombre") or "").strip()
                        tipo = (r.get("tipo") or None)
                        # Etiqueta más rica: "Nombre — Área <email>"
                        area = (r.get("area_nombre") or "").strip()
                        if nombre and area:
                            etiqueta = f"{nombre} — {area} <{email}>"
                        elif nombre:
                            etiqueta = f"{nombre} <{email}>"
                        else:
                            etiqueta = email
                        contactos.append(
                            Contacto(
                                id=f"personal-{r['id']}-{email}",
                                email=email,
                                etiqueta=etiqueta,
                                tipo=tipo,
                            )
                        )
                return contactos
        finally:
            try:
                conn.close()
            except:
                pass
    except Exception:
        return None


def listar_contactos() -> list[Contacto]:
    # 1. Intentar fuente primaria: módulo Personal (MariaDB)
    contactos_personal = _listar_desde_personal()
    if contactos_personal is not None and len(contactos_personal) > 0:
        return contactos_personal
    # 2. Fallback legacy: master_codes.xlsx hoja correos (si Personal está vacío o falla)
    try:
        filas = leer_filas_correos()
    except (FileNotFoundError, ValueError):
        # Si ni Personal ni Excel tienen datos, retornar lo que haya (vacío o personal vacío)
        return contactos_personal if contactos_personal is not None else []
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
    # Si Personal devolvió lista vacía pero Excel tiene datos, usar Excel; si ambos vacíos, devolver vacío
    if contactos and (contactos_personal is not None and len(contactos_personal) == 0):
        return contactos
    return contactos if contactos else (contactos_personal or [])


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
