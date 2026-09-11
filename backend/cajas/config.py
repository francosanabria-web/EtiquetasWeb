# -*- coding: utf-8 -*-
"""Configuración del servicio Cajas de Herramientas (puerto 8021).

Microservice dedicado a gestión de cajas y herramientas en MariaDB.
Reutiliza el mismo patrón que backend/personal (:8019).
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("CAJAS_DATA_DIR", BASE_DIR / "data"))
PORT = int(os.environ.get("CAJAS_PORT", "8021"))

# MariaDB DSN - base de datos panol
DB_HOST = os.environ.get("CAJAS_DB_HOST", "127.0.0.1")
DB_PORT = int(os.environ.get("CAJAS_DB_PORT", "3306"))
DB_USER = os.environ.get("CAJAS_DB_USER", "root")
DB_PASSWORD = os.environ.get("CAJAS_DB_PASSWORD", "")
DB_NAME = os.environ.get("CAJAS_DB_NAME", "panol")
DB_DSN = os.environ.get(
    "CAJAS_DB_DSN",
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
)

# JWT - reutiliza el mismo secreto que backend/usuarios (:8015)
JWT_SECRET = os.environ.get("CAJAS_JWT_SECRET", "panol-secret-key-2024")
JWT_ALGORITHM = "HS256"

# Permisos del módulo cajas.
MODULOS = ["cajas"]
PERMISOS = {
    "cajas": ["lectura", "escritura"],
}

# Roles que pueden acceder al módulo cajas.
PERMISO_POR_ROL: dict[str, dict[str, str]] = {
    "admin": {"cajas": "escritura"},
    "panol": {"cajas": "escritura"},
    "supervisor": {"cajas": "lectura"},
    "jefatura": {"cajas": "lectura"},
}


def cors_origins_list() -> list[str]:
    raw = os.environ.get("CAJAS_CORS_ORIGINS", "*").strip()
    if raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]
