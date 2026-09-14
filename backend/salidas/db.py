# -*- coding: utf-8 -*-
"""Persistencia MariaDB — Salidas (paNol).

Conexion a MariaDB (XAMPP) base `panol`.
Tablas: salida_historial, salida_movimientos_diario, salida_otif
Esquema idempotente definido en Server/docs/salidas_migracion_v1.sql
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
    """Crea las 3 tablas salida_* si no existen (idempotente).

    DDL identico a Server/docs/salidas_migracion_v1.sql pero ejecutado
    via Python para que el servicio pueda auto-inicializarse.
    Requiere que existan las tablas GENERALES `areas` y `personal`;
    si no existen la FK fallara - en ese caso ejecutar primero la
    migracion de personal/cajas.
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
            # salida_movimientos_diario - libro diario por fecha
            # ---------------------------------------------------------
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS `salida_movimientos_diario` (
                  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
                  `fecha` DATE NOT NULL COMMENT 'fecha cierre diario UNIQUE',
                  `total_movimientos` INT UNSIGNED NOT NULL DEFAULT 0,
                  `total_cantidad` DECIMAL(12,2) NOT NULL DEFAULT 0.00,
                  `total_monto` DECIMAL(12,2) NOT NULL DEFAULT 0.00,
                  `devoluciones` INT UNSIGNED NOT NULL DEFAULT 0,
                  `estado` ENUM('abierto','cerrado','anulado') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'abierto',
                  `cerrado_por` VARCHAR(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
                  `cerrado_en` DATETIME DEFAULT NULL,
                  `observaciones` TEXT COLLATE utf8mb4_unicode_ci DEFAULT NULL,
                  `creado_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  `actualizado_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                  PRIMARY KEY (`id`),
                  UNIQUE KEY `uq_salida_diario_fecha` (`fecha`),
                  KEY `idx_salida_diario_estado` (`estado`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Libro diario - cierre por fecha'
                """
            )

            # ---------------------------------------------------------
            # salida_otif - medidor OTIF (On Time In Full)
            # ---------------------------------------------------------
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS `salida_otif` (
                  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
                  `salida_id` INT UNSIGNED DEFAULT NULL COMMENT 'FK salida_historial',
                  `solicitud_id` INT UNSIGNED DEFAULT NULL COMMENT 'FK solicitudes_pedidos',
                  `codigo` VARCHAR(40) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
                  `descripcion` TEXT COLLATE utf8mb4_unicode_ci DEFAULT NULL,
                  `fecha_solicitada` DATE DEFAULT NULL,
                  `fecha_comprometida` DATE NOT NULL COMMENT 'fecha promesa',
                  `fecha_entrega_real` DATE DEFAULT NULL COMMENT 'NULL=pendiente',
                  `cantidad_solicitada` DECIMAL(10,2) NOT NULL,
                  `cantidad_entregada` DECIMAL(10,2) NOT NULL DEFAULT 0.00,
                  `en_tiempo` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '1 si entrega <= compromiso',
                  `completo` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '1 si entregada >= solicitada',
                  `otif` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '1 si en_tiempo AND completo',
                  `motivo_retraso` VARCHAR(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
                  `motivo_faltante` VARCHAR(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
                  `responsable_id` INT UNSIGNED DEFAULT NULL COMMENT 'FK personal',
                  `area_id` INT UNSIGNED DEFAULT NULL COMMENT 'FK areas',
                  `periodo` DATE DEFAULT NULL COMMENT 'primer dia mes de fecha_comprometida',
                  `observaciones` TEXT COLLATE utf8mb4_unicode_ci DEFAULT NULL,
                  `creado_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  `actualizado_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                  PRIMARY KEY (`id`),
                  KEY `idx_salida_otif_periodo` (`periodo`),
                  KEY `idx_salida_otif_fecha_comprometida` (`fecha_comprometida`),
                  KEY `idx_salida_otif_fecha_entrega_real` (`fecha_entrega_real`),
                  KEY `idx_salida_otif_responsable` (`responsable_id`),
                  KEY `idx_salida_otif_area` (`area_id`),
                  KEY `idx_salida_otif_otif` (`otif`),
                  KEY `idx_salida_otif_periodo_otif` (`periodo`, `otif`),
                  KEY `idx_salida_otif_salida` (`salida_id`),
                  KEY `idx_salida_otif_solicitud` (`solicitud_id`),
                  CONSTRAINT `fk_salida_otif_salida` FOREIGN KEY (`salida_id`) REFERENCES `salida_historial` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
                  CONSTRAINT `fk_salida_otif_responsable` FOREIGN KEY (`responsable_id`) REFERENCES `personal` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
                  CONSTRAINT `fk_salida_otif_area` FOREIGN KEY (`area_id`) REFERENCES `areas` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Medidor OTIF por entrega'
                """
            )

            # FK a solicitudes_pedidos es opcional - solo si la tabla existe.
            # Intentar agregarla si no existe aun (idempotente via try).
            try:
                cur.execute(
                    """
                    SELECT COUNT(*) AS c FROM information_schema.TABLE_CONSTRAINTS
                    WHERE CONSTRAINT_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'salida_otif'
                      AND CONSTRAINT_NAME = 'fk_salida_otif_solicitud'
                    """
                )
                row = cur.fetchone()
                if not row or int(row.get("c", 0)) == 0:
                    # Verificar que la tabla referenciada exista antes de crear FK
                    cur.execute(
                        """
                        SELECT COUNT(*) AS c FROM information_schema.TABLES
                        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'solicitudes_pedidos'
                        """
                    )
                    row2 = cur.fetchone()
                    if row2 and int(row2.get("c", 0)) > 0:
                        cur.execute(
                            """
                            ALTER TABLE `salida_otif`
                              ADD CONSTRAINT `fk_salida_otif_solicitud`
                              FOREIGN KEY (`solicitud_id`) REFERENCES `solicitudes_pedidos` (`id`)
                              ON DELETE SET NULL ON UPDATE CASCADE
                            """
                        )
            except Exception:
                # Si falla por FK existente o tabla faltante, ignorar - migracion SQL lo cubre
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
