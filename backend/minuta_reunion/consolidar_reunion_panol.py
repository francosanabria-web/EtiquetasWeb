# -*- coding: utf-8 -*-
"""One-shot: consolidar pedidos del Historico en reunion compartida panol y archivar el resto."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import db  # noqa: E402


OWNER = "panol@panol.local"
SECTOR = "MANTENIMIENTO"
TITULO = "Reunion vigente — Mantenimiento"


def main() -> None:
    db.init_db()
    with db._conectar() as conn:
        reuniones = [dict(r) for r in conn.execute("SELECT * FROM reuniones ORDER BY id").fetchall()]
        print("Reuniones antes:", len(reuniones))
        for r in reuniones:
            n = conn.execute(
                "SELECT COUNT(*) c FROM pedidos WHERE reunion_id = ?", (r["id"],)
            ).fetchone()["c"]
            print(
                f"  id={r['id']} titulo={r['titulo']!r} arch={r.get('archivada')} pedidos={n}"
            )

        dest = conn.execute(
            """
            SELECT * FROM reuniones
            WHERE lower(owner_email) = ? AND sector = ? AND COALESCE(archivada,0) = 0
              AND titulo = ?
            ORDER BY id DESC LIMIT 1
            """,
            (OWNER, SECTOR, TITULO),
        ).fetchone()

    if dest:
        dest_id = int(dest["id"])
        print("Reutilizando destino id=", dest_id)
        db.actualizar_reunion(
            dest_id,
            {
                "visibilidad": "compartida",
                "owner_email": OWNER,
                "archivada": 0,
                "fecha": date.today().isoformat(),
            },
        )
    else:
        creada = db.crear_reunion(
            {
                "sector": SECTOR,
                "fecha": date.today().isoformat(),
                "titulo": TITULO,
                "tipo": "semanal",
                "visibilidad": "compartida",
                "owner_email": OWNER,
                "sectores_comprometidos": "Mantenimiento",
            }
        )
        dest_id = int(creada["id"])
        print("Creada destino id=", dest_id)

    with db._conectar() as conn:
        origenes = [
            int(r["id"])
            for r in conn.execute("SELECT id FROM reuniones WHERE id <> ?", (dest_id,)).fetchall()
        ]

    total_movidos = 0
    for oid in origenes:
        with db._conectar() as conn:
            n = conn.execute(
                "SELECT COUNT(*) c FROM pedidos WHERE reunion_id = ?", (oid,)
            ).fetchone()["c"]
        if n:
            movidos = db.mover_pedidos_reunion(oid, dest_id)
            total_movidos += movidos
            print(f"  movidos {movidos} desde reunion {oid}")

    # Archivar todas excepto destino (incluye Historicos y vacias)
    with db._conectar() as conn:
        conn.execute(
            """
            UPDATE reuniones
            SET archivada = 1, actualizado_en = ?
            WHERE id <> ?
            """,
            (db._ahora_iso(), dest_id),
        )
        conn.commit()
        db._exportar_sector(conn, SECTOR)

    with db._conectar() as conn:
        n_dest = conn.execute(
            "SELECT COUNT(*) c FROM pedidos WHERE reunion_id = ?", (dest_id,)
        ).fetchone()["c"]
        n_nov = conn.execute("SELECT COUNT(*) c FROM novedades").fetchone()["c"]
        activas = conn.execute(
            "SELECT id, titulo FROM reuniones WHERE COALESCE(archivada,0)=0"
        ).fetchall()
        print("Pedidos en destino:", n_dest)
        print("Novedades totales:", n_nov)
        print("Reuniones activas:", [dict(r) for r in activas])
        print("TOTAL_MOVIDOS", total_movidos)
        print("DEST_ID", dest_id)


if __name__ == "__main__":
    main()
