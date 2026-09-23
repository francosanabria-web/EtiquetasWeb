# -*- coding: utf-8 -*-
"""Conexion MariaDB para modulo Activos — preparado para migracion DB-only.

Por ahora mantiene compatibilidad con el fallback Excel (store.py).
El flag ACTIVOS_DB_ENABLED permite cambiar a lectura DB-only en proximos pasos.
"""

from __future__ import annotations

import os
from pathlib import Path

import pymysql
from pymysql.cursors import DictCursor

# ── Configuracion DB (mismo patron que backend/salidas/config.py) ──

DB_HOST = os.environ.get("ACTIVOS_DB_HOST", os.environ.get("DB_HOST", "127.0.0.1"))
DB_PORT = int(os.environ.get("ACTIVOS_DB_PORT", os.environ.get("DB_PORT", "3306")))
DB_USER = os.environ.get("ACTIVOS_DB_USER", os.environ.get("DB_USER", "root"))
DB_PASSWORD = os.environ.get("ACTIVOS_DB_PASSWORD", os.environ.get("DB_PASSWORD", ""))
DB_NAME = os.environ.get("ACTIVOS_DB_NAME", os.environ.get("DB_NAME", "panol"))
DB_DSN = os.environ.get(
    "ACTIVOS_DB_DSN",
    os.environ.get("DB_DSN", f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"),
)

# Flag DB-only: desde 2026-09-23 la DB panol.salida_activos es la unica fuente (153 filas migradas)
ACTIVOS_DB_ENABLED = os.environ.get("ACTIVOS_DB_ENABLED", "1").strip().lower() not in (
    "0", "false", "no", "off", ""
)


def get_connection() -> pymysql.connections.Connection:
    """Retorna conexion pymysql al DB panol para activos."""
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
    )


def init_db() -> None:
    """Asegura que la tabla salida_activos exista.

    Ejecuta el SQL de migracion si la tabla no existe.
    Usar durante el bootstrap del servicio.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS c FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s",
                (DB_NAME, "salida_activos"),
            )
            exists = cur.fetchone()["c"] > 0
            if not exists:
                # Levantar el SQL desde el archivo de migracion
                sql_path = Path(__file__).resolve().parents[2] / "docs" / "activos_migracion_v1.sql"
                if sql_path.is_file():
                    sql = sql_path.read_text(encoding="utf-8")
                    # Ejecutar statements individuales
                    statements = [s.strip() for s in sql.split(";") if s.strip() and not s.strip().startswith("--")]
                    for stmt in statements:
                        if stmt.upper().startswith("SET ") or stmt.upper().startswith("CREATE") or stmt.upper().startswith("INSERT"):
                            try:
                                cur.execute(stmt)
                            except Exception:
                                pass  # Algunos SET puedos fallar en batch
                    conn.commit()
        conn.close()
    except Exception:
        conn.close()
        raise


def table_exists() -> bool:
    """Verifica si la tabla salida_activos existe en DB."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS c FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s",
                (DB_NAME, "salida_activos"),
            )
            return cur.fetchone()["c"] > 0
    finally:
        conn.close()
