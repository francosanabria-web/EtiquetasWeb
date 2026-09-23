# -*- coding: utf-8 -*-
"""Persistencia MariaDB — Salidas (paNol).

Conexion a MariaDB (XAMPP) base `panol`.
Tablas: salida_historial, salida_movimientos_diario, salida_otif, salida_atenciones, salida_atencion_motivos
Esquema idempotente definido en Server/docs/salidas_migracion_v*.sql
Sigue EXACTAMENTE el patron de backend/personal/db.py y backend/cajas/db.py:
  - Pool via pymysql.connections.Connection
  - get_connection() / _get_pool()
  - init_db() con CREATE TABLE IF NOT EXISTS
  - verificar_permiso() con JWT + fallback sesion opaca
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pymysql import connections
from pymysql.cursors import DictCursor
from pymysql.err import IntegrityError  # noqa: F401 - reservado para store_sql

from config import (
    DB_DSN,
    DB_HOST,
    DB_NAME,
    DB_PASSWORD,
    DB_PORT,
    DB_USER,
    JWT_ALGORITHM,
    JWT_SECRET,
    PERMISO_POR_ROL,
)

_pool = None


def _get_pool():
    global _pool
    if _pool is None or _pool.open is False:
        _pool = connections.Connection(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            charset="utf8mb4",
            cursorclass=DictCursor,
            autocommit=False,
        )
    return _pool


def get_connection():
    """Retorna una conexion activa."""
    conn = _get_pool()
    if not conn.open:
        conn = connections.Connection(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            charset="utf8mb4",
            cursorclass=DictCursor,
        )
    return conn


def init_db() -> None:
    """Crea las tablas salida_* si no existen (idempotente).

    v1: salida_historial (fuente unica, se mantiene)
    v2: salida_atenciones (ventanilla)
    v3: salida_atencion_motivos (catalogo) - OBSOLETO en v4 (se elimina)
    v4: simplificacion volantazo 2026-09-16:
        - DROP salida_movimientos_diario (diario se extrae de historial)
        - DROP salida_otif (OTIF detallado futuro)
        - DROP salida_atencion_motivos (catalogo motivos ya no usado)
        - Simplificar salida_atenciones a: fecha, con_retiro, observaciones(500),
          atendido_en, atendido_por, creado_en, actualizado_en
        - salida_historial intacta como fuente unica

    DDL identico a Server/docs/salidas_migracion_v*.sql pero ejecutado
    via Python para que el servicio pueda auto-inicializarse.
    Requiere que existan las tablas GENERALES `areas` y `personal`;
    si no existen la FK fallara - en ese caso ejecutar primero la
    migracion de personal/cajas (fallback sin FKs).
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # ---------------------------------------------------------
            # salida_historial - historial global (reemplaza master_salidas)
            # ---------------------------------------------------------
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS `salida_historial` (
                  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
                  `fecha` DATE NOT NULL COMMENT 'FECHA',
                  `mes` VARCHAR(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'MES ej Enero.',
                  `anio` SMALLINT UNSIGNED DEFAULT NULL COMMENT 'AÑO',
                  `codigo` VARCHAR(40) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'CODIGO',
                  `descripcion` TEXT COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'DESCRIPCION snapshot UPPER',
                  `ubicacion` VARCHAR(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'UBICACION snapshot',
                  `cantidad` DECIMAL(10,2) NOT NULL COMMENT 'CANTIDAD positivo salida negativo devolucion',
                  `tipo_comprobante` VARCHAR(30) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'TIPO_COMPROBANTE',
                  `numero_orden` VARCHAR(40) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'NUMERO_ORDEN',
                  `maquina_sitio` VARCHAR(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'MAQUINA_SITIO',
                  `precio_unitario` DECIMAL(12,2) DEFAULT NULL COMMENT 'PRECIO_UNITARIO',
                  `monto_total` DECIMAL(12,2) DEFAULT NULL COMMENT 'MONTO_TOTAL_SALIDA',
                  `operario_id` INT UNSIGNED DEFAULT NULL COMMENT 'FK personal',
                  `operario_nombre` VARCHAR(150) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'OPERARIO snapshot',
                  `area_id` INT UNSIGNED DEFAULT NULL COMMENT 'FK areas',
                  `sector_nombre` VARCHAR(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'SECTOR snapshot',
                  `es_devolucion` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '1=devolucion',
                  `creado_por` VARCHAR(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
                  `creado_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  `actualizado_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                  PRIMARY KEY (`id`),
                  KEY `idx_salida_historial_fecha` (`fecha`),
                  KEY `idx_salida_historial_codigo` (`codigo`),
                  KEY `idx_salida_historial_operario` (`operario_id`),
                  KEY `idx_salida_historial_area` (`area_id`),
                  KEY `idx_salida_historial_tipo_comprobante` (`tipo_comprobante`),
                  KEY `idx_salida_historial_fecha_codigo` (`fecha`, `codigo`),
                  KEY `idx_salida_historial_creado_en` (`creado_en`),
                  CONSTRAINT `fk_salida_historial_operario` FOREIGN KEY (`operario_id`) REFERENCES `personal` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
                  CONSTRAINT `fk_salida_historial_area` FOREIGN KEY (`area_id`) REFERENCES `areas` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Historial global de salidas - reemplaza master_salidas.xlsx'
                """
            )

            # ---------------------------------------------------------
            # v5: auditable soft-delete/edit para salida_historial
            # Asegurar columnas anulado/editado y tabla de auditoria
            # ---------------------------------------------------------
            # Columnas soft-delete (idempotente via information_schema)
            for _col_name, _col_ddl in (
                ("anulado", "ALTER TABLE `salida_historial` ADD COLUMN `anulado` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '1=anulado (soft delete)'"),
                ("anulado_por", "ALTER TABLE `salida_historial` ADD COLUMN `anulado_por` VARCHAR(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'usuario que anulo'"),
                ("anulado_en", "ALTER TABLE `salida_historial` ADD COLUMN `anulado_en` DATETIME DEFAULT NULL COMMENT 'cuando se anulo'"),
                ("motivo_anulacion", "ALTER TABLE `salida_historial` ADD COLUMN `motivo_anulacion` VARCHAR(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'motivo obligatorio'"),
                ("editado_en", "ALTER TABLE `salida_historial` ADD COLUMN `editado_en` DATETIME DEFAULT NULL"),
                ("editado_por", "ALTER TABLE `salida_historial` ADD COLUMN `editado_por` VARCHAR(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL"),
            ):
                try:
                    cur.execute(
                        """
                        SELECT COUNT(*) AS c FROM information_schema.COLUMNS
                        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME='salida_historial' AND COLUMN_NAME=%s
                        """,
                        (_col_name,),
                    )
                    _rcol = cur.fetchone()
                    if _rcol and int(_rcol.get("c", 0)) == 0:
                        cur.execute(_col_ddl)
                except Exception:
                    pass
            # Indice auxiliar para filtrar anulados si no existe
            try:
                cur.execute(
                    """
                    SELECT COUNT(*) AS c FROM information_schema.STATISTICS
                    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME='salida_historial' AND INDEX_NAME='idx_salida_historial_anulado'
                    """
                )
                _ridx = cur.fetchone()
                if _ridx and int(_ridx.get("c", 0)) == 0:
                    cur.execute("ALTER TABLE `salida_historial` ADD INDEX `idx_salida_historial_anulado` (`anulado`)")
            except Exception:
                pass
            # Tabla auditoria
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS `salida_historial_auditoria` (
                  `id` INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                  `historial_id` INT UNSIGNED NOT NULL COMMENT 'FK salida_historial.id',
                  `accion` ENUM('anular','editar','crear') NOT NULL,
                  `datos_before` JSON DEFAULT NULL COMMENT 'snapshot before',
                  `datos_after` JSON DEFAULT NULL COMMENT 'snapshot after',
                  `realizado_por` VARCHAR(120) DEFAULT NULL,
                  `realizado_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  `motivo` VARCHAR(500) DEFAULT NULL,
                  KEY `idx_auditoria_historial` (`historial_id`),
                  KEY `idx_auditoria_accion` (`accion`),
                  KEY `idx_auditoria_fecha` (`realizado_en`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Auditoria de ediciones/anulaciones salida_historial'
                """
            )

            # ---------------------------------------------------------
            # v4: DROP tablas obsoletas (volantazo 2026-09-16)
            # Si existen, eliminarlas. Diario/OTIF/motivos ya no se usan.
            # ---------------------------------------------------------
            for _tbl in ("salida_movimientos_diario", "salida_otif", "salida_atencion_motivos"):
                try:
                    cur.execute(f"DROP TABLE IF EXISTS `{_tbl}`")
                except Exception:
                    # Intentar con FOREIGN_KEY_CHECKS=0 si hay FK dependencias
                    try:
                        cur.execute("SET FOREIGN_KEY_CHECKS=0")
                        cur.execute(f"DROP TABLE IF EXISTS `{_tbl}`")
                        cur.execute("SET FOREIGN_KEY_CHECKS=1")
                    except Exception:
                        try:
                            cur.execute("SET FOREIGN_KEY_CHECKS=1")
                        except Exception:
                            pass
                        pass

            # ---------------------------------------------------------
            # salida_atenciones - v4 simplificada al minimo
            # Solo: fecha, con_retiro, observaciones(500), atendido_en, atendido_por, creado_en, actualizado_en
            # Semantica: con_retiro=true -> retiro FUERA DE SISTEMA, false -> no hubo stock
            # ---------------------------------------------------------
            # Crear si no existe con esquema minimo
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS `salida_atenciones` (
                  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
                  `fecha` DATE NOT NULL COMMENT 'Fecha de atencion - obligatorio',
                  `con_retiro` TINYINT(1) NOT NULL COMMENT '1=retiro FUERA DE SISTEMA, 0=no hubo stock de lo solicitado',
                  `observaciones` VARCHAR(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Observaciones libres (500) - semantica con_retiro',
                  `atendido_en` DATETIME DEFAULT NULL COMMENT 'Timestamp completo opcional',
                  `atendido_por` VARCHAR(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Usuario que atendio - opcional',
                  `creado_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  `actualizado_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                  PRIMARY KEY (`id`),
                  KEY `idx_salida_atenciones_fecha` (`fecha`),
                  KEY `idx_salida_atenciones_con_retiro` (`con_retiro`),
                  KEY `idx_salida_atenciones_creado_en` (`creado_en`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Atenciones ventanilla simplificada v4 - solo fecha, con_retiro (fuera sistema vs sin stock), observaciones'
                """
            )

            # ---------------------------------------------------------
            # v4 migration: simplificar tabla existente si viene de v2/v3
            # - Eliminar FKs que bloquean DROP COLUMN
            # - Eliminar indices dependientes
            # - DROP columnas obsoletas una por una (si existen)
            # - Ampliar observaciones a 500
            # - Asegurar columnas minimas existan
            # ---------------------------------------------------------
            try:
                # Verificar que tabla existe (ya creada arriba)
                cur.execute(
                    """
                    SELECT COUNT(*) AS c FROM information_schema.TABLES
                    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'salida_atenciones'
                    """
                )
                row_tbl = cur.fetchone()
                if row_tbl and int(row_tbl.get("c", 0)) > 0:
                    # --- FKs ---
                    for _fk in ("fk_salida_atenciones_persona", "fk_salida_atenciones_area", "fk_salida_atenciones_atendido_por", "fk_salida_atenciones_motivo"):
                        try:
                            cur.execute(
                                """
                                SELECT COUNT(*) AS c FROM information_schema.TABLE_CONSTRAINTS
                                WHERE CONSTRAINT_SCHEMA = DATABASE()
                                  AND TABLE_NAME = 'salida_atenciones'
                                  AND CONSTRAINT_NAME = %s
                                """,
                                (_fk,),
                            )
                            rfk = cur.fetchone()
                            if rfk and int(rfk.get("c", 0)) > 0:
                                cur.execute(f"ALTER TABLE `salida_atenciones` DROP FOREIGN KEY `{_fk}`")
                        except Exception:
                            pass
                    # --- Indices ---
                    for _idx in ("idx_salida_atenciones_area", "idx_salida_atenciones_persona", "idx_salida_atenciones_atendido_por", "idx_salida_atenciones_motivo", "idx_salida_atenciones_fecha_con_retiro"):
                        try:
                            cur.execute(
                                """
                                SELECT COUNT(*) AS c FROM information_schema.STATISTICS
                                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME='salida_atenciones' AND INDEX_NAME=%s
                                """,
                                (_idx,),
                            )
                            ridx = cur.fetchone()
                            if ridx and int(ridx.get("c", 0)) > 0:
                                cur.execute(f"ALTER TABLE `salida_atenciones` DROP INDEX `{_idx}`")
                        except Exception:
                            pass
                    # --- Columnas obsoletas ---
                    for _col in ("hora", "persona_solicitante", "persona_id", "area_id", "sector_nombre", "motivo_sin_retiro", "cantidad_items_solicitados", "orden_referencia", "atendido_por_id", "creado_por"):
                        try:
                            cur.execute(
                                """
                                SELECT COUNT(*) AS c FROM information_schema.COLUMNS
                                WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='salida_atenciones' AND COLUMN_NAME=%s
                                """,
                                (_col,),
                            )
                            rc = cur.fetchone()
                            if rc and int(rc.get("c", 0)) > 0:
                                cur.execute(f"ALTER TABLE `salida_atenciones` DROP COLUMN `{_col}`")
                        except Exception:
                            pass
                    # --- Ampliar observaciones ---
                    try:
                        cur.execute(
                            """
                            SELECT COLUMN_TYPE, CHARACTER_MAXIMUM_LENGTH FROM information_schema.COLUMNS
                            WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='salida_atenciones' AND COLUMN_NAME='observaciones'
                            """
                        )
                        robs = cur.fetchone()
                        if robs:
                            maxlen = robs.get("CHARACTER_MAXIMUM_LENGTH")
                            coltype = str(robs.get("COLUMN_TYPE") or "")
                            # Si no es 500, ampliar
                            if maxlen is not None and int(maxlen) < 500:
                                cur.execute(
                                    """
                                    ALTER TABLE `salida_atenciones`
                                    MODIFY `observaciones` VARCHAR(500) COLLATE utf8mb4_unicode_ci NULL
                                    COMMENT 'Observaciones libres (500) - semantica con_retiro: con_retiro=1 retiro fuera de sistema, 0=sin stock'
                                    """
                                )
                            elif "varchar(140" in coltype.lower() or "varchar(150" in coltype.lower() or "varchar(30" in coltype.lower():
                                cur.execute(
                                    """
                                    ALTER TABLE `salida_atenciones`
                                    MODIFY `observaciones` VARCHAR(500) COLLATE utf8mb4_unicode_ci NULL
                                    COMMENT 'Observaciones libres (500) - semantica con_retiro'
                                    """
                                )
                    except Exception:
                        pass
                    # --- Asegurar columnas minimas existan ---
                    # atendido_en
                    try:
                        cur.execute(
                            """
                            SELECT COUNT(*) AS c FROM information_schema.COLUMNS
                            WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='salida_atenciones' AND COLUMN_NAME='atendido_en'
                            """
                        )
                        rc = cur.fetchone()
                        if rc and int(rc.get("c", 0)) == 0:
                            cur.execute("ALTER TABLE `salida_atenciones` ADD COLUMN `atendido_en` DATETIME DEFAULT NULL COMMENT 'Timestamp completo opcional' AFTER `con_retiro`")
                    except Exception:
                        pass
                    # atendido_por
                    try:
                        cur.execute(
                            """
                            SELECT COUNT(*) AS c FROM information_schema.COLUMNS
                            WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='salida_atenciones' AND COLUMN_NAME='atendido_por'
                            """
                        )
                        rc = cur.fetchone()
                        if rc and int(rc.get("c", 0)) == 0:
                            cur.execute("ALTER TABLE `salida_atenciones` ADD COLUMN `atendido_por` VARCHAR(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Usuario que atendio - opcional' AFTER `atendido_en`")
                    except Exception:
                        pass
                    # creado_en / actualizado_en ya existen si tabla existia, pero verificar por si es instalacion vieja con otra definicion
                    for _col_def in [
                        ("creado_en", "ALTER TABLE `salida_atenciones` ADD COLUMN `creado_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"),
                        ("actualizado_en", "ALTER TABLE `salida_atenciones` ADD COLUMN `actualizado_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
                    ]:
                        _cn, _sql = _col_def
                        try:
                            cur.execute(
                                "SELECT COUNT(*) AS c FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='salida_atenciones' AND COLUMN_NAME=%s",
                                (_cn,),
                            )
                            rc = cur.fetchone()
                            if rc and int(rc.get("c", 0)) == 0:
                                cur.execute(_sql)
                        except Exception:
                            pass
                    # --- Indices minimos ---
                    for _idx, _sql in (
                        ("idx_salida_atenciones_fecha", "ALTER TABLE `salida_atenciones` ADD INDEX `idx_salida_atenciones_fecha` (`fecha`)"),
                        ("idx_salida_atenciones_con_retiro", "ALTER TABLE `salida_atenciones` ADD INDEX `idx_salida_atenciones_con_retiro` (`con_retiro`)"),
                        ("idx_salida_atenciones_creado_en", "ALTER TABLE `salida_atenciones` ADD INDEX `idx_salida_atenciones_creado_en` (`creado_en`)"),
                    ):
                        try:
                            cur.execute(
                                "SELECT COUNT(*) AS c FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='salida_atenciones' AND INDEX_NAME=%s",
                                (_idx,),
                            )
                            rc = cur.fetchone()
                            if rc and int(rc.get("c", 0)) == 0:
                                cur.execute(_sql)
                        except Exception:
                            pass
                    # --- Observaciones: asegurar que no sea NOT NULL si hay datos legacy ---
                    # No forzamos; dejar NULL
            except Exception:
                pass

            # ---------------------------------------------------------
            # maestro_stock: ensure alias column + index (bidirectional sync DB <-> Firestore)
            # Idempotent: checks information_schema before ALTER.
            # Alias VARCHAR(300) for search (e.g., T10 for tornillo 10mm).
            # ---------------------------------------------------------
            try:
                # Ensure maestro_stock table exists with minimal DDL (covers fresh installs
                # that did not run the _ensure_tables from routes/maestro_stock).
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS `maestro_stock` (
                      `codigo` VARCHAR(40) COLLATE utf8mb4_unicode_ci NOT NULL,
                      `descripcion` TEXT COLLATE utf8mb4_unicode_ci NOT NULL,
                      `alias` VARCHAR(300) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Alias de busqueda, ej T10 para tornillo 10mm',
                      `stock` DECIMAL(10,2) NOT NULL DEFAULT 0.00,
                      `stock_minimo` DECIMAL(10,2) NOT NULL DEFAULT 0.00,
                      `ubicacion` VARCHAR(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
                      `precio_unitario` DECIMAL(12,2) NOT NULL DEFAULT 0.00,
                      `importancia` ENUM('CRITICO','ALTA FRECUENCIA','BASE') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'BASE',
                      `categoria` VARCHAR(80) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
                      `activo` TINYINT(1) NOT NULL DEFAULT 1,
                      `creado_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                      `actualizado_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                      PRIMARY KEY (`codigo`),
                      KEY `idx_maestro_stock_ubicacion` (`ubicacion`),
                      KEY `idx_maestro_stock_importancia` (`importancia`),
                      KEY `idx_maestro_stock_categoria` (`categoria`),
                      KEY `idx_maestro_stock_alias` (`alias`)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                )
                # If table already existed without alias, add column and index
                cur.execute(
                    """
                    SELECT COUNT(*) AS c FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME='maestro_stock' AND COLUMN_NAME='alias'
                    """
                )
                _ralias = cur.fetchone()
                if _ralias and int(_ralias.get("c", 0)) == 0:
                    try:
                        cur.execute(
                            """
                            ALTER TABLE `maestro_stock`
                            ADD COLUMN `alias` VARCHAR(300) COLLATE utf8mb4_unicode_ci DEFAULT NULL
                            COMMENT 'Alias de busqueda, ej T10 para tornillo 10mm' AFTER `descripcion`
                            """
                        )
                    except Exception:
                        # Fallback: try without AFTER (some MySQL versions / if column order differs)
                        try:
                            cur.execute(
                                """
                                ALTER TABLE `maestro_stock`
                                ADD COLUMN `alias` VARCHAR(300) COLLATE utf8mb4_unicode_ci DEFAULT NULL
                                COMMENT 'Alias de busqueda, ej T10 para tornillo 10mm'
                                """
                            )
                        except Exception:
                            pass
                # Ensure index on alias exists
                cur.execute(
                    """
                    SELECT COUNT(*) AS c FROM information_schema.STATISTICS
                    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME='maestro_stock' AND INDEX_NAME='idx_maestro_stock_alias'
                    """
                )
                _ridx_alias = cur.fetchone()
                if _ridx_alias and int(_ridx_alias.get("c", 0)) == 0:
                    try:
                        cur.execute("ALTER TABLE `maestro_stock` ADD INDEX `idx_maestro_stock_alias` (`alias`)")
                    except Exception:
                        pass
            except Exception:
                pass

        conn.commit()
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _verificar_jwt(token: str) -> dict[str, Any] | None:
    """Verifica JWT Bearer token. Retorna payload o None."""
    try:
        from jose import jwt as jose_jwt

        payload = jose_jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except Exception:
        return None


def _verificar_sesion_opaca(token: str) -> dict[str, Any] | None:
    """Fallback: valida token opaco de backend/usuarios (sesiones SQLite)."""
    if not token or len(token) < 10:
        return None
    from pathlib import Path
    import sqlite3

    try:
        base = Path(__file__).resolve().parent
        candidatos = [
            base.parent / "usuarios" / "data" / "usuarios.db",
            base.parent / "usuarios" / "usuarios.db",
            Path(r"C:\Users\Pañol\Desktop\sistemas_panol\Server\AppWebSalidas\backend\usuarios\data\usuarios.db"),
        ]
        db_path = next((p for p in candidatos if p.exists()), None)
        if not db_path:
            return None
        con = sqlite3.connect(str(db_path))
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute("SELECT * FROM sesiones WHERE token = ?", (token,))
        ses = cur.fetchone()
        if not ses:
            con.close()
            return None
        try:
            vence = datetime.fromisoformat(ses["vence_en"])
            if vence.tzinfo is None:
                vence = vence.replace(tzinfo=timezone.utc)
            ahora = datetime.now(timezone.utc)
            if vence < ahora:
                con.execute("DELETE FROM sesiones WHERE token = ?", (token,))
                con.commit()
                con.close()
                return None
        except Exception:
            pass
        cur.execute("SELECT * FROM usuarios WHERE id = ?", (ses["usuario_id"],))
        row = cur.fetchone()
        if not row or not row["activo"]:
            con.close()
            return None
        uid = int(row["id"])
        rol_base = str(row["rol_base"] or "")
        cur.execute("SELECT nivel FROM permisos WHERE usuario_id = ? AND modulo = 'salidas'", (uid,))
        prow = cur.fetchone()
        if prow:
            nivel = str(prow["nivel"] or "sin_acceso")
        else:
            nivel = PERMISO_POR_ROL.get(rol_base, {}).get("salidas", "sin_acceso")
        con.close()
        if nivel == "sin_acceso":
            return None
        return {"sub": str(uid), "usuario": str(row["usuario"]), "rol": rol_base, "id": uid, "nivel": nivel}
    except Exception:
        try:
            con.close()
        except Exception:
            pass
        return None


def verificar_permiso(token: str, permiso_requerido: str) -> dict[str, Any] | None:
    """Verifica JWT y permisos del modulo salidas.

    Soporta JWT (legado) y token opaco de backend/usuarios.
    Retorna payload si tiene permiso, None si no autenticado/sin permiso.
    """
    payload = _verificar_jwt(token)
    if payload:
        rol = payload.get("rol", "")
        permisos = PERMISO_POR_ROL.get(rol, {})
        nivel = permisos.get("salidas", "sin_acceso")
        if permiso_requerido.endswith(":lectura") and nivel in ("lectura", "escritura"):
            return payload
        if permiso_requerido.endswith(":escritura") and nivel == "escritura":
            return payload
        if nivel != "sin_acceso":
            return payload
        return None
    payload2 = _verificar_sesion_opaca(token)
    if not payload2:
        return None
    nivel2 = str(payload2.get("nivel") or PERMISO_POR_ROL.get(str(payload2.get("rol") or ""), {}).get("salidas", "sin_acceso"))
    if permiso_requerido.endswith(":lectura") and nivel2 in ("lectura", "escritura"):
        return payload2
    if permiso_requerido.endswith(":escritura") and nivel2 == "escritura":
        return payload2
    if nivel2 != "sin_acceso":
        return payload2
    return None
