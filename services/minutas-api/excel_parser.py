# -*- coding: utf-8 -*-
"""
Lectura del Excel de solicitudes de pedidos (formato pañol).

Los colores del Excel suelen ser formato condicional (openpyxl no siempre los expone);
clasificamos cumplida/pendiente por columnas W (estado ítem) y X (estado solicitud).
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, BinaryIO, Optional

import openpyxl
from openpyxl.worksheet.worksheet import Worksheet

# Mapa de columnas del Excel pañol (hoja "Base datos 2025").
# Los colores visuales suelen ser formato condicional; openpyxl no los expone de forma
# fiable, por eso cumplida/pendiente se deduce de W (ítem) y X (solicitud).
COL = {
    "cant_articulos_pedido": "A",  # cant. ítems de la solicitud
    "solicitante": "B",
    "tipo_solicitud": "C",  # URGENTE | NORMAL
    "maquina_linea": "D",
    "fecha_solicitud": "E",
    "num_odoo": "H",  # nº pedido sistema
    "almacenista": "I",  # iniciales quien carga el pedido
    "num_solicitud": "J",  # nº registro manual (ej. P-3437)
    "codigo": "K",
    "descripcion": "L",
    "cantidad": "M",
    "unidad": "N",
    "precio": "O",
    "total": "P",
    "moneda": "Q",
    "proveedor": "R",
    "oc_rq": "S",
    "fecha_oc": "T",
    "comprador": "U",  # iniciales comprador (en el archivo real; no confundir con V)
    "fecha_envio_compras": "V",
    "estado_item": "W",  # estado real del artículo
    "estado_solicitud": "X",  # estado real de la solicitud
}

# Índice 0-based para iter_rows(values_only=True): A=0, B=1, …
_COL_IDX = {letter: ord(letter) - ord("A") for letter in COL.values()}

HOJAS_PREFERIDAS = ("Base datos 2025", "PP2026", "Base datos 2026")


def _celda_fila(row_vals: tuple[Any, ...] | list[Any], col: str) -> Any:
    idx = _COL_IDX[col]
    if idx >= len(row_vals):
        return None
    return row_vals[idx]


def _texto(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, datetime):
        return f"{val.day}/{val.month}/{val.year}"
    if isinstance(val, date):
        return f"{val.day}/{val.month}/{val.year}"
    return str(val).strip()


def _texto_fecha(val: Any) -> str:
    """Col. E: datetime, date, serial Excel (float) o texto."""
    if val is None:
        return ""
    if isinstance(val, datetime):
        return f"{val.day:02d}/{val.month:02d}/{val.year}"
    if isinstance(val, date):
        return f"{val.day:02d}/{val.month:02d}/{val.year}"
    if isinstance(val, (int, float)) and val > 0:
        try:
            from openpyxl.utils.datetime import from_excel

            d = from_excel(val)
            if isinstance(d, datetime):
                return f"{d.day:02d}/{d.month:02d}/{d.year}"
            if isinstance(d, date):
                return f"{d.day:02d}/{d.month:02d}/{d.year}"
        except (ValueError, OSError, OverflowError):
            pass
    return _texto(val)


def _ref_pedido(num_odoo: str, num_solicitud: str) -> str:
    o, s = num_odoo.strip(), num_solicitud.strip()
    if o and s:
        return f"{o} / {s}"
    return s or o or ""


def normalizar_estado(texto: str) -> str:
    return re.sub(r"\s+", " ", (texto or "").strip().lower())


def solicitud_cumplida(estado_solicitud: str) -> bool:
    e = normalizar_estado(estado_solicitud)
    return e in ("cumplida", "cumplido", "completa", "completo", "cerrada", "cerrado")


def parse_fecha_orden(texto: str) -> tuple[int, int, int]:
    """
    Convierte fecha de solicitud (col. E) a tupla ordenable (año, mes, día).
    Sin fecha válida va al final del listado.
    """
    t = (texto or "").strip()
    if not t:
        return (9999, 12, 31)
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            d = datetime.strptime(t.split()[0], fmt)
            return (d.year, d.month, d.day)
        except ValueError:
            continue
    parts = t.replace("-", "/").split("/")
    if len(parts) == 3:
        try:
            a, b, c = int(parts[0]), int(parts[1]), int(parts[2])
            if a > 31:
                return (a, b, c)
            y = c if c > 31 else c + (2000 if c < 100 else 0)
            return (y, b, a)
        except ValueError:
            pass
    return (9999, 12, 31)


def es_fila_elegible(estado_item: str, estado_solicitud: str) -> bool:
    """
    Reglas del desplegable de reunión:
    - Incluir si X tiene pendiente y W no es Anulado.
    - Incluir si W es Recibido pero la solicitud (X) aún no está cumplida (entrega parcial).
    """
    wi = normalizar_estado(estado_item)
    wx = normalizar_estado(estado_solicitud)
    if wi == "anulado":
        return False
    if "pendiente" in wx:
        return True
    if wi == "recibido" and not solicitud_cumplida(estado_solicitud):
        return True
    return False


@dataclass
class FilaPedido:
    fila_excel: int
    cant_articulos_pedido: str
    solicitante: str
    tipo_solicitud: str
    maquina_linea: str
    fecha_solicitud: str
    ref_pedido: str
    num_odoo: str
    num_solicitud: str
    almacenista: str
    codigo: str
    descripcion: str
    cantidad: str
    unidad: str
    precio: str
    total: str
    moneda: str
    proveedor: str
    oc_rq: str
    fecha_oc: str
    comprador: str
    fecha_envio_compras: str
    estado_item: str
    estado_solicitud: str
    cumplida: bool
    elegible_reunion: bool

    def clave_agrupacion(self) -> str:
        return self.ref_pedido or f"FILA-{self.fila_excel}"


def _elegir_hoja(wb: openpyxl.Workbook, hoja: Optional[str]) -> Worksheet:
    if hoja and hoja in wb.sheetnames:
        return wb[hoja]
    for name in HOJAS_PREFERIDAS:
        if name in wb.sheetnames:
            return wb[name]
    return wb[wb.sheetnames[0]]


def _fila_vacia(row_vals: tuple[Any, ...] | list[Any]) -> bool:
    return not any(_texto(_celda_fila(row_vals, c)) for c in ("B", "J", "L", "W", "X"))


def _parsear_fila(row_num: int, row_vals: tuple[Any, ...] | list[Any]) -> FilaPedido:
    num_odoo = _texto(_celda_fila(row_vals, COL["num_odoo"]))
    num_sol = _texto(_celda_fila(row_vals, COL["num_solicitud"]))
    estado_item = _texto(_celda_fila(row_vals, COL["estado_item"]))
    estado_sol = _texto(_celda_fila(row_vals, COL["estado_solicitud"]))
    return FilaPedido(
        fila_excel=row_num,
        cant_articulos_pedido=_texto(_celda_fila(row_vals, COL["cant_articulos_pedido"])),
        solicitante=_texto(_celda_fila(row_vals, COL["solicitante"])),
        tipo_solicitud=_texto(_celda_fila(row_vals, COL["tipo_solicitud"])),
        maquina_linea=_texto(_celda_fila(row_vals, COL["maquina_linea"])),
        fecha_solicitud=_texto_fecha(_celda_fila(row_vals, COL["fecha_solicitud"])),
        ref_pedido=_ref_pedido(num_odoo, num_sol),
        num_odoo=num_odoo,
        num_solicitud=num_sol,
        almacenista=_texto(_celda_fila(row_vals, COL["almacenista"])),
        codigo=_texto(_celda_fila(row_vals, COL["codigo"])),
        descripcion=_texto(_celda_fila(row_vals, COL["descripcion"])),
        cantidad=_texto(_celda_fila(row_vals, COL["cantidad"])),
        unidad=_texto(_celda_fila(row_vals, COL["unidad"])),
        precio=_texto(_celda_fila(row_vals, COL["precio"])),
        total=_texto(_celda_fila(row_vals, COL["total"])),
        moneda=_texto(_celda_fila(row_vals, COL["moneda"])),
        proveedor=_texto(_celda_fila(row_vals, COL["proveedor"])),
        oc_rq=_texto(_celda_fila(row_vals, COL["oc_rq"])),
        fecha_oc=_texto_fecha(_celda_fila(row_vals, COL["fecha_oc"])),
        comprador=_texto(_celda_fila(row_vals, COL["comprador"])),
        fecha_envio_compras=_texto_fecha(_celda_fila(row_vals, COL["fecha_envio_compras"])),
        estado_item=estado_item,
        estado_solicitud=estado_sol,
        cumplida=solicitud_cumplida(estado_sol),
        elegible_reunion=es_fila_elegible(estado_item, estado_sol),
    )


def _completar_fechas_pedido(filas: list[FilaPedido]) -> None:
    """Filas de ítems suelen tener col. E vacía; heredan la fecha del mismo pedido."""
    cache: dict[str, str] = {}
    for f in filas:
        ref = f.clave_agrupacion()
        if f.fecha_solicitud:
            cache[ref] = f.fecha_solicitud
        elif ref in cache:
            f.fecha_solicitud = cache[ref]


def parsear_excel(
    source: BinaryIO | bytes,
    hoja: Optional[str] = None,
    fila_inicio: int = 2,
    max_filas_vacias_seguidas: int = 40,
) -> tuple[str, list[FilaPedido]]:
    """
    Lee el Excel fila a fila con iter_rows (evita recorrer max_row=1M que congela el parser).
    """
    if isinstance(source, bytes):
        source = io.BytesIO(source)
    wb = openpyxl.load_workbook(source, data_only=True, read_only=True)
    ws = _elegir_hoja(wb, hoja)
    nombre_hoja = ws.title
    filas: list[FilaPedido] = []
    vacias_seguidas = 0

    for row_num, row_vals in enumerate(
        ws.iter_rows(min_row=fila_inicio, values_only=True),
        start=fila_inicio,
    ):
        if _fila_vacia(row_vals):
            vacias_seguidas += 1
            if vacias_seguidas >= max_filas_vacias_seguidas:
                break
            continue
        vacias_seguidas = 0
        filas.append(_parsear_fila(row_num, row_vals))

    _completar_fechas_pedido(filas)
    wb.close()
    return nombre_hoja, filas


def agrupar_por_pedido(filas: list[FilaPedido]) -> dict[str, list[FilaPedido]]:
    grupos: dict[str, list[FilaPedido]] = {}
    for f in filas:
        grupos.setdefault(f.clave_agrupacion(), []).append(f)
    return grupos


def resumen_importacion(filas: list[FilaPedido]) -> dict[str, int]:
    elegibles = [f for f in filas if f.elegible_reunion]
    return {
        "total_filas": len(filas),
        "elegibles": len(elegibles),
        "cumplidas": sum(1 for f in filas if f.cumplida),
        "pedidos_elegibles": len(agrupar_por_pedido(elegibles)),
        "pedidos_total": len(agrupar_por_pedido(filas)),
    }
