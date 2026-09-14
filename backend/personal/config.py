# -*- coding: utf-8 -*-
"""Configuración del servicio Personal (puerto 8019).

Microservice dedicado a gestión de personal y áreas en MariaDB.
Reutiliza el mismo patrón que backend/usuarios (:8015).
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("PERSONAL_DATA_DIR", BASE_DIR / "data"))
PORT = int(os.environ.get("PERSONAL_PORT", "8019"))

# MariaDB DSN - base de datos panol
DB_HOST = os.environ.get("PERSONAL_DB_HOST", "127.0.0.1")
DB_PORT = int(os.environ.get("PERSONAL_DB_PORT", "3306"))
DB_USER = os.environ.get("PERSONAL_DB_USER", "root")
DB_PASSWORD = os.environ.get("PERSONAL_DB_PASSWORD", "")
DB_NAME = os.environ.get("PERSONAL_DB_NAME", "panol")
DB_DSN = os.environ.get(
    "PERSONAL_DB_DSN",
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
)

# JWT - reutiliza el mismo secreto que backend/usuarios (:8015)
JWT_SECRET = os.environ.get("PERSONAL_JWT_SECRET", "panol-secret-key-2024")
JWT_ALGORITHM = "HS256"

# Permisos del módulo personal.
MODULOS = ["personal"]
PERMISOS = {
    "personal": ["lectura", "escritura"],
}

# Roles que pueden acceder al módulo personal.
PERMISO_POR_ROL: dict[str, dict[str, str]] = {
    "admin": {"personal": "escritura"},
    "panol": {"personal": "escritura"},
    "supervisor": {"personal": "lectura"},
    "jefatura": {"personal": "lectura"},
}


# Feature flag: when 1, seed may proceed with full DB population.
PERSONAL_DB_ENABLED = os.environ.get("PERSONAL_DB_ENABLED", "0").strip() not in (
    "0", "false", "False", "no",
)


def cors_origins_list() -> list[str]:
    raw = os.environ.get("PERSONAL_CORS_ORIGINS", "*").strip()
    if raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]
