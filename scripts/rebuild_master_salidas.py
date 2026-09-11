# -*- coding: utf-8 -*-
"""Reconstruir master_salidas.xlsx desde diarios (recuperación de archivo vacío)."""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd

BASE = Path(r"G:\Unidades compartidas\Mantenimiento\MANTENIMIENTO  OZLA 2024-2025\17. Pañol\pañol v5.0")
MASTER = BASE / "master_salidas.xlsx"
DIARIA = BASE / "salidas_diaria"
HOJA = "Movimientos"

COLS = [
    "FECHA",
    "MES",
    "AÑO",
    "CODIGO",
    "DESCRIPCION",
    "UBICACION",
    "CANTIDAD",
    "TIPO_COMPROBANTE",
    "NUMERO_ORDEN",
    "MAQUINA_SITIO",
    "PRECIO_UNITARIO",
    "MONTO_TOTAL_SALIDA",
    "OPERARIO",
    "SECTOR",
]


def _candidatos() -> list[Path]:
    seen: set[str] = set()
    out: list[Path] = []
    for folder in (DIARIA, BASE):
        if not folder.is_dir():
            continue
        for p in sorted(folder.glob("salidas_*.xlsx")):
            key = p.name.lower()
            if key in seen:
                # Preferir el más grande / más reciente si hay duplicado root vs diaria
                prev = next(x for x in out if x.name.lower() == key)
                if p.stat().st_size > prev.stat().st_size or (
                    p.stat().st_size == prev.stat().st_size
                    and p.stat().st_mtime > prev.stat().st_mtime
                ):
                    out.remove(prev)
                    out.append(p)
                    seen.add(key)
                continue
            seen.add(key)
            out.append(p)
    return out


def main() -> None:
    files = _candidatos()
    print(f"Archivos diarios a fusionar: {len(files)}")
    frames: list[pd.DataFrame] = []
    errores = 0
    for p in files:
        try:
            if p.stat().st_size < 100:
                print(f"  SKIP vacío/pequeño: {p.name}")
                continue
            df = pd.read_excel(p, engine="openpyxl")
            if df.empty:
                continue
            df["_src"] = p.name
            frames.append(df)
            print(f"  OK {p.name}: {len(df)} filas")
        except Exception as e:
            errores += 1
            print(f"  FAIL {p.name}: {type(e).__name__}: {e}")

    if not frames:
        raise SystemExit("No hay datos para reconstruir")

    full = pd.concat(frames, ignore_index=True)
    # Deduplicar: preferir filas sin _src conflict — usar todas las columnas clave de movimiento
    key_cols = [c for c in COLS if c in full.columns]
    before = len(full)
    full = full.drop_duplicates(subset=key_cols, keep="last")
    print(f"Filas totales: {before} -> tras dedupe: {len(full)} (errores lectura: {errores})")

    # Orden columnas
    cols = [c for c in COLS if c in full.columns] + [
        c for c in full.columns if c not in COLS and c != "_src"
    ]
    full = full[cols]

    # Backup del vacío / actual
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if MASTER.exists():
        bak = MASTER.with_name(f"master_salidas.xlsx.CORRUPTO_{stamp}")
        shutil.copy2(MASTER, bak)
        print(f"Backup corrupto -> {bak.name} ({bak.stat().st_size} bytes)")

    tmp = MASTER.with_suffix(".xlsx.tmp")
    with pd.ExcelWriter(tmp, engine="openpyxl") as w:
        full.to_excel(w, index=False, sheet_name=HOJA)
    shutil.move(str(tmp), str(MASTER))
    print(f"Escrito {MASTER} size={MASTER.stat().st_size} filas={len(full)}")


if __name__ == "__main__":
    main()
