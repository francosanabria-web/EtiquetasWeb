# -*- coding: utf-8 -*-
"""Configuración del servicio Salidas (egreso de material del pañol).

Modo planta (default si existe la ruta G:\\):
  - Lee maestro SOLO LECTURA: master_codes.xlsx del pañol (escritorio).
  - Escribe movimientos en salidas_web/ (no toca master_salidas ni master_codes
    de producción).

Modo prueba local: si no hay Drive/pañol, usa data_prueba/ (lectura+escritura).
Ver data_prueba/COMO_APUNTAR_PRODUCCION.md.
"""

from __future__ import annotations

import os
from pathlib import Path

_DIR = Path(__file__).resolve().parent
_DEFAULT_DATA_PRUEBA = _DIR / "data_prueba"

# Ruta real verificada (doble espacio en "MANTENIMIENTO  OZLA")
DEFAULT_PANOL_BASE = Path(
    r"G:\Unidades compartidas\Mantenimiento\MANTENIMIENTO  OZLA 2024-2025\17. Pañol\pañol v5.0"
)
DEFAULT_SALIDAS_WEB = DEFAULT_PANOL_BASE / "salidas_web"

PORT = int(os.environ.get("SALIDAS_PORT", "8018"))

# MariaDB DSN - base de datos panol (mismo patron que backend/cajas y backend/personal)
DB_HOST = os.environ.get("SALIDAS_DB_HOST", os.environ.get("DB_HOST", "127.0.0.1"))
DB_PORT = int(os.environ.get("SALIDAS_DB_PORT", os.environ.get("DB_PORT", "3306")))
DB_USER = os.environ.get("SALIDAS_DB_USER", os.environ.get("DB_USER", "root"))
DB_PASSWORD = os.environ.get("SALIDAS_DB_PASSWORD", os.environ.get("DB_PASSWORD", ""))
DB_NAME = os.environ.get("SALIDAS_DB_NAME", os.environ.get("DB_NAME", "panol"))
DB_DSN = os.environ.get(
    "SALIDAS_DB_DSN",
    os.environ.get("DB_DSN", f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"),
)

# JWT - reutiliza el mismo secreto que backend/usuarios (:8015)
JWT_SECRET = os.environ.get("SALIDAS_JWT_SECRET", os.environ.get("JWT_SECRET", "panol-secret-key-2024"))
JWT_ALGORITHM = "HS256"

# Permisos del modulo salidas
MODULOS = ["salidas"]
PERMISOS = {
    "salidas": ["lectura", "escritura"],
}
PERMISO_POR_ROL: dict[str, dict[str, str]] = {
    "admin": {"salidas": "escritura"},
    "panol": {"salidas": "escritura"},
    "supervisor": {"salidas": "lectura"},
    "jefatura": {"salidas": "lectura"},
}

# Feature flags
SALIDAS_DB_ENABLED = os.environ.get("SALIDAS_DB_ENABLED", "0").strip().lower() not in (
    "0", "false", "no", "off", ""
)

# Maestro (artículos + config). En planta: master_codes.xlsx (como el escritorio).
MAESTRO_PRIMARY = "base_datos.xlsx"  # solo data_prueba / legacy
MAESTRO_LEGACY = "master_codes.xlsx"
HISTORIAL_NAME = "master_salidas.xlsx"
HOJA_ARTICULOS = "ARTICULOS"
HOJA_MOVIMIENTOS = "Movimientos"
HOJA_CONFIG = "config"

MES_NOMBRES = {
    1: "Enero.",
    2: "Febrero.",
    3: "Marzo.",
    4: "Abril.",
    5: "Mayo.",
    6: "Junio.",
    7: "Julio.",
    8: "Agosto.",
    9: "Septiembre.",
    10: "Octubre.",
    11: "Noviembre.",
    12: "Diciembre.",
}

TIPOS_COMPROBANTE_DEFAULT = [
    "PAÑOL",
    "L1",
    "L2",
    "L3",
    "L4",
    "L5",
    "L6",
    "L7",
    "PROYECTOS",
]
SECTORES_DEFAULT = [
    "MANTENIMIENTO",
    "EDILICIO",
    "PRODUCCION",
    "PROYECTOS",
    "AUTOELEVADORES",
]
OPERARIOS_DEFAULT = ["AA", "AB", "AC", "AD", "AE", "AF", "AG"]
OPERARIOS_PROYECTOS_DEFAULT = ["MACCARONI", "VALENZUELA"]

COLUMNAS_MOVIMIENTO = [
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

# Sync Firebase: pull opcional. Write al confirmar = OFF por decisión 2026-08-05.
HORA_SYNC_FIREBASE = int(os.environ.get("SALIDAS_SYNC_HORA", "8"))
FIREBASE_WRITE_ENABLED = os.environ.get("SALIDAS_FIREBASE_WRITE", "0").strip() not in (
    "0",
    "false",
    "False",
    "no",
)

# Feature flag: when 1, salidas catalog sources from MariaDB personal/areas tables.
PERSONAL_DB_ENABLED = os.environ.get("PERSONAL_DB_ENABLED", "0").strip() not in (
    "0",
    "false",
    "False",
    "no",
)


def panol_base() -> Path:
    raw = os.environ.get("SALIDAS_PANOL_PATH", "").strip()
    return Path(raw) if raw else DEFAULT_PANOL_BASE


def data_path() -> Path:
    """Carpeta de ESCRITURA: historial web + diarios + caché SQLite.

    Preferencia:
      1. SALIDAS_WEB_PATH o SALIDAS_DATA_PATH (env)
      2. panol/salidas_web si el pañol existe en disco
      3. data_prueba/ (demo local)
    """
    raw = (
        os.environ.get("SALIDAS_WEB_PATH", "").strip()
        or os.environ.get("SALIDAS_DATA_PATH", "").strip()
    )
    if raw:
        return Path(raw)
    base = panol_base()
    if base.is_dir():
        return base / "salidas_web"
    return _DEFAULT_DATA_PRUEBA


def maestro_path() -> Path:
    """Ruta del maestro de artículos/config (preferir master_codes del escritorio)."""
    explicit = os.environ.get("SALIDAS_MAESTRO_PATH", "").strip()
    if explicit:
        return Path(explicit)

    # 1) Planta: master_codes junto al escritorio
    prod = panol_base() / MAESTRO_LEGACY
    if prod.is_file():
        return prod

    # 2) Carpeta de escritura (prueba / override)
    write = data_path()
    for name in (MAESTRO_PRIMARY, MAESTRO_LEGACY):
        candidate = write / name
        if candidate.is_file():
            return candidate

    # 3) data_prueba embebida
    for name in (MAESTRO_PRIMARY, MAESTRO_LEGACY):
        candidate = _DEFAULT_DATA_PRUEBA / name
        if candidate.is_file():
            return candidate

    # Destino esperado en planta (aunque aún no exista)
    if panol_base().is_dir():
        return prod
    return _DEFAULT_DATA_PRUEBA / MAESTRO_PRIMARY


def maestro_writable() -> bool:
    """Nunca escribir master_codes / base_datos de producción del pañol.

    Solo permite escritura si el maestro está bajo data_prueba o si
    SALIDAS_MAESTRO_WRITABLE=1 (solo para demos controladas).
    """
    flag = os.environ.get("SALIDAS_MAESTRO_WRITABLE", "").strip().lower()
    if flag in ("1", "true", "yes", "si", "sí"):
        return True
    if flag in ("0", "false", "no"):
        return False

    path = maestro_path().resolve()
    try:
        if path == (panol_base() / MAESTRO_LEGACY).resolve():
            return False
        if path == (panol_base() / MAESTRO_PRIMARY).resolve():
            return False
    except OSError:
        pass

    try:
        path.relative_to(_DEFAULT_DATA_PRUEBA.resolve())
        return True
    except ValueError:
        pass

    # Maestro dentro de salidas_web u otra carpeta de escritura: no escribir
    # por defecto (el egreso web no debe mutar un maestro compartido).
    return False


def historial_path() -> Path:
    return data_path() / HISTORIAL_NAME


def diario_path(fecha) -> Path:
    """salidas_DD-MM-AAAA.xlsx en salidas_web (o data_prueba)."""
    return data_path() / f"salidas_{fecha.strftime('%d-%m-%Y')}.xlsx"


def cache_db_path() -> Path:
    raw = os.environ.get("SALIDAS_CACHE_DB", "").strip()
    if raw:
        return Path(raw)
    return data_path() / "articulos_cache.db"


def firebase_credentials_path() -> Path:
    raw = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if raw:
        return Path(raw)
    candidatos = [
        _DIR / "serviceAccountKey.json",
        panol_base() / "serviceAccountKey.json",
        _DIR.parent.parent / "services" / "etiquetas-api" / "serviceAccountKey.json",
    ]
    for c in candidatos:
        if c.is_file():
            return c
    return candidatos[0]


def cors_origins_list() -> list[str]:
    raw = os.environ.get(
        "SALIDAS_CORS_ORIGINS",
        "http://localhost:5173,http://localhost:5180,http://127.0.0.1:5173,http://127.0.0.1:5180",
    ).strip()
    if raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]
