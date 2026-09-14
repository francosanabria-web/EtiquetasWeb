# -*- coding: utf-8 -*-
"""Inspeccion + recuperacion reunion panol."""
from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

import db

ROOT = Path(__file__).resolve().parent
DB = ROOT / "data" / "minutas.db"
BACKUP = ROOT / "data" / "backup_pre_sync_20260730_090633" / "minutas.db"
JSON_M = ROOT / "data" / "sectores" / "MANTENIMIENTO.json"


def inspect() -> None:
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    print("=== ALL reuniones ===")
    for r in c.execute(
        "SELECT id,titulo,sector,owner_email,archivada,visibilidad,fecha FROM reuniones ORDER BY id"
    ):
        print(dict(r))
    print("=== pedidos por reunion/sector ===")
    for r in c.execute(
        "SELECT reunion_id, sector, COUNT(1) n FROM pedidos GROUP BY reunion_id, sector"
    ):
        print(dict(r))
    print("=== novedades por fecha ===")
    for r in c.execute(
        "SELECT fecha_reunion, COUNT(1) n FROM novedades GROUP BY fecha_reunion ORDER BY fecha_reunion"
    ):
        print(dict(r))
    if JSON_M.exists():
        d = json.loads(JSON_M.read_text(encoding="utf-8"))
        print("JSON exportado_en", d.get("exportado_en"))
        print("JSON pedidos", len(d.get("pedidos", [])))
        print(
            "JSON reuniones ids",
            [(r.get("id"), r.get("titulo"), r.get("archivada")) for r in d.get("reuniones", [])],
        )


def recover() -> int:
    """Recrea reunion vigente panol y mueve todos los pedidos actuales ahi."""
    db.init_db()
    # Prefer pedidos actuales (tienen novedades de ayer). Estan en reunion 27.
    with db._conectar() as conn:
        n = conn.execute("SELECT COUNT(1) c FROM pedidos").fetchone()["c"]
        print("pedidos totales ahora:", n)
        dest = conn.execute(
            """
            SELECT id FROM reuniones
            WHERE lower(owner_email)='panol@panol.local'
              AND sector='MANTENIMIENTO'
              AND COALESCE(archivada,0)=0
              AND titulo LIKE 'Reunion vigente%'
            ORDER BY id DESC LIMIT 1
            """
        ).fetchone()

    if dest:
        dest_id = int(dest["id"])
        print("ya existe destino", dest_id)
    else:
        creada = db.crear_reunion(
            {
                "sector": "MANTENIMIENTO",
                "fecha": date.today().isoformat(),
                "titulo": "Reunion vigente — Mantenimiento",
                "tipo": "semanal",
                "visibilidad": "compartida",
                "owner_email": "panol@panol.local",
                "sectores_comprometidos": "Mantenimiento",
            }
        )
        dest_id = int(creada["id"])
        print("creada destino", dest_id)

    with db._conectar() as conn:
        origenes = [
            int(r["reunion_id"])
            for r in conn.execute(
                "SELECT DISTINCT reunion_id FROM pedidos WHERE reunion_id <> ?",
                (dest_id,),
            ).fetchall()
        ]
    total = 0
    for oid in origenes:
        total += db.mover_pedidos_reunion(oid, dest_id)
        print("movidos desde", oid)

    # Asegurar sector MANTENIMIENTO en pedidos
    with db._conectar() as conn:
        conn.execute(
            "UPDATE pedidos SET sector = 'MANTENIMIENTO', actualizado_en = ? WHERE reunion_id = ?",
            (db._ahora_iso(), dest_id),
        )
        conn.execute(
            """
            UPDATE reuniones SET archivada=0, visibilidad='compartida',
              owner_email='panol@panol.local', sector='MANTENIMIENTO',
              actualizado_en=?
            WHERE id=?
            """,
            (db._ahora_iso(), dest_id),
        )
        conn.commit()
        db._exportar_sector(conn, "MANTENIMIENTO")
        n_dest = conn.execute(
            "SELECT COUNT(1) c FROM pedidos WHERE reunion_id=?", (dest_id,)
        ).fetchone()["c"]
        n_nov = conn.execute(
            """
            SELECT COUNT(1) c FROM novedades n
            JOIN pedidos p ON p.id=n.pedido_id WHERE p.reunion_id=?
            """,
            (dest_id,),
        ).fetchone()["c"]
    print("DEST", dest_id, "pedidos", n_dest, "novedades ligadas", n_nov)
    return dest_id


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "recover":
        recover()
    else:
        inspect()
