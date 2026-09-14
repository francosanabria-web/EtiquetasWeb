# -*- coding: utf-8 -*-
"""Persistencia MariaDB — Personal y areas.

Conexion pool a MariaDB (ruta XAMPP).
Reutiliza el esquema definido en la propuesta:
- areas(id PK, nombre VARCHAR UNIQUE)
- personal(id PK, legajo UNIQUE nullable, nombre UNIQUE, email UNIQUE nullable,
  area_id FK->areas(id), tipo ENUM, activo BOOLEAN)
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
    """Crea las tablas areas y personal si no existen (idempotente)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS areas (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    nombre VARCHAR(100) NOT NULL UNIQUE,
                    activo BOOLEAN NOT NULL DEFAULT 1
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS personal (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    legajo VARCHAR(50) UNIQUE NULL,
                    nombre VARCHAR(150) NOT NULL UNIQUE,
                    email VARCHAR(150) UNIQUE NULL,
                    area_id INT NULL,
                    tipo ENUM('tecnico','supervisor','produccion','generico','panol')
                        NOT NULL DEFAULT 'tecnico',
                    activo BOOLEAN NOT NULL DEFAULT 1,
                    CONSTRAINT fk_personal_area FOREIGN KEY (area_id)
                        REFERENCES areas(id) ON DELETE RESTRICT
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
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
    Retorna payload minimal con rol si el token es válido y tiene permiso personal.
    """
    if not token or len(token) < 10:
        return None
    # Usuarios DB está en backend/usuarios/data/usuarios.db (ver usuarios/config.py)
    from pathlib import Path
    import sqlite3

    # Resolver ruta relativa al proyecto (personal -> ../usuarios/data/usuarios.db)
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
        # Verificar vencimiento
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
        # Buscar permiso específico en tabla permisos
        cur.execute("SELECT nivel FROM permisos WHERE usuario_id = ? AND modulo = 'personal'", (uid,))
        prow = cur.fetchone()
        if prow:
            nivel = str(prow["nivel"] or "sin_acceso")
        else:
            # Fallback a plantilla por rol
            nivel = PERMISO_POR_ROL.get(rol_base, {}).get("personal", "sin_acceso")
        con.close()
        if nivel == "sin_acceso":
            return None
        # Payload compatible con el resto del servicio
        return {"sub": str(uid), "usuario": str(row["usuario"]), "rol": rol_base, "id": uid, "nivel": nivel}
    except Exception:
        try:
            con.close()
        except Exception:
            pass
        return None


def verificar_permiso(token: str, permiso_requerido: str) -> dict[str, Any] | None:
    """Verifica JWT y permisos del módulo personal.
    Soporta JWT (legado) y token opaco de backend/usuarios (real).
    Retorna el payload si tiene el permiso, None si no autenticado o sin permiso.
    """
    # 1) Intentar JWT
    payload = _verificar_jwt(token)
    if payload:
        rol = payload.get("rol", "")
        permisos = PERMISO_POR_ROL.get(rol, {})
        nivel = permisos.get("personal", "sin_acceso")
        # Si requiere lectura, lectura o escritura sirven; si requiere escritura, solo escritura
        if permiso_requerido.endswith(":lectura") and nivel in ("lectura", "escritura"):
            return payload
        if permiso_requerido.endswith(":escritura") and nivel == "escritura":
            return payload
        if nivel != "sin_acceso":
            # Compatibilidad: si no se parsea el sufijo, cualquier nivel no sin_acceso
            return payload
        return None
    # 2) Fallback a sesión opaca (usuarios)
    payload2 = _verificar_sesion_opaca(token)
    if not payload2:
        return None
    nivel2 = str(payload2.get("nivel") or PERMISO_POR_ROL.get(str(payload2.get("rol") or ""), {}).get("personal", "sin_acceso"))
    if permiso_requerido.endswith(":lectura") and nivel2 in ("lectura", "escritura"):
        return payload2
    if permiso_requerido.endswith(":escritura") and nivel2 == "escritura":
        return payload2
    if nivel2 != "sin_acceso":
        return payload2
    return None
