# -*- coding: utf-8 -*-
"""Configuración del servicio Solicitud de pedidos."""

from __future__ import annotations

import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("SOLICITUDES_DATA_DIR", BASE_DIR / "data"))

# Carpeta de datos compartida en Google Drive (misma que usan KPIs / correos).
# En producción es la carpeta sincronizada del pañol; todas las PC ven lo mismo.
DEFAULT_DRIVE_DIR = Path(
    r"G:\Unidades compartidas\Mantenimiento\MANTENIMIENTO  OZLA 2024-2025"
    r"\17. Pañol\pañol v5.0"
)


def _drive_dir() -> Path:
    raw = os.environ.get("SOLICITUDES_DRIVE_DIR", "").strip()
    return Path(raw) if raw else DEFAULT_DRIVE_DIR


DRIVE_DIR = _drive_dir()

# Fuente de verdad de los pedidos: Excel en Drive (no SQLite local).
EXCEL_PATH = Path(
    os.environ.get("SOLICITUDES_EXCEL_PATH", DRIVE_DIR / "solicitudes_pedidos.xlsx")
)
# Adjuntos (remito / presupuesto / imágenes) también compartidos en Drive.
UPLOADS_DIR = Path(
    os.environ.get("SOLICITUDES_UPLOADS_DIR", DRIVE_DIR / "solicitudes_adjuntos")
)
# SQLite legado: solo se usa para migrar datos existentes al Excel la primera vez.
DB_PATH = Path(os.environ.get("SOLICITUDES_DB_PATH", DATA_DIR / "solicitudes.db"))
CATALOGOS_PATH = BASE_DIR / "CATALOGOS_EDITABLES.json"
PORT = int(os.environ.get("SOLICITUDES_PORT", "8014"))


def cors_origins_list() -> list[str]:
    raw = os.environ.get("SOLICITUDES_CORS_ORIGINS", "*").strip()
    if raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]


def cargar_catalogos() -> dict:
    if not CATALOGOS_PATH.is_file():
        return {
            "estados": [],
            "tipos": [],
            "areas": [],
            "cuentas_contables": [],
            "unidades_medida": [],
            "proveedores": [],
        }
    return json.loads(CATALOGOS_PATH.read_text(encoding="utf-8"))
