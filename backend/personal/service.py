# -*- coding: utf-8 -*-
"""Lógica de negocio del módulo Personal.

Implementa:
- Validación de ENUM tipo
- Normalización UPPER(TRIM(nombre))
- Coerción "" / " " → SQL NULL para legajo y email
- Manejo de IntegrityError → 409 Conflict
- Verificación de permisos JWT
"""

from __future__ import annotations

from typing import Any

from db import verificar_permiso, init_db
from store import (
    listar_areas, obtener_area, listar_personal, obtener_personal,
    crear_personal, actualizar_personal, eliminar_personal,
    get_mail_prefs, set_mail_prefs, list_prefs,
)

TIPOS_VALIDOS = ("tecnico", "supervisor", "produccion", "generico", "panol")
MAIL_TIPOS_VALIDOS = ("diario_gastos", "activos_fuera")


def _requerir_permiso(token: str, permiso: str) -> dict[str, Any] | None:
    """Verifica JWT y permiso. Retorna payload o None."""
    resultado = verificar_permiso(token, permiso)
    if resultado is None:
        return None
    return resultado


def health_payload() -> dict[str, Any]:
    return {"status": "ok", "service": "personal"}


def get_areas(token: str) -> dict[str, Any] | tuple[str, int]:
    if not _requerir_permiso(token, "personal:lectura"):
        return ("No autorizado", 401)
    return {"areas": listar_areas()}


def get_personal_list(token: str, params: dict[str, Any]) -> dict[str, Any] | tuple[str, int]:
    if not _requerir_permiso(token, "personal:lectura"):
        return ("No autorizado", 401)
    q = str(params.get("q", ""))
    area_id = params.get("area_id")
    tipo = str(params.get("tipo", ""))
    activo = params.get("activo")
    limit = int(params.get("limit", 50))
    offset = int(params.get("offset", 0))
    include_prefs = params.get("include_prefs") in ("1", 1, "true", True)
    if area_id is not None:
        area_id = int(area_id)
    return listar_personal(q=q, area_id=area_id, tipo=tipo, activo=activo, limit=limit, offset=offset, include_prefs=include_prefs)


def get_personal_by_id(token: str, personal_id: int) -> dict[str, Any] | tuple[str, int]:
    if not _requerir_permiso(token, "personal:lectura"):
        return ("No autorizado", 401)
    personal = obtener_personal(personal_id)
    if not personal:
        return ("No encontrado", 404)
    return personal


def create_personal(token: str, data: dict[str, Any]) -> dict[str, Any] | tuple[str, int]:
    if not _requerir_permiso(token, "personal:escritura"):
        return ("No autorizado", 401)
    try:
        return crear_personal(data)
    except ValueError as e:
        msg = str(e)
        if "unicidad" in msg.lower() or "ya existe" in msg.lower():
            return (msg, 409)
        return (msg, 400)


def update_personal(token: str, personal_id: int, data: dict[str, Any]) -> dict[str, Any] | tuple[str, int]:
    if not _requerir_permiso(token, "personal:escritura"):
        return ("No autorizado", 401)
    try:
        result = actualizar_personal(personal_id, data)
        if result is None:
            return ("No encontrado", 404)
        return result
    except ValueError as e:
        msg = str(e)
        if "unicidad" in msg.lower() or "ya existe" in msg.lower():
            return (msg, 409)
        return (msg, 400)


def delete_personal(token: str, personal_id: int) -> dict[str, Any] | tuple[str, int]:
    if not _requerir_permiso(token, "personal:escritura"):
        return ("No autorizado", 401)
    try:
        result = eliminar_personal(personal_id)
        if result is None:
            return ("No encontrado", 404)
        return result
    except ValueError as e:
        return (str(e), 409)


def get_personal_mail_prefs(token: str, personal_id: int) -> dict[str, Any] | tuple[str, int]:
    if not _requerir_permiso(token, "personal:lectura"):
        return ("No autorizado", 401)
    prefs = get_mail_prefs(personal_id)
    return prefs


def set_personal_mail_prefs(token: str, personal_id: int, prefs: dict[str, bool]) -> dict[str, Any] | tuple[str, int]:
    if not _requerir_permiso(token, "personal:escritura"):
        return ("No autorizado", 401)
    # Validar que todos los tipos sean permitidos
    invalidos = [t for t in prefs if t not in MAIL_TIPOS_VALIDOS]
    if invalidos:
        return (f"Tipos de mail no válidos: {invalidos}. Permitidos: {MAIL_TIPOS_VALIDOS}", 400)
    result = set_mail_prefs(personal_id, prefs)
    return result


def list_all_personal_mail_prefs(token: str) -> dict[str, Any] | tuple[str, int]:
    if not _requerir_permiso(token, "personal:lectura"):
        return ("No autorizado", 401)
    items = list_prefs(include_prefs=True)
    return {"items": items, "total": len(items)}
