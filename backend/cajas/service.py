# -*- coding: utf-8 -*-
"""Logica de negocio del modulo Cajas de Herramientas.

Implementa:
- Validacion de UPPER(TRIM(codigo))
- Coercion "" -> NULL para descripcion, ubicacion, articulo_codigo
- Manejo de IntegrityError -> 409 Conflict
- Verificacion de permisos JWT
"""

from __future__ import annotations

from typing import Any

from db import verificar_permiso, init_db
from store import (
    listar_cajas, obtener_caja, crear_caja, actualizar_caja, eliminar_caja,
    listar_herramientas, obtener_herramienta, crear_herramienta, actualizar_herramienta, eliminar_herramienta,
    crear_inventario_txn, obtener_inventario, listar_inventarios, actualizar_estado_inventario, eliminar_inventario,
)


def _requerir_permiso(token: str, permiso: str) -> dict[str, Any] | None:
    """Verifica JWT y permiso. Retorna payload o None."""
    resultado = verificar_permiso(token, permiso)
    if resultado is None:
        return None
    return resultado


def health_payload() -> dict[str, Any]:
    return {"status": "ok", "service": "cajas", "version": "1.0.0"}


# --------------------------------------------------------------------------- #
# Cajas Cajas
# --------------------------------------------------------------------------- #
def get_cajas_list(token: str, params: dict[str, Any]) -> dict[str, Any] | tuple[str, int]:
    if not _requerir_permiso(token, "cajas:lectura"):
        return ("No autorizado", 401)
    q = str(params.get("q", ""))
    activo = params.get("activo")
    limit = int(params.get("limit", 50))
    offset = int(params.get("offset", 0))
    if activo is not None:
        activo = 1 if str(activo) == "true" else 0
    return listar_cajas(q=q, activo=activo, limit=limit, offset=offset)


def get_caja_by_id(token: str, caja_id: int) -> dict[str, Any] | tuple[str, int]:
    if not _requerir_permiso(token, "cajas:lectura"):
        return ("No autorizado", 401)
    caja = obtener_caja(caja_id)
    if not caja:
        return ("No encontrado", 404)
    return caja


def create_caja(token: str, data: dict[str, Any]) -> dict[str, Any] | tuple[str, int]:
    if not _requerir_permiso(token, "cajas:escritura"):
        return ("No autorizado", 401)
    try:
        return crear_caja(data)
    except ValueError as e:
        msg = str(e)
        if "unicidad" in msg.lower() or "ya existe" in msg.lower():
            return (msg, 409)
        return (msg, 400)


def update_caja(token: str, caja_id: int, data: dict[str, Any]) -> dict[str, Any] | tuple[str, int]:
    if not _requerir_permiso(token, "cajas:escritura"):
        return ("No autorizado", 401)
    try:
        result = actualizar_caja(caja_id, data)
        if result is None:
            return ("No encontrado", 404)
        return result
    except ValueError as e:
        msg = str(e)
        if "unicidad" in msg.lower() or "ya existe" in msg.lower():
            return (msg, 409)
        return (msg, 400)


def delete_caja(token: str, caja_id: int) -> dict[str, Any] | tuple[str, int]:
    if not _requerir_permiso(token, "cajas:escritura"):
        return ("No autorizado", 401)
    try:
        result = eliminar_caja(caja_id)
        if result is None:
            return ("No encontrado", 404)
        return result
    except ValueError as e:
        return (str(e), 409)


# --------------------------------------------------------------------------- #
# Cajas Herramientas
# --------------------------------------------------------------------------- #
def get_herramientas_list(token: str, params: dict[str, Any]) -> dict[str, Any] | tuple[str, int]:
    if not _requerir_permiso(token, "cajas:lectura"):
        return ("No autorizado", 401)
    q = str(params.get("q", ""))
    categoria = str(params.get("categoria", ""))
    limit = int(params.get("limit", 50))
    offset = int(params.get("offset", 0))
    return listar_herramientas(q=q, categoria=categoria, limit=limit, offset=offset)


def get_herramienta_by_id(token: str, herramienta_id: int) -> dict[str, Any] | tuple[str, int]:
    if not _requerir_permiso(token, "cajas:lectura"):
        return ("No autorizado", 401)
    herramienta = obtener_herramienta(herramienta_id)
    if not herramienta:
        return ("No encontrado", 404)
    return herramienta


