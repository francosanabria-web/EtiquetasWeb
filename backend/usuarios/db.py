# -*- coding: utf-8 -*-
"""Persistencia SQLite — Usuarios, permisos por usuario y sesiones.

Contraseñas: PBKDF2-HMAC-SHA256 + salt por usuario (librería estándar).
Sesiones: token opaco con vencimiento. Todo local en la PC de pañol.
Migración futura a la base central: este módulo aísla el acceso a datos.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from config import DATA_DIR, DB_PATH, MODULOS, NIVELES, ROLES, SESSION_TTL_HORAS, plantilla_rol

_PBKDF2_ITER = 200_000

# Usuarios iniciales (continuidad con las cuentas demo previas).
_SEED = [
    ("admin", "Administrador", "admin@panol.local", "admin123", "admin"),
    ("panol", "Pañol", "panol@panol.local", "panol123", "panol"),
    ("supervisor", "Supervisor", "supervisor@panol.local", "supervisor123", "supervisor"),
    ("jefatura", "Jefatura", "jefatura@panol.local", "jefatura123", "jefatura"),
]


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _conectar() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


# --------------------------------------------------------------------------- #
# Contraseñas
# --------------------------------------------------------------------------- #
def hash_password(clave: str, salt: str | None = None) -> tuple[str, str]:
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", clave.encode("utf-8"), bytes.fromhex(salt), _PBKDF2_ITER)
    return dk.hex(), salt


def verificar_password(clave: str, hash_hex: str, salt: str) -> bool:
    calc, _ = hash_password(clave, salt)
    return hmac.compare_digest(calc, hash_hex)


# --------------------------------------------------------------------------- #
# Esquema + seed
# --------------------------------------------------------------------------- #
def init_db() -> None:
    with _conectar() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT NOT NULL UNIQUE,
                nombre TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL DEFAULT '',
                hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                rol_base TEXT NOT NULL DEFAULT 'jefatura',
                activo INTEGER NOT NULL DEFAULT 1,
                creado_en TEXT NOT NULL,
                actualizado_en TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS permisos (
                usuario_id INTEGER NOT NULL,
                modulo TEXT NOT NULL,
                nivel TEXT NOT NULL DEFAULT 'sin_acceso',
                PRIMARY KEY (usuario_id, modulo),
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS sesiones (
                token TEXT PRIMARY KEY,
                usuario_id INTEGER NOT NULL,
                creado_en TEXT NOT NULL,
                vence_en TEXT NOT NULL,
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
            );
            """
        )
        conn.commit()
        n = conn.execute("SELECT COUNT(*) c FROM usuarios").fetchone()["c"]
        if n == 0:
            for usuario, nombre, email, clave, rol in _SEED:
                _crear_interno(conn, usuario, nombre, email, clave, rol, plantilla_rol(rol), activo=True)
            conn.commit()


