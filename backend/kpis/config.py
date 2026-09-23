# -*- coding: utf-8 -*-
"""Configuración del servicio KPIs."""

from __future__ import annotations

import os
from pathlib import Path

# Ruta real verificada (doble espacio en "MANTENIMIENTO  OZLA")
DEFAULT_BASE_PATH = Path(
    r"G:\Unidades compartidas\Mantenimiento\MANTENIMIENTO  OZLA 2024-2025\17. Pañol\pañol v5.0"
)

MASTER_CODES = "master_codes.xlsx"
MASTER_SALIDAS = "master_salidas.xlsx"
SALIDA_ACTIVOS = "salida_activos.xlsx"

SHEET_ARTICULOS = "ARTICULOS"
SHEET_CONFIG = "config"
SHEET_MOVIMIENTOS = "Movimientos"
SHEET_ACTIVOS = "FUERA_DE_PLANTA"

PORT = int(os.environ.get("KPIS_PORT", "8001"))

CORS_ORIGINS = os.environ.get(
    "KPIS_CORS_ORIGINS",
    "http://localhost:5173,http://localhost:5180,http://127.0.0.1:5173,http://127.0.0.1:5180",
)

# ── MariaDB DSN (misma configuración que backend/salidas/config.py) ──
DB_HOST = os.environ.get("SALIDAS_DB_HOST", os.environ.get("DB_HOST", "127.0.0.1"))
DB_PORT = int(os.environ.get("SALIDAS_DB_PORT", os.environ.get("DB_PORT", "3306")))
DB_USER = os.environ.get("SALIDAS_DB_USER", os.environ.get("DB_USER", "root"))
DB_PASSWORD = os.environ.get("SALIDAS_DB_PASSWORD", os.environ.get("DB_PASSWORD", ""))
DB_NAME = os.environ.get("SALIDAS_DB_NAME", os.environ.get("DB_NAME", "panol"))
DB_DSN = os.environ.get(
    "SALIDAS_DB_DSN",
    os.environ.get("DB_DSN", f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"),
)

KPIS_DB_ENABLED = os.environ.get("KPIS_DB_ENABLED", os.environ.get("SALIDAS_DB_ENABLED", "1")).strip().lower() not in (
    "0", "false", "no", "off", ""
)


def base_path() -> Path:
    raw = os.environ.get("KPIS_DATA_PATH", "").strip()
    return Path(raw) if raw else DEFAULT_BASE_PATH


def cors_origins_list() -> list[str]:
    val = os.environ.get("KPIS_CORS_ORIGINS", CORS_ORIGINS).strip()
    if val == "*":
        return ["*"]
    return [o.strip() for o in val.split(",") if o.strip()]
