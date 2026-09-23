# -*- coding: utf-8 -*-
"""Configuración del servicio Reportes (consultas operativas de movimientos).

DB es la única fuente de datos (salida_historial en MariaDB panol).
Nunca lee Excel ni referencias a G:\.
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = BASE_DIR / "data"
SAMPLE_FILE = "sample_movimientos.csv"
HOJA_MOVIMIENTOS = "Movimientos"

PORT = int(os.environ.get("REPORTES_PORT", "8017"))

# Columnas canónicas (mismo esquema que salida_historial).
COLUMNAS = [
    "FECHA",
    "MES",
    "AÑO",
    "CODIGO",
    "DESCRIPCION",
    "UBICACION",
    "CANTIDAD",
    "TIPO_COMPROBANTE",
    "NUMERO_ORDEN",
    "MAQUINA_SITIO",
    "PRECIO_UNITARIO",
    "MONTO_TOTAL_SALIDA",
    "OPERARIO",
    "SECTOR",
]

# Detalle del mail diario de gastos (almacen_gui._generar_reporte_gastos_sector).
COLUMNAS_DETALLE_GASTOS = [
    "FECHA",
    "CODIGO",
    "DESCRIPCION",
    "CANTIDAD",
    "PRECIO_UNITARIO",
    "MONTO_TOTAL_SALIDA",
    "TIPO_COMPROBANTE",
    "NUMERO_ORDEN",
    "MAQUINA_SITIO",
    "OPERARIO",
]

COLUMNAS_EXPORT_TABLA = COLUMNAS_DETALLE_GASTOS + ["SECTOR"]

# ── Feature flag DB — DB es la única fuente ──
def _env_flag(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() not in ("0", "false", "no", "off", "")


REPORTES_DB_ENABLED = _env_flag("REPORTES_DB_ENABLED", "1")
REPORTES_DB_HOST = os.environ.get("REPORTES_DB_HOST", os.environ.get("SALIDAS_DB_HOST", os.environ.get("DB_HOST", "127.0.0.1")))
REPORTES_DB_PORT = int(os.environ.get("REPORTES_DB_PORT", os.environ.get("SALIDAS_DB_PORT", os.environ.get("DB_PORT", "3306"))))
REPORTES_DB_USER = os.environ.get("REPORTES_DB_USER", os.environ.get("SALIDAS_DB_USER", os.environ.get("DB_USER", "root")))
REPORTES_DB_PASSWORD = os.environ.get("REPORTES_DB_PASSWORD", os.environ.get("SALIDAS_DB_PASSWORD", os.environ.get("DB_PASSWORD", "")))
REPORTES_DB_NAME = os.environ.get("REPORTES_DB_NAME", os.environ.get("SALIDAS_DB_NAME", os.environ.get("DB_NAME", "panol")))

# ── Mail diario / mensual (scaffold; DESACTIVADO por defecto) ──
REPORTES_MAIL_DIARIO_ENABLED = _env_flag("REPORTES_MAIL_DIARIO_ENABLED", "0")
REPORTES_MAIL_MENSUAL_ENABLED = _env_flag("REPORTES_MAIL_MENSUAL_ENABLED", "0")
REPORTES_MAIL_DIARIO_HORA = os.environ.get("REPORTES_MAIL_DIARIO_HORA", "08:00").strip()
REPORTES_MAIL_MENSUAL_DIA = int(os.environ.get("REPORTES_MAIL_MENSUAL_DIA", "1") or "1")
REPORTES_MAIL_MENSUAL_HORA = os.environ.get("REPORTES_MAIL_MENSUAL_HORA", "08:00").strip()
REPORTES_MAIL_DESTINATARIOS = [
    d.strip()
    for d in os.environ.get("REPORTES_MAIL_DESTINATARIOS", "").split(",")
    if d.strip()
]
REPORTES_EMAIL_SERVICE_URL = os.environ.get(
    "REPORTES_EMAIL_SERVICE_URL", "http://127.0.0.1:8020"
).strip().rstrip("/")


def data_dir() -> Path:
    raw = os.environ.get("REPORTES_DATA_PATH", "").strip()
    return Path(raw) if raw else DEFAULT_DATA_DIR


def reportes_drive_config() -> dict[str, str]:
    """Google Drive source settings from environment (optional, legacy).

    Returns dict with service_account and file_id. Both must be non-empty
    for Drive mode to activate; otherwise the disk path is used unchanged.
    """
    return {
        "service_account": os.environ.get("REPORTES_DRIVE_SERVICE_ACCOUNT", "").strip(),
        "file_id": os.environ.get("REPORTES_DRIVE_FILE_ID", "").strip(),
    }


def cors_origins_list() -> list[str]:
    raw = os.environ.get(
        "REPORTES_CORS_ORIGINS",
        "http://localhost:5173,http://localhost:5180,http://127.0.0.1:5173,http://127.0.0.1:5180",
    ).strip()
    if raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]
