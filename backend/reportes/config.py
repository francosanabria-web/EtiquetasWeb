# -*- coding: utf-8 -*-
"""Configuración del servicio Reportes (consultas operativas de movimientos).

Lee master_salidas.xlsx en modo solo lectura (mismo origen que KPIs por defecto).
Nunca escribe en el Excel. Pensado para sustituir el store por SQL / API Salidas
sin cambiar el contrato HTTP.
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = BASE_DIR / "data"
SAMPLE_FILE = "sample_movimientos.csv"
HOJA_MOVIMIENTOS = "Movimientos"
MASTER_SALIDAS = "master_salidas.xlsx"

# Misma ruta de producción que KPIs (doble espacio en "MANTENIMIENTO  OZLA").
DEFAULT_PROD_BASE = Path(
    r"G:\Unidades compartidas\Mantenimiento\MANTENIMIENTO  OZLA 2024-2025\17. Pañol\pañol v5.0"
)
DEFAULT_PROD_MASTER = DEFAULT_PROD_BASE / MASTER_SALIDAS

# Último recurso local (solo si no hay prod ni overrides).
SALIDAS_PRUEBA_XLSX = (
    BASE_DIR.parent / "salidas" / "data_prueba" / MASTER_SALIDAS
)

PORT = int(os.environ.get("REPORTES_PORT", "8017"))

# Columnas canónicas (mismo esquema que master_salidas / tab Reportes escritorio).
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
# En el mail HTML/Excel por sector no va SECTOR (una hoja/cuadro por sector).
# En export unificado del módulo web se agrega SECTOR al final.
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

# ── Feature flag DB (cuando 1, reportes lee salida_historial; fallback Excel) ─
def _env_flag(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() not in ("0", "false", "no", "off", "")


REPORTES_DB_ENABLED = _env_flag("REPORTES_DB_ENABLED", "0")
# Compat: si SALIDAS_DB_ENABLED=1 y REPORTES_DB_ENABLED no seteado explícitamente, heredar?
# Se respeta REPORTES_DB_ENABLED como autoridad; el start script lo setea a 1.
REPORTES_DB_HOST = os.environ.get("REPORTES_DB_HOST", os.environ.get("SALIDAS_DB_HOST", os.environ.get("DB_HOST", "127.0.0.1")))
REPORTES_DB_PORT = int(os.environ.get("REPORTES_DB_PORT", os.environ.get("SALIDAS_DB_PORT", os.environ.get("DB_PORT", "3306"))))
REPORTES_DB_USER = os.environ.get("REPORTES_DB_USER", os.environ.get("SALIDAS_DB_USER", os.environ.get("DB_USER", "root")))
REPORTES_DB_PASSWORD = os.environ.get("REPORTES_DB_PASSWORD", os.environ.get("SALIDAS_DB_PASSWORD", os.environ.get("DB_PASSWORD", "")))
REPORTES_DB_NAME = os.environ.get("REPORTES_DB_NAME", os.environ.get("SALIDAS_DB_NAME", os.environ.get("DB_NAME", "panol")))

# ── Mail diario / mensual (scaffold; DESACTIVADO por defecto) ──────────────
REPORTES_MAIL_DIARIO_ENABLED = _env_flag("REPORTES_MAIL_DIARIO_ENABLED", "0")
REPORTES_MAIL_MENSUAL_ENABLED = _env_flag("REPORTES_MAIL_MENSUAL_ENABLED", "0")
REPORTES_MAIL_DIARIO_HORA = os.environ.get("REPORTES_MAIL_DIARIO_HORA", "07:30").strip()
REPORTES_MAIL_MENSUAL_DIA = int(os.environ.get("REPORTES_MAIL_MENSUAL_DIA", "1") or "1")
REPORTES_MAIL_MENSUAL_HORA = os.environ.get("REPORTES_MAIL_MENSUAL_HORA", "08:00").strip()
REPORTES_MAIL_DESTINATARIOS = [
    d.strip()
    for d in os.environ.get("REPORTES_MAIL_DESTINATARIOS", "").split(",")
    if d.strip()
]
# URL opcional del email_service (hoy sin adjuntos; el scaffold usa SMTP local con adjunto).
REPORTES_EMAIL_SERVICE_URL = os.environ.get(
    "REPORTES_EMAIL_SERVICE_URL", "http://127.0.0.1:8020"
).strip().rstrip("/")


def data_dir() -> Path:
    raw = os.environ.get("REPORTES_DATA_PATH", "").strip()
    return Path(raw) if raw else DEFAULT_DATA_DIR


def _master_in_dir(raw: str) -> Path | None:
    """Si `raw` apunta a carpeta o archivo, devolver master_salidas.xlsx existente."""
    if not raw:
        return None
    p = Path(raw)
    if p.is_file() and p.name.lower().endswith((".xlsx", ".csv")):
        return p
    if p.is_dir():
        candidate = p / MASTER_SALIDAS
        if candidate.is_file():
            return candidate
    return None


def reportes_drive_config() -> dict[str, str]:
    """Google Drive source settings from environment (optional).

    Returns dict with service_account and file_id. Both must be non-empty
    for Drive mode to activate; otherwise the disk path is used unchanged.
    """
    return {
        "service_account": os.environ.get("REPORTES_DRIVE_SERVICE_ACCOUNT", "").strip(),
        "file_id": os.environ.get("REPORTES_DRIVE_FILE_ID", "").strip(),
    }


def movimientos_path() -> Path:
    """Archivo de movimientos (solo lectura).

    Orden de resolución:
    1. REPORTES_MOVIMIENTOS_FILE (override explícito)
    2. REPORTES_DATA_PATH → master_salidas.xlsx si existe
    3. KPIS_DATA_PATH o SALIDAS_DATA_PATH → master_salidas.xlsx si existe
    4. Fallback producción (mismo path que KPIs)
    5. Último recurso: backend/salidas/data_prueba/master_salidas.xlsx
    """
    explicit = os.environ.get("REPORTES_MOVIMIENTOS_FILE", "").strip()
    if explicit:
        return Path(explicit)

    from_reportes = _master_in_dir(os.environ.get("REPORTES_DATA_PATH", "").strip())
    if from_reportes is not None:
        return from_reportes

    for env_key in ("KPIS_DATA_PATH", "SALIDAS_DATA_PATH"):
        found = _master_in_dir(os.environ.get(env_key, "").strip())
        if found is not None:
            return found

    if DEFAULT_PROD_MASTER.is_file():
        return DEFAULT_PROD_MASTER

    if SALIDAS_PRUEBA_XLSX.is_file():
        return SALIDAS_PRUEBA_XLSX

    # Preferir path de prod en mensajes de error si tampoco hay prueba.
    if DEFAULT_PROD_BASE.is_dir():
        return DEFAULT_PROD_MASTER
    return SALIDAS_PRUEBA_XLSX


def cors_origins_list() -> list[str]:
    raw = os.environ.get(
        "REPORTES_CORS_ORIGINS",
        "http://localhost:5173,http://localhost:5180,http://127.0.0.1:5173,http://127.0.0.1:5180",
    ).strip()
    if raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]
