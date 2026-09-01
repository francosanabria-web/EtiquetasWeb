# -*- coding: utf-8 -*-
"""Persistencia de filas importadas desde Excel."""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from excel_parser import FilaPedido, parse_fecha_orden, resumen_importacion, normalizar_estado
from repo import DB_PATH, _conectar, _ahora_iso


def _init_tablas_import(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS importaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sesion_id INTEGER NOT NULL,
            nombre_archivo TEXT NOT NULL,
            hoja TEXT NOT NULL,
            importado_en TEXT NOT NULL,
            resumen_json TEXT NOT NULL,
            source_bytes BLOB
        );"""
    )
    # Migración: agregar source_bytes si la tabla ya existía sin esa columna
    try:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(importaciones)").fetchall()]
        if "source_bytes" not in cols:
            conn.execute("ALTER TABLE importaciones ADD COLUMN source_bytes BLOB")
    except Exception:
        pass
    conn.executescript(
        """

        CREATE TABLE IF NOT EXISTS filas_pedido (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sesion_id INTEGER NOT NULL,
            importacion_id INTEGER NOT NULL,
            fila_excel INTEGER NOT NULL,
            ref_pedido TEXT NOT NULL,
            datos_json TEXT NOT NULL,
            seleccionada INTEGER NOT NULL DEFAULT 0,
            cumplida INTEGER NOT NULL DEFAULT 0,
            elegible INTEGER NOT NULL DEFAULT 0,
            UNIQUE (sesion_id, importacion_id, fila_excel)
        );

        CREATE TABLE IF NOT EXISTS notas_fila (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sesion_id INTEGER NOT NULL,
            fila_id INTEGER NOT NULL,
            texto TEXT NOT NULL,
            autor TEXT,
            creado_en TEXT NOT NULL,
            FOREIGN KEY (fila_id) REFERENCES filas_pedido(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS consultas_pendientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sesion_id INTEGER NOT NULL,
            fila_id INTEGER NOT NULL,
            texto_existente TEXT NOT NULL,
            texto_nuevo TEXT NOT NULL,
            autor TEXT,
            creado_en TEXT NOT NULL,
            estado TEXT NOT NULL DEFAULT 'pendiente',
            FOREIGN KEY (fila_id) REFERENCES filas_pedido(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_consultas_sesion ON consultas_pendientes(sesion_id);
        CREATE INDEX IF NOT EXISTS idx_consultas_fila ON consultas_pendientes(fila_id);
        """
    )


def init_import_db() -> None:
    with _conectar() as conn:
        _init_tablas_import(conn)


def _fila_desde_row(row: sqlite3.Row) -> dict[str, Any]:
    datos = json.loads(row["datos_json"])
    return {
        "id": row["id"],
        "sesion_id": row["sesion_id"],
        "importacion_id": row["importacion_id"],
        "fila_excel": row["fila_excel"],
        "ref_pedido": row["ref_pedido"],
        "seleccionada": bool(row["seleccionada"]),
        "cumplida": bool(row["cumplida"]),
        "elegible": bool(row["elegible"]),
        **datos,
    }


def guardar_importacion(
    sesion_id: int,
    nombre_archivo: str,
    hoja: str,
    filas: list[FilaPedido],
    merge: bool = False,
    source_bytes: bytes | None = None,
) -> dict[str, Any]:
    with _conectar() as conn:
        _init_tablas_import(conn)
        ses = conn.execute("SELECT estado FROM sesiones WHERE id = ?", (sesion_id,)).fetchone()
        if not ses:
            raise LookupError("Sesión no encontrada.")
        if merge:
            if ses["estado"] not in ("abierta", "cerrada"):
                raise ValueError("Solo se importa en sesión abierta o cerrada.")
        else:
            if ses["estado"] != "abierta":
                raise ValueError("Solo se importa en sesión abierta.")

        ahora = _ahora_iso()

        if merge:
            return _guardar_importacion_merge(
                conn, sesion_id, nombre_archivo, hoja, ahora, filas, source_bytes
            )

        resumen = resumen_importacion(filas)
        cur = conn.execute(
            """
            INSERT INTO importaciones
                (sesion_id, nombre_archivo, hoja, importado_en, resumen_json, source_bytes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (sesion_id, nombre_archivo, hoja, ahora, json.dumps(resumen), source_bytes),
        )
        imp_id = cur.lastrowid
        assert imp_id is not None

        conn.execute("DELETE FROM filas_pedido WHERE sesion_id = ?", (sesion_id,))

        for f in filas:
            payload = asdict(f)
            conn.execute(
                """
                INSERT INTO filas_pedido (
                    sesion_id, importacion_id, fila_excel, ref_pedido, datos_json,
                    seleccionada, cumplida, elegible
                ) VALUES (?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (
                    sesion_id,
                    imp_id,
                    f.fila_excel,
                    f.ref_pedido,
                    json.dumps(payload, ensure_ascii=False),
                    1 if f.cumplida else 0,
                    1 if f.elegible_reunion else 0,
                ),
            )
        conn.commit()
        return {
            "importacion_id": imp_id,
            "hoja": hoja,
            "nombre_archivo": nombre_archivo,
            "importado_en": ahora,
            "resumen": resumen,
        }


def _guardar_importacion_merge(
    conn: sqlite3.Connection,
    sesion_id: int,
    nombre_archivo: str,
    hoja: str,
    ahora: str,
    filas: list[FilaPedido],
    source_bytes: bytes | None = None,
) -> dict[str, Any]:
    resumen = {
        "procesadas": 0,
        "omitidas_duplicadas": 0,
        "pendientes_consulta": 0,
        "no_reconocidas": 0,
        "total_importadas": len(filas),
    }

    # Cargar filas_pedido existentes y notas_fila
    filas_existentes = conn.execute(
        "SELECT id, ref_pedido, fila_excel FROM filas_pedido WHERE sesion_id = ?",
        (sesion_id,),
    ).fetchall()
    lookup: dict[tuple[str, int], int] = {
        (r["ref_pedido"], r["fila_excel"]): r["id"] for r in filas_existentes
    }

    # Insertar registro de importación (con source_bytes)
    cur = conn.execute(
        """
        INSERT INTO importaciones (sesion_id, nombre_archivo, hoja, importado_en, resumen_json, source_bytes)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (sesion_id, nombre_archivo, hoja, ahora, json.dumps(resumen), source_bytes),
    )
    imp_id = cur.lastrowid
    assert imp_id is not None

    for f in filas:
        key = (f.ref_pedido, f.fila_excel)
        fila_id = lookup.get(key)

        if fila_id is None:
            resumen["no_reconocidas"] += 1
            continue

        novedad_norm = normalizar_estado(f.novedades)
        if not novedad_norm:
            resumen["omitidas_duplicadas"] += 1
            continue

        notas_existentes = conn.execute(
            "SELECT texto FROM notas_fila WHERE fila_id = ?", (fila_id,)
        ).fetchall()

        if notas_existentes and any(
            normalizar_estado(n["texto"]) == novedad_norm for n in notas_existentes
        ):
            resumen["omitidas_duplicadas"] += 1
            continue

        if notas_existentes:
            conn.execute(
                """
                INSERT INTO consultas_pendientes
                    (sesion_id, fila_id, texto_existente, texto_nuevo, autor, creado_en, estado)
                VALUES (?, ?, ?, ?, ?, ?, 'pendiente')
                """,
                (
                    sesion_id,
                    fila_id,
                    notas_existentes[0]["texto"],
                    f.novedades.strip(),
                    None,
                    ahora,
                ),
            )
            resumen["pendientes_consulta"] += 1
        else:
            conn.execute(
                """
                INSERT INTO notas_fila (sesion_id, fila_id, texto, autor, creado_en)
                VALUES (?, ?, ?, ?, ?)
                """,
                (sesion_id, fila_id, f.novedades.strip(), None, ahora),
            )
            resumen["procesadas"] += 1

    conn.commit()
    return resumen


def listar_filas(
    sesion_id: int,
    solo_elegibles: bool = False,
    solo_seleccionadas: bool = False,
    order_by_fila_excel: bool = False,
) -> list[dict[str, Any]]:
    with _conectar() as conn:
        _init_tablas_import(conn)
        q = "SELECT * FROM filas_pedido WHERE sesion_id = ?"
        params: list[Any] = [sesion_id]
        if solo_elegibles:
            q += " AND elegible = 1"
        if solo_seleccionadas:
            q += " AND seleccionada = 1"
        if order_by_fila_excel:
            q += " ORDER BY fila_excel ASC"
        else:
            q += " ORDER BY ref_pedido, fila_excel"
        rows = conn.execute(q, params).fetchall()
        notas_rows = conn.execute(
            "SELECT * FROM notas_fila WHERE sesion_id = ? ORDER BY creado_en, id",
            (sesion_id,),
        ).fetchall()
        notas_por_fila: dict[int, list[dict[str, Any]]] = {}
        for n in notas_rows:
            notas_por_fila.setdefault(n["fila_id"], []).append(dict(n))
        out = []
        for r in rows:
            fila = _fila_desde_row(r)
            fila["notas"] = notas_por_fila.get(r["id"], [])
            out.append(fila)
        return out


def listar_filas_por_fila_excel_asc(sesion_id: int) -> list[dict[str, Any]]:
    return listar_filas(sesion_id, order_by_fila_excel=True)


def _fecha_grupo(items: list[dict[str, Any]]) -> str:
    """Primera fecha no vacía del grupo (la fila elegible puede no ser la cabecera)."""
    for i in items:
        f = str(i.get("fecha_solicitud") or "").strip()
        if f:
            return f
    return ""


def _fechas_por_ref_sesion(sesion_id: int) -> dict[str, str]:
    """Fecha col. E puede estar en filas no elegibles del mismo pedido."""
    with _conectar() as conn:
        _init_tablas_import(conn)
        rows = conn.execute(
            "SELECT ref_pedido, datos_json FROM filas_pedido WHERE sesion_id = ?",
            (sesion_id,),
        ).fetchall()
    fechas: dict[str, str] = {}
    for r in rows:
        ref = r["ref_pedido"]
        if ref in fechas:
            continue
        datos = json.loads(r["datos_json"])
        f = str(datos.get("fecha_solicitud") or "").strip()
        if f:
            fechas[ref] = f
    return fechas


def listar_pedidos_agrupados(sesion_id: int, solo_elegibles: bool = True) -> list[dict[str, Any]]:
    fechas_ref = _fechas_por_ref_sesion(sesion_id)
    filas = listar_filas(sesion_id, solo_elegibles=solo_elegibles)
    by_ref: dict[str, list[dict[str, Any]]] = {}
    for f in filas:
        by_ref.setdefault(f["ref_pedido"], []).append(f)
    out: list[dict[str, Any]] = []
    for ref, items in by_ref.items():
        cab = min(items, key=lambda x: x.get("fila_excel", 0))
        fecha = fechas_ref.get(ref) or _fecha_grupo(items)
        for i in items:
            if not str(i.get("fecha_solicitud") or "").strip():
                i["fecha_solicitud"] = fecha
        out.append(
            {
                "ref_pedido": ref,
                "fecha_solicitud": fecha,
                "solicitante": cab.get("solicitante", "") or _primer_campo(items, "solicitante"),
                "tipo_solicitud": cab.get("tipo_solicitud", "") or _primer_campo(items, "tipo_solicitud"),
                "maquina_linea": cab.get("maquina_linea", "") or _primer_campo(items, "maquina_linea"),
                "estado_solicitud": cab.get("estado_solicitud", "") or _primer_campo(items, "estado_solicitud"),
                "num_odoo": cab.get("num_odoo", ""),
                "num_solicitud": cab.get("num_solicitud", ""),
                "almacenista": cab.get("almacenista", "") or _primer_campo(items, "almacenista"),
                "filas": items,
                "seleccionada": any(i["seleccionada"] for i in items),
                "cantidad_filas": len(items),
            }
        )
    out.sort(key=lambda p: parse_fecha_orden(str(p.get("fecha_solicitud", ""))))
    return out


def _primer_campo(items: list[dict[str, Any]], campo: str) -> str:
    for i in items:
        v = str(i.get(campo) or "").strip()
        if v:
            return v
    return ""


def fijar_seleccion_reunion(sesion_id: int, refs: list[str]) -> int:
    """Marca solo refs como seleccionadas; el resto de elegibles queda apartado."""
    with _conectar() as conn:
        _init_tablas_import(conn)
        conn.execute(
            "UPDATE filas_pedido SET seleccionada = 0 WHERE sesion_id = ? AND elegible = 1",
            (sesion_id,),
        )
        n = 0
        for ref in refs:
            cur = conn.execute(
                """
                UPDATE filas_pedido SET seleccionada = 1
                WHERE sesion_id = ? AND ref_pedido = ? AND elegible = 1
                """,
                (sesion_id, ref),
            )
            n += cur.rowcount
        conn.commit()
        return n


def actualizar_seleccion(sesion_id: int, refs: list[str], seleccionada: bool) -> int:
    if not refs:
        return 0
    with _conectar() as conn:
        _init_tablas_import(conn)
        val = 1 if seleccionada else 0
        n = 0
        for ref in refs:
            cur = conn.execute(
                """
                UPDATE filas_pedido SET seleccionada = ?
                WHERE sesion_id = ? AND ref_pedido = ? AND elegible = 1
                """,
                (val, sesion_id, ref),
            )
            n += cur.rowcount
        conn.commit()
        return n


def agregar_nota_fila(
    sesion_id: int, fila_id: int, texto: str, autor: Optional[str] = None
) -> dict[str, Any]:
    with _conectar() as conn:
        _init_tablas_import(conn)
        fila = conn.execute(
            "SELECT id FROM filas_pedido WHERE id = ? AND sesion_id = ?",
            (fila_id, sesion_id),
        ).fetchone()
        if not fila:
            raise LookupError("Fila no encontrada.")
        ahora = _ahora_iso()
        cur = conn.execute(
            """
            INSERT INTO notas_fila (sesion_id, fila_id, texto, autor, creado_en)
            VALUES (?, ?, ?, ?, ?)
            """,
            (sesion_id, fila_id, texto.strip(), autor, ahora),
        )
        conn.commit()
        return {
            "id": cur.lastrowid,
            "sesion_id": sesion_id,
            "fila_id": fila_id,
            "texto": texto.strip(),
            "autor": autor,
            "creado_en": ahora,
        }


def notas_por_sesion(sesion_id: int) -> list[dict[str, Any]]:
    with _conectar() as conn:
        _init_tablas_import(conn)
        rows = conn.execute(
            "SELECT * FROM notas_fila WHERE sesion_id = ? ORDER BY creado_en, id",
            (sesion_id,),
        ).fetchall()
        return [dict(r) for r in rows]


@dataclass
class ConsultaPendiente:
    id: int
    sesion_id: int
    fila_id: int
    texto_existente: str
    texto_nuevo: str
    autor: Optional[str]
    creado_en: str
    estado: str


def listar_consultas_pendientes(sesion_id: int) -> list[dict[str, Any]]:
    with _conectar() as conn:
        rows = conn.execute(
            "SELECT * FROM consultas_pendientes WHERE sesion_id = ? ORDER BY creado_en, id",
            (sesion_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def obtener_source_bytes(sesion_id: int) -> bytes | None:
    """Retorna source_bytes de la última importación de una sesión."""
    with _conectar() as conn:
        row = conn.execute(
            "SELECT source_bytes FROM importaciones WHERE sesion_id = ? ORDER BY id DESC LIMIT 1",
            (sesion_id,),
        ).fetchone()
        if row and row["source_bytes"]:
            return row["source_bytes"]
        return None


def obtener_filas_importadas(sesion_id: int) -> list[dict[str, Any]]:
    """Retorna las filas importadas de una sesión, ordenadas por fila_excel ASC."""
    return listar_filas(sesion_id, order_by_fila_excel=True)
