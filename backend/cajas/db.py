# -*- coding: utf-8 -*-
"""Persistencia MariaDB — Cajas de Herramientas.

Conexion pool a MariaDB (ruta XAMPP).
Tablas: cajas_cajas, cajas_herramientas (schema ya existe en panol).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pymysql import connections
from pymysql.err import IntegrityError
from pymysql.cursors import DictCursor
from config import (
    DB_DSN, DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME,
    JWT_SECRET, JWT_ALGORITHM, PERMISO_POR_ROL,
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
    """Retorna una conexión activa desde el pool."""
    conn = _get_pool()
    if not conn.open:
        conn = connections.Connection(
            host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD,
            database=DB_NAME, charset="utf8mb4", cursorclass=DictCursor,
        )
    return conn


def init_db() -> None:
    """Verifica que las tablas cajas_cajas y cajas_herramientas existan (idempotente)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS cajas_cajas (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    codigo VARCHAR(100) NOT NULL UNIQUE,
                    descripcion VARCHAR(255) NULL,
                    ubicacion VARCHAR(100) NULL,
                    activa BOOLEAN NOT NULL DEFAULT 1,
                    INDEX idx_cajas_codigo (codigo),
                    INDEX idx_cajas_activa (activa)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS cajas_herramientas (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    codigo VARCHAR(100) NOT NULL UNIQUE,
                    descripcion VARCHAR(255) NULL,
                    categoria VARCHAR(50) NOT NULL DEFAULT 'HERRAMIENTA',
                    unidad VARCHAR(20) NOT NULL DEFAULT 'UND',
                    articulo_codigo VARCHAR(100) NULL,
                    INDEX idx_herramientas_codigo (codigo),
                    INDEX idx_herramientas_categoria (categoria)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            # --- Caja Ideal versionado (Slice 1) ---
            # Nota: ids autoincrement, singleton activa via transacción en store
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS cajas_caja_ideal (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    nombre VARCHAR(100) NOT NULL,
                    descripcion TEXT NULL,
                    activa TINYINT(1) NOT NULL DEFAULT 0,
                    vigente_desde DATETIME NOT NULL,
                    creado_por INT NULL,
                    creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_ideal_activa (activa),
                    INDEX idx_ideal_vigente (vigente_desde)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            # Crear detalle con FK inline; si falla por orden/tipo, fallback a ALTER se maneja abajo
            # Nota: cajas_herramientas.id es INT UNSIGNED, por lo que herramienta_id debe ser UNSIGNED
            try:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS cajas_caja_ideal_detalle (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        caja_ideal_id INT NOT NULL,
                        herramienta_id INT UNSIGNED NOT NULL,
                        cantidad_minima INT NOT NULL DEFAULT 1,
                        articulo_codigo VARCHAR(100) NULL,
                        UNIQUE KEY uq_ideal_herramienta (caja_ideal_id, herramienta_id),
                        CONSTRAINT fk_ideal_cab FOREIGN KEY (caja_ideal_id) REFERENCES cajas_caja_ideal(id) ON DELETE CASCADE,
                        CONSTRAINT fk_ideal_herr FOREIGN KEY (herramienta_id) REFERENCES cajas_herramientas(id) ON DELETE RESTRICT
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                )
            except Exception:
                # Fallback: crear sin FK y agregar vía ALTER si no existen
                try:
                    conn.rollback()
                except Exception:
                    pass
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS cajas_caja_ideal_detalle (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        caja_ideal_id INT NOT NULL,
                        herramienta_id INT UNSIGNED NOT NULL,
                        cantidad_minima INT NOT NULL DEFAULT 1,
                        articulo_codigo VARCHAR(100) NULL,
                        UNIQUE KEY uq_ideal_herramienta (caja_ideal_id, herramienta_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                )
                # Intentar agregar FKs si no existen (ignorar si ya existen)
                try:
                    cur.execute(
                        "ALTER TABLE cajas_caja_ideal_detalle ADD CONSTRAINT fk_ideal_cab FOREIGN KEY (caja_ideal_id) REFERENCES cajas_caja_ideal(id) ON DELETE CASCADE"
                    )
                except Exception:
                    pass
                try:
                    cur.execute(
                        "ALTER TABLE cajas_caja_ideal_detalle ADD CONSTRAINT fk_ideal_herr FOREIGN KEY (herramienta_id) REFERENCES cajas_herramientas(id) ON DELETE RESTRICT"
                    )
                except Exception:
                    pass
            # Post-check: asegurar FK herramienta existe (corrige tablas creadas previamente con INT signed)
            try:
                cur.execute(
                    "SELECT COUNT(*) c FROM information_schema.TABLE_CONSTRAINTS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'cajas_caja_ideal_detalle' AND CONSTRAINT_NAME = 'fk_ideal_herr'"
                )
                has_fk = cur.fetchone()["c"] > 0
                if not has_fk:
                    # Intentar convertir columna a UNSIGNED si aún es signed
                    try:
                        cur.execute("ALTER TABLE cajas_caja_ideal_detalle MODIFY herramienta_id INT UNSIGNED NOT NULL")
                    except Exception:
                        pass
                    try:
                        cur.execute(
                            "ALTER TABLE cajas_caja_ideal_detalle ADD CONSTRAINT fk_ideal_herr FOREIGN KEY (herramienta_id) REFERENCES cajas_herramientas(id) ON DELETE RESTRICT"
                        )
                    except Exception:
                        pass
            except Exception:
                pass
            # --- Fase 2: limpieza_historial y asignaciones (DDL idempotente) ---
            # cajas_limpieza_historial: auditoría de eventos de limpieza
            # personal.id es INT UNSIGNED → match con UNSIGNED
            try:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS cajas_limpieza_historial (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        caja_id INT UNSIGNED NOT NULL,
                        tecnico_id INT UNSIGNED NOT NULL,
                        fecha DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        estado ENUM('pendiente','realizada','vencida') NOT NULL DEFAULT 'pendiente',
                        responsable_id INT UNSIGNED NULL,
                        observaciones TEXT NULL,
                        creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_limpieza_caja_fecha (caja_id, fecha),
                        INDEX idx_limpieza_estado_fecha (estado, fecha),
                        INDEX idx_limpieza_tecnico (tecnico_id),
                        CONSTRAINT fk_limpieza_caja FOREIGN KEY (caja_id) REFERENCES cajas_cajas(id) ON DELETE RESTRICT,
                        CONSTRAINT fk_limpieza_tec FOREIGN KEY (tecnico_id) REFERENCES personal(id) ON DELETE RESTRICT,
                        CONSTRAINT fk_limpieza_resp FOREIGN KEY (responsable_id) REFERENCES personal(id) ON DELETE RESTRICT
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                )
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
                # Fallback sin FK (posible mismatch de tipos) — crear tabla y luego intentar ALTER
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS cajas_limpieza_historial (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        caja_id INT UNSIGNED NOT NULL,
                        tecnico_id INT UNSIGNED NOT NULL,
                        fecha DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        estado ENUM('pendiente','realizada','vencida') NOT NULL DEFAULT 'pendiente',
                        responsable_id INT UNSIGNED NULL,
                        observaciones TEXT NULL,
                        creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_limpieza_caja_fecha (caja_id, fecha),
                        INDEX idx_limpieza_estado_fecha (estado, fecha),
                        INDEX idx_limpieza_tecnico (tecnico_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                )
                for fk_sql in [
                    "ALTER TABLE cajas_limpieza_historial ADD CONSTRAINT fk_limpieza_caja FOREIGN KEY (caja_id) REFERENCES cajas_cajas(id) ON DELETE RESTRICT",
                    "ALTER TABLE cajas_limpieza_historial ADD CONSTRAINT fk_limpieza_tec FOREIGN KEY (tecnico_id) REFERENCES personal(id) ON DELETE RESTRICT",
                    "ALTER TABLE cajas_limpieza_historial ADD CONSTRAINT fk_limpieza_resp FOREIGN KEY (responsable_id) REFERENCES personal(id) ON DELETE RESTRICT",
                ]:
                    try:
                        cur.execute(fk_sql)
                    except Exception:
                        pass
            # cajas_asignaciones: asignaciones versionadas (singleton activa por caja vía transacción en store)
            # Uniqueness enforced in store transaction, not via UNIQUE constraint — ver store.crear_asignacion
            try:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS cajas_asignaciones (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        caja_id INT UNSIGNED NOT NULL,
                        tecnico_id INT UNSIGNED NOT NULL,
                        desde DATE NOT NULL,
                        hasta DATE NULL,
                        activa TINYINT(1) NOT NULL DEFAULT 1,
                        creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_asig_caja (caja_id),
                        INDEX idx_asig_tecnico (tecnico_id),
                        INDEX idx_asig_activa (activa),
                        CONSTRAINT fk_asig_caja FOREIGN KEY (caja_id) REFERENCES cajas_cajas(id) ON DELETE RESTRICT,
                        CONSTRAINT fk_asig_tec FOREIGN KEY (tecnico_id) REFERENCES personal(id) ON DELETE RESTRICT
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                )
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS cajas_asignaciones (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        caja_id INT UNSIGNED NOT NULL,
                        tecnico_id INT UNSIGNED NOT NULL,
                        desde DATE NOT NULL,
                        hasta DATE NULL,
                        activa TINYINT(1) NOT NULL DEFAULT 1,
                        creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_asig_caja (caja_id),
                        INDEX idx_asig_tecnico (tecnico_id),
                        INDEX idx_asig_activa (activa)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                )
                for fk_sql in [
                    "ALTER TABLE cajas_asignaciones ADD CONSTRAINT fk_asig_caja FOREIGN KEY (caja_id) REFERENCES cajas_cajas(id) ON DELETE RESTRICT",
                    "ALTER TABLE cajas_asignaciones ADD CONSTRAINT fk_asig_tec FOREIGN KEY (tecnico_id) REFERENCES personal(id) ON DELETE RESTRICT",
                ]:
                    try:
                        cur.execute(fk_sql)
                    except Exception:
                        pass
        conn.commit()
    finally:
        conn.close()


def _verificar_jwt(token: str) -> dict[str, Any] | None:
    """Verifica JWT Bearer token. Retorna payload o None."""
    try:
        from jose import jwt as jose_jwt
        payload = jose_jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except Exception:
        return None


def _verificar_sesion_opaca(token: str) -> dict[str, Any] | None:
    """Fallback: valida token opaco de backend/usuarios (sesiones SQLite).
    Retorna payload minimal con rol si el token es válido y tiene permiso cajas.
    """
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
        from datetime import datetime, timezone, timedelta
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
        cur.execute("SELECT nivel FROM permisos WHERE usuario_id = ? AND modulo = 'cajas'", (uid,))
        prow = cur.fetchone()
        if prow:
            nivel = str(prow["nivel"] or "sin_acceso")
        else:
            nivel = PERMISO_POR_ROL.get(rol_base, {}).get("cajas", "sin_acceso")
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
    """Verifica JWT y permisos del módulo cajas (strict exact match).

    Soporta JWT (legado) y token opaco de backend/usuarios (real).
    Reglas estrictas:
    - :lectura → nivel in (lectura, escritura)
    - :escritura → nivel == escritura
    - else → None (sin catch-all)
    Retorna el payload si tiene el permiso, None si no autenticado o sin permiso.
    """
    payload = _verificar_jwt(token)
    if payload:
        rol = payload.get("rol", "")
        permisos = PERMISO_POR_ROL.get(rol, {})
        nivel = permisos.get("cajas", "sin_acceso")
        if permiso_requerido.endswith(":lectura") and nivel in ("lectura", "escritura"):
            return payload
        if permiso_requerido.endswith(":escritura") and nivel == "escritura":
            return payload
        return None
    payload2 = _verificar_sesion_opaca(token)
    if not payload2:
        return None
    nivel2 = str(payload2.get("nivel") or PERMISO_POR_ROL.get(str(payload2.get("rol") or ""), {}).get("cajas", "sin_acceso"))
    if permiso_requerido.endswith(":lectura") and nivel2 in ("lectura", "escritura"):
        return payload2
    if permiso_requerido.endswith(":escritura") and nivel2 == "escritura":
        return payload2
    return None
