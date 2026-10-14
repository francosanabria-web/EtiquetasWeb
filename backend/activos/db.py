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

# Feature flag migration v2 (fotos + aprobacion). Default OFF: los endpoints
# nuevos y columnas v2 solo se usan cuando esta habilitado. Crear la tabla/
# columnas siempre es seguro e idempotente; el flag solo abre el comportamiento.
ACTIVOS_FOTOS_ENABLED = os.environ.get("ACTIVOS_FOTOS_ENABLED", "0").strip().lower() not in (
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
    Luego aplica la migracion v2 (fotos + aprobacion) de forma idempotente.
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
        apply_migration_v2(conn)
    except Exception:
        conn.close()
        raise


# ─────────────────────────────────────────────────────────────
# Migracion v2: fotos (MEDIUMBLOB + hash) + aprobacion + encargado
# Idempotente: cada paso verifica information_schema antes de ALTER.
# Las sentencias SQL equivalentes estan en docs/activos_migracion_v2.sql
# para ejecucion manual; mantener ambas en sync.
# ─────────────────────────────────────────────────────────────

_CREATE_FOTOS_TABLE = """
CREATE TABLE IF NOT EXISTS `salida_activos_fotos` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `salida_activo_id` bigint(20) unsigned NOT NULL COMMENT 'FK salida_activos(id)',
  `tipo` enum('retiro','ingreso') NOT NULL DEFAULT 'retiro',
  `foto` mediumblob NOT NULL COMMENT 'WebP (1280px max, 5 MB max)',
  `mime` varchar(30) NOT NULL DEFAULT 'image/webp',
  `tamano_bytes` int(10) unsigned NOT NULL,
  `hash_sha256` char(64) NOT NULL COMMENT 'Integridad / dedup',
  `numero_remito` varchar(40) NOT NULL DEFAULT '' COMMENT 'Remito asociado si aplica',
  `usuario_id` int(11) DEFAULT NULL,
  `creado_en` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_fotos_salida` (`salida_activo_id`),
  CONSTRAINT `fk_fotos_activo` FOREIGN KEY (`salida_activo_id`)
    REFERENCES `salida_activos` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

# Nuevas columnas de salida_activos en v2: (nombre, definicion SQL completa).
_ACTIVOS_V2_COLUMNS: tuple[tuple[str, str], ...] = (
    (
        "estado_aprobacion",
        "ADD COLUMN `estado_aprobacion` enum('pendiente','aprobado') NOT NULL DEFAULT 'pendiente'",
    ),
    (
        "encargado_salida_id",
        "ADD COLUMN `encargado_salida_id` int(11) DEFAULT NULL",
    ),
    ("aprobado_por", "ADD COLUMN `aprobado_por` int(11) DEFAULT NULL"),
    ("aprobado_en", "ADD COLUMN `aprobado_en` datetime DEFAULT NULL"),
    ("usuario_creador_id", "ADD COLUMN `usuario_creador_id` int(11) DEFAULT NULL"),
    ("usuario_ur", "ADD COLUMN `usuario_ur` int(11) DEFAULT NULL"),
)


def _column_exists(cur: DictCursor, table: str, column: str) -> bool:
    cur.execute(
        "SELECT COUNT(*) AS c FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s",
        (DB_NAME, table, column),
    )
    return cur.fetchone()["c"] > 0


def _index_exists(cur: DictCursor, table: str, index: str) -> bool:
    cur.execute(
        "SELECT COUNT(*) AS c FROM information_schema.STATISTICS "
        "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND INDEX_NAME = %s",
        (DB_NAME, table, index),
    )
    return cur.fetchone()["c"] > 0


def _fk_exists(cur: DictCursor, table: str, fk: str) -> bool:
    cur.execute(
        "SELECT COUNT(*) AS c FROM information_schema.TABLE_CONSTRAINTS "
        "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
        "AND CONSTRAINT_NAME = %s AND CONSTRAINT_TYPE = 'FOREIGN KEY'",
        (DB_NAME, table, fk),
    )
    return cur.fetchone()["c"] > 0


def apply_migration_v2(conn: pymysql.connections.Connection | None = None) -> None:
    """Aplica la migracion v2 (fotos + aprobacion) de forma idempotente.

    Segura para correr en cada arranque: cada ALTER se ejecuta solo si
    falta el objeto. El backfill a 'aprobado' corre UNA SOLA VEZ, solo
    cuando la columna estado_aprobacion se crea en esta ejecucion.
    """
    own_conn = conn is None
    conn = conn or get_connection()
    try:
        with conn.cursor() as cur:
            # 1) Tabla de fotos con FK CASCADE (creacion idempotente).
            cur.execute(_CREATE_FOTOS_TABLE)

            # 2) Columnas nuevas en salida_activos (una por una, guardadas).
            estado_col_existed = _column_exists(cur, "salida_activos", "estado_aprobacion")
            for col_name, col_def in _ACTIVOS_V2_COLUMNS:
                if not _column_exists(cur, "salida_activos", col_name):
                    cur.execute(f"ALTER TABLE `salida_activos` {col_def}")

            # 3) Backfill historico SOLO en la primera aplicacion (cuando
            # la columna acaba de crearse): marca filas preexistentes como
            # aprobadas para no inundar de 'pendiente' tras el deploy.
            if not estado_col_existed and _column_exists(cur, "salida_activos", "estado_aprobacion"):
                cur.execute(
                    "UPDATE `salida_activos` SET `estado_aprobacion` = 'aprobado' "
                    "WHERE `estado_aprobacion` = 'pendiente'"
                )

            # 4) Indice para consultas por estado de aprobacion.
            if not _index_exists(cur, "salida_activos", "idx_activos_estado_aprob"):
                cur.execute(
                    "ALTER TABLE `salida_activos` "
                    "ADD KEY `idx_activos_estado_aprob` (`estado_aprobacion`)"
                )

            # 5) FK al encargado (personal). Si personal no existe aun,
            # se omite sin fallar; la proxima corrida la crea.
            cur.execute(
                "SELECT COUNT(*) AS c FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'personal'",
                (DB_NAME,),
            )
            personal_exists = cur.fetchone()["c"] > 0
            if (
                personal_exists
                and _column_exists(cur, "salida_activos", "encargado_salida_id")
                and not _fk_exists(cur, "salida_activos", "fk_activos_encargado")
            ):
                cur.execute(
                    "ALTER TABLE `salida_activos` "
                    "ADD CONSTRAINT `fk_activos_encargado` "
                    "FOREIGN KEY (`encargado_salida_id`) REFERENCES `personal` (`id`)"
                )

        conn.commit()
    finally:
        if own_conn:
            conn.close()


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
