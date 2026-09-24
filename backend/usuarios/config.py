# -*- coding: utf-8 -*-
"""Configuración del servicio Usuarios / accesos (puerto 8015)."""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("USUARIOS_DATA_DIR", BASE_DIR / "data"))
DB_PATH = Path(os.environ.get("USUARIOS_DB_PATH", DATA_DIR / "usuarios.db"))
PORT = int(os.environ.get("USUARIOS_PORT", "8015"))

# Duración de la sesión (horas) antes de pedir login de nuevo.
SESSION_TTL_HORAS = int(os.environ.get("USUARIOS_SESSION_TTL_HORAS", "12"))

# Módulos del portal (mismo orden/ids que apps/web/src/config/navegacion.ts).
MODULOS = [
    "inicio",
    "salidas",
    "reportes",
    "activos",
    "etiquetas",
    "minuta",
    "kpis",
    "solicitudes",
    "buscador",
    "usuarios",
    "personal",
    "cajas",
    "actualizacion",
]

ROLES = ["admin", "panol", "supervisor", "jefatura"]
NIVELES = ["sin_acceso", "consulta", "escritura"]

# Plantillas de permisos por rol (punto de partida al crear un usuario).
# Reflejan apps/web/src/config/usuarios_permisos.ts + el módulo 'usuarios' (solo admin).
PLANTILLAS_ROL: dict[str, dict[str, str]] = {
    "admin": {m: "escritura" for m in MODULOS},
    "panol": {
        "inicio": "escritura",
        "salidas": "escritura",
        "reportes": "escritura",
        "activos": "escritura",
        "etiquetas": "escritura",
        "minuta": "escritura",
        "kpis": "escritura",
        "solicitudes": "escritura",
        "buscador": "escritura",
        "usuarios": "sin_acceso",
        "personal": "escritura",
        "cajas": "escritura",
        "actualizacion": "escritura",
    },
    "supervisor": {
        "inicio": "consulta",
        "salidas": "sin_acceso",
        "reportes": "sin_acceso",
        "activos": "escritura",
        "etiquetas": "sin_acceso",
        "minuta": "escritura",
        "kpis": "sin_acceso",
        "solicitudes": "escritura",
        "buscador": "consulta",
        "usuarios": "sin_acceso",
        "personal": "lectura",
        "cajas": "lectura",
        "actualizacion": "sin_acceso",
    },
    "jefatura": {
        "inicio": "consulta",
        "salidas": "sin_acceso",
        "reportes": "consulta",
        "activos": "escritura",
        "etiquetas": "sin_acceso",
        "minuta": "escritura",
        "kpis": "consulta",
        "solicitudes": "consulta",
        "buscador": "consulta",
        "usuarios": "sin_acceso",
        "personal": "lectura",
        "cajas": "lectura",
        "actualizacion": "sin_acceso",
    },
}


def plantilla_rol(rol: str) -> dict[str, str]:
    base = PLANTILLAS_ROL.get(rol, {})
    return {m: base.get(m, "sin_acceso") for m in MODULOS}


def cors_origins_list() -> list[str]:
    raw = os.environ.get("USUARIOS_CORS_ORIGINS", "*").strip()
    if raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]