def _crear_interno(
    conn: sqlite3.Connection,
    usuario: str,
    nombre: str,
    email: str,
    clave: str,
    rol: str,
    permisos: dict[str, str],
    activo: bool,
) -> int:
    h, salt = hash_password(clave)
    ahora = _iso(_ahora())
    cur = conn.execute(
        """
        INSERT INTO usuarios (usuario, nombre, email, hash, salt, rol_base, activo, creado_en, actualizado_en)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (usuario, nombre, email, h, salt, rol, 1 if activo else 0, ahora, ahora),
    )
    uid = int(cur.lastrowid)
    _guardar_permisos(conn, uid, permisos)
    return uid


def _guardar_permisos(conn: sqlite3.Connection, uid: int, permisos: dict[str, str]) -> None:
    for modulo in MODULOS:
        nivel = permisos.get(modulo, "sin_acceso")
        if nivel not in NIVELES:
            nivel = "sin_acceso"
        conn.execute(
            """
            INSERT INTO permisos (usuario_id, modulo, nivel) VALUES (?, ?, ?)
            ON CONFLICT(usuario_id, modulo) DO UPDATE SET nivel = excluded.nivel
            """,
            (uid, modulo, nivel),
        )


# --------------------------------------------------------------------------- #
# Lectura
# --------------------------------------------------------------------------- #
def _permisos_de(conn: sqlite3.Connection, uid: int) -> dict[str, str]:
    rows = conn.execute("SELECT modulo, nivel FROM permisos WHERE usuario_id = ?", (uid,)).fetchall()
    m = {r["modulo"]: r["nivel"] for r in rows}
    return {mod: m.get(mod, "sin_acceso") for mod in MODULOS}


def _usuario_dict(conn: sqlite3.Connection, row: sqlite3.Row, incluir_permisos: bool = True) -> dict[str, Any]:
    d = {
        "id": int(row["id"]),
        "usuario": row["usuario"],
        "nombre": row["nombre"],
        "email": row["email"],
        "rol": row["rol_base"],
        "activo": bool(row["activo"]),
        "creado_en": row["creado_en"],
    }
    if incluir_permisos:
        d["permisos"] = _permisos_de(conn, int(row["id"]))
    return d


def listar_usuarios() -> list[dict[str, Any]]:
    with _conectar() as conn:
        rows = conn.execute("SELECT * FROM usuarios ORDER BY usuario").fetchall()
        return [_usuario_dict(conn, r) for r in rows]


def obtener_usuario(uid: int) -> dict[str, Any] | None:
    with _conectar() as conn:
        row = conn.execute("SELECT * FROM usuarios WHERE id = ?", (uid,)).fetchone()
        return _usuario_dict(conn, row) if row else None


# --------------------------------------------------------------------------- #
# Alta / edición
# --------------------------------------------------------------------------- #
def _validar_permisos(permisos: Any) -> dict[str, str] | None:
    if not isinstance(permisos, dict):
        return None
    out = {}
    for mod in MODULOS:
        nivel = str(permisos.get(mod, "sin_acceso"))
        out[mod] = nivel if nivel in NIVELES else "sin_acceso"
    return out


def crear_usuario(data: dict[str, Any]) -> dict[str, Any]:
    usuario = str(data.get("usuario") or "").strip().lower()
    if not usuario or not all(c.isalnum() or c in "._-" for c in usuario):
        raise ValueError("Usuario inválido (solo letras, números, . _ -).")
    nombre = str(data.get("nombre") or "").strip() or usuario
    clave = str(data.get("clave") or "")
    if len(clave) < 4:
        raise ValueError("La contraseña debe tener al menos 4 caracteres.")
    rol = str(data.get("rol") or "jefatura").strip().lower()
    if rol not in ROLES:
        raise ValueError(f"Rol inválido: {rol}")
    email = str(data.get("email") or "").strip() or f"{usuario}@panol.local"
    permisos = _validar_permisos(data.get("permisos")) or plantilla_rol(rol)
    with _conectar() as conn:
        existe = conn.execute("SELECT 1 FROM usuarios WHERE usuario = ?", (usuario,)).fetchone()
        if existe:
            raise ValueError("Ya existe un usuario con ese nombre.")
        uid = _crear_interno(conn, usuario, nombre, email, clave, rol, permisos, activo=True)
        conn.commit()
        row = conn.execute("SELECT * FROM usuarios WHERE id = ?", (uid,)).fetchone()
        return _usuario_dict(conn, row)


def actualizar_usuario(uid: int, data: dict[str, Any]) -> dict[str, Any] | None:
    with _conectar() as conn:
        row = conn.execute("SELECT * FROM usuarios WHERE id = ?", (uid,)).fetchone()
        if not row:
            return None
        campos, valores = [], []
        if "nombre" in data:
            campos.append("nombre = ?")
            valores.append(str(data["nombre"] or "").strip())
        if "email" in data:
            campos.append("email = ?")
            valores.append(str(data["email"] or "").strip())
        if "activo" in data:
            campos.append("activo = ?")
            valores.append(1 if data["activo"] else 0)
        if "rol" in data:
            rol = str(data["rol"] or "").strip().lower()
            if rol not in ROLES:
                raise ValueError(f"Rol inválido: {rol}")
            campos.append("rol_base = ?")
            valores.append(rol)
        if campos:
            campos.append("actualizado_en = ?")
            valores.append(_iso(_ahora()))
            valores.append(uid)
            conn.execute(f"UPDATE usuarios SET {', '.join(campos)} WHERE id = ?", valores)
        if "permisos" in data:
            permisos = _validar_permisos(data.get("permisos"))
            if permisos is None:
                raise ValueError("Permisos inválidos.")
            _guardar_permisos(conn, uid, permisos)
        conn.commit()
        row = conn.execute("SELECT * FROM usuarios WHERE id = ?", (uid,)).fetchone()
        return _usuario_dict(conn, row)


def set_password(uid: int, nueva: str) -> bool:
    if len(nueva) < 4:
        raise ValueError("La contraseña debe tener al menos 4 caracteres.")
    h, salt = hash_password(nueva)
    with _conectar() as conn:
        cur = conn.execute(
            "UPDATE usuarios SET hash = ?, salt = ?, actualizado_en = ? WHERE id = ?",
            (h, salt, _iso(_ahora()), uid),
        )
        conn.commit()
        return cur.rowcount > 0


def cambiar_mi_password(uid: int, actual: str, nueva: str) -> None:
    with _conectar() as conn:
        row = conn.execute("SELECT hash, salt FROM usuarios WHERE id = ?", (uid,)).fetchone()
        if not row or not verificar_password(actual, row["hash"], row["salt"]):
            raise ValueError("La contraseña actual no es correcta.")
    set_password(uid, nueva)


def eliminar_usuario(uid: int) -> bool:
    with _conectar() as conn:
        cur = conn.execute("DELETE FROM usuarios WHERE id = ?", (uid,))
        conn.commit()
        return cur.rowcount > 0


def contar_admins_activos(excluir_id: int | None = None) -> int:
    with _conectar() as conn:
        sql = "SELECT COUNT(*) c FROM usuarios WHERE rol_base = 'admin' AND activo = 1"
        params: list[Any] = []
        if excluir_id is not None:
            sql += " AND id <> ?"
            params.append(excluir_id)
        return int(conn.execute(sql, params).fetchone()["c"])


# --------------------------------------------------------------------------- #
# Login / sesiones
# --------------------------------------------------------------------------- #
def autenticar(usuario: str, clave: str) -> dict[str, Any] | None:
    q = str(usuario or "").strip().lower()
    with _conectar() as conn:
        row = conn.execute("SELECT * FROM usuarios WHERE usuario = ?", (q,)).fetchone()
        if not row or not row["activo"]:
            return None
        if not verificar_password(clave, row["hash"], row["salt"]):
            return None
        return _usuario_dict(conn, row)


def crear_sesion(uid: int) -> str:
    token = secrets.token_urlsafe(32)
    ahora = _ahora()
    vence = ahora + timedelta(hours=SESSION_TTL_HORAS)
    with _conectar() as conn:
        conn.execute(
            "INSERT INTO sesiones (token, usuario_id, creado_en, vence_en) VALUES (?, ?, ?, ?)",
            (token, uid, _iso(ahora), _iso(vence)),
        )
        conn.commit()
    return token


def usuario_por_token(token: str) -> dict[str, Any] | None:
    if not token:
        return None
    with _conectar() as conn:
        ses = conn.execute("SELECT * FROM sesiones WHERE token = ?", (token,)).fetchone()
        if not ses:
            return None
        try:
            vence = datetime.fromisoformat(ses["vence_en"])
        except ValueError:
            vence = _ahora() - timedelta(seconds=1)
        if vence < _ahora():
            conn.execute("DELETE FROM sesiones WHERE token = ?", (token,))
            conn.commit()
            return None
        row = conn.execute("SELECT * FROM usuarios WHERE id = ?", (ses["usuario_id"],)).fetchone()
        if not row or not row["activo"]:
            return None
        return _usuario_dict(conn, row)


def borrar_sesion(token: str) -> None:
    with _conectar() as conn:
        conn.execute("DELETE FROM sesiones WHERE token = ?", (token,))
        conn.commit()