def create_herramienta(token: str, data: dict[str, Any]) -> dict[str, Any] | tuple[str, int]:
    if not _requerir_permiso(token, "cajas:escritura"):
        return ("No autorizado", 401)
    try:
        return crear_herramienta(data)
    except ValueError as e:
        msg = str(e)
        if "unicidad" in msg.lower() or "ya existe" in msg.lower():
            return (msg, 409)
        return (msg, 400)


def update_herramienta(token: str, herramienta_id: int, data: dict[str, Any]) -> dict[str, Any] | tuple[str, int]:
    if not _requerir_permiso(token, "cajas:escritura"):
        return ("No autorizado", 401)
    try:
        result = actualizar_herramienta(herramienta_id, data)
        if result is None:
            return ("No encontrado", 404)
        return result
    except ValueError as e:
        msg = str(e)
        if "unicidad" in msg.lower() or "ya existe" in msg.lower():
            return (msg, 409)
        return (msg, 400)


def delete_herramienta(token: str, herramienta_id: int) -> dict[str, Any] | tuple[str, int]:
    if not _requerir_permiso(token, "cajas:escritura"):
        return ("No autorizado", 401)
    try:
        result = eliminar_herramienta(herramienta_id)
        if result is None:
            return ("No encontrado", 404)
        return result
    except ValueError as e:
        return (str(e), 409)


# --------------------------------------------------------------------------- #
# Cajas Inventarios
# --------------------------------------------------------------------------- #
def get_inventarios_list(token: str, params: dict[str, Any]) -> dict[str, Any] | tuple[str, int]:
    if not _requerir_permiso(token, "cajas:lectura"):
        return ("No autorizado", 401)
    caja_id = params.get("caja_id")
    periodo = params.get("periodo")
    estado = params.get("estado")
    q = str(params.get("q", ""))
    limit = int(params.get("limit", 50))
    offset = int(params.get("offset", 0))
    try:
        return listar_inventarios(
            caja_id=int(caja_id) if caja_id else None,
            periodo=periodo,
            estado=estado,
            q=q,
            limit=limit,
            offset=offset,
        )
    except ValueError as e:
        return (str(e), 400)


def get_inventario_by_id(token: str, inv_id: int) -> dict[str, Any] | tuple[str, int]:
    if not _requerir_permiso(token, "cajas:lectura"):
        return ("No autorizado", 401)
    inv = obtener_inventario(inv_id)
    if not inv:
        return ("No encontrado", 404)
    return inv


def create_inventario(token: str, data: dict[str, Any]) -> dict[str, Any] | tuple[str, int]:
    if not _requerir_permiso(token, "cajas:escritura"):
        return ("No autorizado", 401)
    try:
        return crear_inventario_txn(data)
    except ValueError as e:
        msg = str(e)
        if "ya existe inventario" in msg.lower() or "periodo" in msg.lower():
            return (msg, 409)
        if "no existe" in msg.lower() or "obligatorio" in msg.lower() or "invalido" in msg.lower():
            return (msg, 400)
        return (msg, 400)


def update_inventario_estado(token: str, inv_id: int, estado: str) -> dict[str, Any] | tuple[str, int]:
    if not _requerir_permiso(token, "cajas:escritura"):
        return ("No autorizado", 401)
    if estado not in ("borrador", "cerrado"):
        return ("estado must be 'borrador' or 'cerrado'", 400)
    try:
        result = actualizar_estado_inventario(inv_id, estado)
        if result is None:
            return ("No encontrado", 404)
        return result
    except ValueError as e:
        msg = str(e)
        if "revertir" in msg.lower():
            return (msg, 400)
        return (msg, 400)


def delete_inventario(token: str, inv_id: int) -> dict[str, Any] | tuple[str, int]:
    if not _requerir_permiso(token, "cajas:escritura"):
        return ("No autorizado", 401)
    try:
        result = eliminar_inventario(inv_id)
        if result is None:
            return ("No encontrado", 404)
        return result
    except ValueError as e:
        msg = str(e)
        if "cerrado" in msg.lower():
            return (msg, 409)
        return (msg, 400)
