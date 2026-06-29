# -*- coding: utf-8 -*-
"""
catalogo_cache.py — Persistencia local del catálogo (SQLite).

Evita volver a leer Firestore si la API se reinicia el mismo día después
de la sincronización matutina. SOLO LECTURA respecto a Firebase.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from typing import Any, Optional

DB_PATH = os.environ.get(
    "ETIQUETAS_CATALOGO_CACHE_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "catalogo_cache.db"),
)

META_ULTIMA_SYNC = "ultima_sync_iso"


def _conectar() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _conectar() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS catalogo (
                doc_id      TEXT PRIMARY KEY,
                codigo      TEXT NOT NULL,
                descripcion TEXT NOT NULL DEFAULT '',
                ubicacion   TEXT NOT NULL DEFAULT ''
            );
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_catalogo_codigo ON catalogo (codigo);"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS catalogo_meta (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )


def obtener_ultima_sync() -> Optional[datetime]:
    with _conectar() as conn:
        row = conn.execute(
            "SELECT value FROM catalogo_meta WHERE key = ?;", (META_ULTIMA_SYNC,)
        ).fetchone()
    if not row:
        return None
    try:
        return datetime.fromisoformat(row["value"])
    except ValueError:
        return None


def tiene_datos() -> bool:
    with _conectar() as conn:
        row = conn.execute("SELECT 1 FROM catalogo LIMIT 1;").fetchone()
    return row is not None


def marcar_sync(cuando: datetime) -> None:
    with _conectar() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO catalogo_meta (key, value) VALUES (?, ?);",
            (META_ULTIMA_SYNC, cuando.isoformat()),
        )


def cargar_todos() -> list[dict[str, str]]:
    with _conectar() as conn:
        filas = conn.execute(
            "SELECT doc_id, codigo, descripcion, ubicacion FROM catalogo;"
        ).fetchall()
    return [
        {
            "doc_id": f["doc_id"],
            "codigo": f["codigo"],
            "descripcion": f["descripcion"],
            "ubicacion": f["ubicacion"],
        }
        for f in filas
    ]


def reemplazar_todo(items: list[dict[str, str]], cuando: datetime) -> None:
    with _conectar() as conn:
        conn.execute("DELETE FROM catalogo;")
        conn.executemany(
            """
            INSERT INTO catalogo (doc_id, codigo, descripcion, ubicacion)
            VALUES (?, ?, ?, ?);
            """,
            [
                (
                    i["doc_id"],
                    i["codigo"],
                    i["descripcion"],
                    i["ubicacion"],
                )
                for i in items
            ],
        )
        conn.execute(
            "INSERT OR REPLACE INTO catalogo_meta (key, value) VALUES (?, ?);",
            (META_ULTIMA_SYNC, cuando.isoformat()),
        )


def upsert_item(doc_id: str, codigo: str, descripcion: str, ubicacion: str) -> None:
    with _conectar() as conn:
        conn.execute(
            """
            INSERT INTO catalogo (doc_id, codigo, descripcion, ubicacion)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(doc_id) DO UPDATE SET
                codigo = excluded.codigo,
                descripcion = excluded.descripcion,
                ubicacion = excluded.ubicacion;
            """,
            (doc_id, codigo, descripcion, ubicacion),
        )


def eliminar_item(doc_id: str) -> None:
    with _conectar() as conn:
        conn.execute("DELETE FROM catalogo WHERE doc_id = ?;", (doc_id,))
