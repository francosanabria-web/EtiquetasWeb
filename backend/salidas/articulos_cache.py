# -*- coding: utf-8 -*-
"""Caché local diaria de artículos (SQLite) — misma lección que etiquetas.

Evita releer Firestore si el servicio reinicia el mismo día.
La fuente de verdad operativa del stock en Fase 1 es el Excel de prueba;
Firestore se actualiza al confirmar salidas y se puede sincronizar 1×/día.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from config import cache_db_path

META_ULTIMA_SYNC = "ultima_sync_iso"
META_ULTIMA_PULL = "ultima_pull_firestore_iso"


def _conectar() -> sqlite3.Connection:
    path = cache_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _conectar() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS articulos (
                doc_id     TEXT PRIMARY KEY,
                codigo     TEXT NOT NULL,
                desc       TEXT NOT NULL DEFAULT '',
                stock      REAL NOT NULL DEFAULT 0,
                ubicacion  TEXT NOT NULL DEFAULT '',
                categoria  TEXT NOT NULL DEFAULT 'GENERAL',
                alias      TEXT DEFAULT NULL
            );
            """
        )
        # Migration for existing DBs without alias column
        try:
            cur = conn.execute("SELECT alias FROM articulos LIMIT 1")
            cur.fetchone()
        except Exception as e:
            if "no such column" in str(e).lower():
                try:
                    conn.execute("ALTER TABLE articulos ADD COLUMN alias TEXT DEFAULT NULL")
                except Exception:
                    pass
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_salidas_art_codigo ON articulos (codigo);"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_salidas_art_alias ON articulos (alias);"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS articulos_meta (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )


def _meta_get(key: str) -> Optional[str]:
    with _conectar() as conn:
        row = conn.execute(
            "SELECT value FROM articulos_meta WHERE key = ?;", (key,)
        ).fetchone()
    return str(row["value"]) if row else None


def _meta_set(key: str, value: str) -> None:
    with _conectar() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO articulos_meta (key, value) VALUES (?, ?);",
            (key, value),
        )


def obtener_ultima_sync() -> Optional[datetime]:
    raw = _meta_get(META_ULTIMA_SYNC)
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def obtener_ultima_pull() -> Optional[datetime]:
    raw = _meta_get(META_ULTIMA_PULL)
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def tiene_datos() -> bool:
    with _conectar() as conn:
        row = conn.execute("SELECT 1 FROM articulos LIMIT 1;").fetchone()
    return row is not None


def marcar_sync(cuando: datetime) -> None:
    _meta_set(META_ULTIMA_SYNC, cuando.isoformat())


def marcar_pull(cuando: datetime) -> None:
    _meta_set(META_ULTIMA_PULL, cuando.isoformat())
    marcar_sync(cuando)


def cargar_todos() -> list[dict[str, Any]]:
    with _conectar() as conn:
        # Try with alias, fallback without for old DBs mid-migration
        try:
            filas = conn.execute(
                "SELECT doc_id, codigo, desc, stock, ubicacion, categoria, alias FROM articulos;"
            ).fetchall()
            has_alias = True
        except Exception as e:
            if "no such column" in str(e).lower():
                filas = conn.execute(
                    "SELECT doc_id, codigo, desc, stock, ubicacion, categoria FROM articulos;"
                ).fetchall()
                has_alias = False
            else:
                raise
    out = []
    for f in filas:
        try:
            alias_v = f["alias"] if has_alias and "alias" in f.keys() else None
        except Exception:
            alias_v = None
        out.append(
            {
                "doc_id": f["doc_id"],
                "codigo": f["codigo"],
                "desc": f["desc"],
                "stock": float(f["stock"] or 0),
                "ubicacion": f["ubicacion"],
                "categoria": f["categoria"],
                "alias": str(alias_v).strip() if alias_v is not None and str(alias_v).strip() != "" else None,
            }
        )
    return out


def reemplazar_todo(items: list[dict[str, Any]], cuando: datetime) -> None:
    with _conectar() as conn:
        # Ensure alias column exists
        try:
            conn.execute("SELECT alias FROM articulos LIMIT 1")
        except Exception as e:
            if "no such column" in str(e).lower():
                try:
                    conn.execute("ALTER TABLE articulos ADD COLUMN alias TEXT DEFAULT NULL")
                except Exception:
                    pass
        conn.execute("DELETE FROM articulos;")
        conn.executemany(
            """
            INSERT INTO articulos (doc_id, codigo, desc, stock, ubicacion, categoria, alias)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            [
                (
                    str(i.get("doc_id") or i["codigo"]),
                    str(i["codigo"]),
                    str(i.get("desc") or ""),
                    float(i.get("stock") or 0),
                    str(i.get("ubicacion") or ""),
                    str(i.get("categoria") or "GENERAL"),
                    str(i.get("alias") or "").strip() if i.get("alias") is not None and str(i.get("alias")).strip() != "" else None,
                )
                for i in items
            ],
        )
        conn.execute(
            "INSERT OR REPLACE INTO articulos_meta (key, value) VALUES (?, ?);",
            (META_ULTIMA_SYNC, cuando.isoformat()),
        )
        conn.execute(
            "INSERT OR REPLACE INTO articulos_meta (key, value) VALUES (?, ?);",
            (META_ULTIMA_PULL, cuando.isoformat()),
        )


def upsert_item(
    doc_id: str,
    codigo: str,
    desc: str,
    stock: float,
    ubicacion: str,
    categoria: str = "GENERAL",
    alias: str | None = None,
) -> None:
    with _conectar() as conn:
        # Ensure alias column exists idempotently
        try:
            conn.execute("SELECT alias FROM articulos LIMIT 1")
        except Exception as e:
            if "no such column" in str(e).lower():
                try:
                    conn.execute("ALTER TABLE articulos ADD COLUMN alias TEXT DEFAULT NULL")
                except Exception:
                    pass
        if alias is None:
            # Preserve existing alias: do not overwrite alias column on conflict
            conn.execute(
                """
                INSERT INTO articulos (doc_id, codigo, desc, stock, ubicacion, categoria)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(doc_id) DO UPDATE SET
                    codigo = excluded.codigo,
                    desc = excluded.desc,
                    stock = excluded.stock,
                    ubicacion = excluded.ubicacion,
                    categoria = excluded.categoria;
                """,
                (doc_id, codigo, desc, float(stock), ubicacion, categoria),
            )
            # Ensure new rows get alias NULL (already default) - no action needed
        else:
            conn.execute(
                """
                INSERT INTO articulos (doc_id, codigo, desc, stock, ubicacion, categoria, alias)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(doc_id) DO UPDATE SET
                    codigo = excluded.codigo,
                    desc = excluded.desc,
                    stock = excluded.stock,
                    ubicacion = excluded.ubicacion,
                    categoria = excluded.categoria,
                    alias = excluded.alias;
                """,
                (doc_id, codigo, desc, float(stock), ubicacion, categoria, alias),
            )
