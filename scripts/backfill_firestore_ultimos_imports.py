# -*- coding: utf-8 -*-
"""Backfill Firestore desde los últimos N imports SIN reimportar los Excel.

Uso:
    cd backend/salidas
    .\\.venv\\Scripts\\python.exe ..\\..\\scripts\\backfill_firestore_ultimos_imports.py [--last 2]

Lee maestro_stock_audit para los últimos N import_log_id, toma las filas
finales de maestro_stock y las pushea con firebase_sync.sync_stock_bulk_to_firestore
(merge por doc, cap 500 por llamada, best-effort). Idempotente: re-pushear los
mismos valores no rompe nada, solo consume escrituras.

Reglas: solo códigos efectivamente cambiados (NEW + MOD del audit), con los
mismos valores finales de la DB (ya filtrados por detallado/valorizado,
vacío-no-borra y precio-0-no-pisa en el import original).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SALIDAS_DIR = Path(__file__).resolve().parent.parent / "backend" / "salidas"
if str(_SALIDAS_DIR) not in sys.path:
    sys.path.insert(0, str(_SALIDAS_DIR))

from db import get_connection  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Backfill Firestore desde últimos imports (sin reimportar Excel)")
    ap.add_argument("--last", type=int, default=2, help="Cantidad de últimos imports a cubrir (default 2)")
    args = ap.parse_args()
    last = max(1, min(10, int(args.last or 2)))

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, archivo_origen FROM maestro_stock_import_log ORDER BY id DESC LIMIT %s", (last,))
            logs = cur.fetchall() or []
            if not logs:
                print("Sin imports registrados.")
                return 1
            log_ids = [int(r["id"]) for r in logs]
            print(f"Logs: {[(r['id'], r['archivo_origen']) for r in logs]}")
            fmt = ",".join(["%s"] * len(log_ids))
            cur.execute(f"SELECT DISTINCT codigo FROM maestro_stock_audit WHERE import_log_id IN ({fmt})", tuple(log_ids))
            codigos = sorted(str(r["codigo"]).strip().upper() for r in cur.fetchall() if r.get("codigo"))
            print(f"Códigos distintos: {len(codigos)}")
            items: list[dict] = []
            for cod in codigos:
                try:
                    cur.execute("SELECT codigo, descripcion, stock, ubicacion, categoria, alias FROM maestro_stock WHERE codigo=%s LIMIT 1", (cod,))
                    fr = cur.fetchone()
                except Exception:
                    cur.execute("SELECT codigo, descripcion, stock, ubicacion, categoria FROM maestro_stock WHERE codigo=%s LIMIT 1", (cod,))
                    fr = cur.fetchone()
                    if fr is not None:
                        fr["alias"] = None
                if not fr:
                    continue
                items.append(
                    {
                        "codigo": str(fr.get("codigo") or cod).strip().upper(),
                        "desc": str(fr.get("descripcion") or ""),
                        "stock": float(fr.get("stock") or 0),
                        "ubicacion": str(fr.get("ubicacion") or ""),
                        "categoria": str(fr.get("categoria") or "GENERAL") or "GENERAL",
                        "alias": fr.get("alias"),
                    }
                )
            print(f"Items a pushear: {len(items)}")
    finally:
        try:
            conn.close()
        except Exception:
            pass

    if not items:
        print("Nada para pushear.")
        return 0

    import firebase_sync as fb

    total_pushed = 0
    total_errors = 0
    for i in range(0, len(items), 500):
        chunk = items[i : i + 500]
        res = fb.sync_stock_bulk_to_firestore(chunk)
        print(f"chunk {i // 500 + 1}: {res}")
        total_pushed += int(res.get("pushed") or 0)
        total_errors += int(res.get("errors") or 0)
        if res.get("error"):
            print(f"  error: {res.get('error')}")
    print(f"TOTAL pushed={total_pushed} errors={total_errors}")
    return 0 if total_errors == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
