# -*- coding: utf-8 -*-
"""Configuración del servicio Activos fuera de planta (independiente de KPIs)."""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_BASE_PATH = Path(
    r"G:\Unidades compartidas\Mantenimiento\MANTENIMIENTO  OZLA 2024-2025\17. Pañol\pañol v5.0"
)

SALIDA_ACTIVOS = "salida_activos.xlsx"
SHEET_FUERA = "FUERA_DE_PLANTA"
SHEET_INGRESADOS = "INGRESADO_A_PLANTA"

PORT = int(os.environ.get("ACTIVOS_PORT", "8016"))

DIAS_AVISO = 21
DIAS_ALERTA = 30


def base_path() -> Path:
    raw = os.environ.get("ACTIVOS_DATA_PATH", "").strip()
    if raw:
        return Path(raw)
    # Compatibilidad: reutilizar KPIS_DATA_PATH si ya está configurado en la PC pañol.
    legacy = os.environ.get("KPIS_DATA_PATH", "").strip()
    return Path(legacy) if legacy else DEFAULT_BASE_PATH


def cors_origins_list() -> list[str]:
    raw = os.environ.get(
        "ACTIVOS_CORS_ORIGINS",
        "http://localhost:5173,http://localhost:5180,http://127.0.0.1:5173,http://127.0.0.1:5180",
    ).strip()
    if raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]


def excel_path() -> Path:
    return base_path() / SALIDA_ACTIVOS
