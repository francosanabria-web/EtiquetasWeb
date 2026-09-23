# -*- coding: utf-8 -*-
"""Seed idempotent for maestro_stock (migrates Excel ARTICULOS to MariaDB).

Purpose: Reads LABORATORIO BASE/base_datos.xlsx (preferred) or master_codes.xlsx
         fallback, sheet ARTICULOS (~6988 rows), and UPSERTs into maestro_stock.
Business rules: empty never overwrites; price 0 never overwrites price >0.

Usage:
    python scripts/seed_maestro_stock.py [--excel PATH] [--dry-run]
    python scripts/seed_maestro_stock.py --excel "LABORATORIO BASE/base_datos.xlsx"
    python scripts/seed_maestro_stock.py --dry-run   # no DB writes, just report

Notes:
    - Handles 6988 rows without OOM (batch 500).
    - Normalizes headers lower without accents/spaces; finds codigo via
      variants codigo/cod/sku; cleans codigo UPPER without trailing .0;
      detects columns via scoring similar to almacen_gui _col_stock_actual_maestro.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd

# Allow import of backend/salidas/config for DSN
_SCRIPT_DIR = Path(__file__).resolve().parent
_SALIDAS_DIR = _SCRIPT_DIR.parent / "backend" / "salidas"
if str(_SALIDAS_DIR) not in sys.path:
    sys.path.insert(0, str(_SALIDAS_DIR))

try:
    import config as salidas_config  # type: ignore

    DB_HOST = getattr(salidas_config, "DB_HOST", "127.0.0.1")
    DB_PORT = int(getattr(salidas_config, "DB_PORT", 3306))
    DB_USER = getattr(salidas_config, "DB_USER", "root")
    DB_PASSWORD = getattr(salidas_config, "DB_PASSWORD", "")
    DB_NAME = getattr(salidas_config, "DB_NAME", "panol")
except Exception:
    import os

    DB_HOST = os.environ.get("SALIDAS_DB_HOST", os.environ.get("DB_HOST", "127.0.0.1"))
    DB_PORT = int(os.environ.get("SALIDAS_DB_PORT", os.environ.get("DB_PORT", "3306")))
    DB_USER = os.environ.get("SALIDAS_DB_USER", os.environ.get("DB_USER", "root"))
    DB_PASSWORD = os.environ.get("SALIDAS_DB_PASSWORD", os.environ.get("DB_PASSWORD", ""))
    DB_NAME = os.environ.get("SALIDAS_DB_NAME", os.environ.get("DB_NAME", "panol"))

import pymysql  # noqa: E402
from pymysql.cursors import DictCursor  # noqa: E402

BATCH_SIZE = 500
HOJA_ARTICULOS = "ARTICULOS"


def _norm_header(name: Any) -> str:
    """Lower without accents/spaces, like almacen_gui _norm_header_imp."""
    s = str(name or "").strip().lower()
    # Remove accents via unicodedata
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return s.strip()


def _norm_nospace(name: Any) -> str:
    return _norm_header(name).replace(" ", "").replace("_", "").replace("-", "").replace(".", "")


def _limpiar_codigo(val: Any) -> str:
    if val is None:
        return ""
    try:
        if pd.isna(val):
            return ""
    except Exception:
        pass
    s = str(val).strip().upper()
    if not s or s in ("NAN", "NONE", "NULL"):
        return ""
    # Remove trailing .0 like Excel numeric codes (e.g., 123.0)
    if s.endswith(".0"):
        base = s[:-2]
        if base and (base.isdigit() or (base.startswith("-") and base[1:].isdigit())):
            s = base
    # General regex for .0 suffix
    s = re.sub(r"\.0$", "", s)
    s = s.strip()
    if s in ("NAN", "NONE", ""):
        return ""
    return s


def _parse_decimal(val: Any) -> float | None:
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except Exception:
        pass
    if isinstance(val, (int, float)):
        try:
            f = float(val)
            if pd.isna(f):
                return None
            return f
        except Exception:
            return None
    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", "-", ""):
        return None
    # Handle AR format: remove $, spaces
    s = s.replace("$", "").replace(" ", "").replace("\u00a0", "")
    # Handle both . and , present: last separator is decimal
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        parts = s.split(",")
        if len(parts[-1]) <= 2:
            s = ",".join(parts[:-1]).replace(".", "") + "." + parts[-1]
        else:
            s = s.replace(",", "")
    # Remove thousand separators if needed
    try:
        return float(s)
    except ValueError:
        # Fallback via pandas
        try:
            v = pd.to_numeric(s, errors="coerce")
            if pd.isna(v):
                return None
            return float(v)
        except Exception:
            return None


def _normalize_importancia(val: Any) -> str:
    s = str(val or "").strip().upper()
    if not s or s in ("NAN", "NONE"):
        return "BASE"
    # Remove accents for comparison
    sn = _norm_header(s).replace("_", " ").replace("-", " ")
    if "crit" in sn:
        return "CRITICO"
    if "alta" in sn and ("freq" in sn.replace(" ", "") or "frecuencia" in sn):
        return "ALTA FRECUENCIA"
    if sn.strip() in ("critico", "alta frecuencia", "base"):
        # Map to ENUM exact
        if "critico" in sn:
            return "CRITICO"
        if "alta frecuencia" in sn:
            return "ALTA FRECUENCIA"
        return "BASE"
    if s in ("CRITICO", "ALTA FRECUENCIA", "BASE"):
        return s
    return "BASE"


def _detectar_columnas(df: pd.DataFrame) -> dict[str, str]:
    """Return mapping db_field -> actual column name in df."""
    cols = list(df.columns)
    # Normalized maps
    norm_map = {_norm_header(c): c for c in cols}
    nospace_map = {_norm_nospace(c): c for c in cols}

    result: dict[str, str] = {}

    # --- codigo: variants codigo/cod/sku/code ---
    # Try nospace exact
    for cand in ("codigo", "cod", "sku", "code", "codigoproducto", "articulocodigo"):
        if cand in nospace_map:
            result["codigo"] = nospace_map[cand]
            break
    if "codigo" not in result:
        for c in cols:
            nh = _norm_header(c)
            if nh in ("codigo", "cod", "sku") or nh.startswith("codigo"):
                result["codigo"] = c
                break
    # Fallback: first column that contains 'cod' and not 'desc'
    if "codigo" not in result:
        for c in cols:
            nh = _norm_nospace(c)
            if "codigo" in nh or nh == "cod":
                result["codigo"] = c
                break

    # --- descripcion ---
    for c in cols:
        nh = _norm_header(c)
        if nh in ("descripcion", "articulo", "articulo_descripcion", "detalle", "nombre", "desc"):
            result["descripcion"] = c
            break
    if "descripcion" not in result:
        for c in cols:
            nh = _norm_header(c)
            if "desc" in nh or "detalle" in nh or "nombre" in nh:
                # avoid precio column
                if "precio" not in nh and "costo" not in nh:
                    result["descripcion"] = c
                    break
    # Generic fallback: if no descripcion found but 2nd column might be it, pick first non-codigo text column
    # Keep as is if not found.

    # --- stock actual: scoring similar to _col_stock_actual_maestro ---
    scored: list[tuple[int, str]] = []
    for c in cols:
        nhr = _norm_nospace(c)
        if "precio" in nhr or nhr == "codigo":
            continue
        if "importancia" in nhr:
            continue
        # Exclude minimo columns for stock actual detection (unless also has actual)
        if ("min" in nhr or "minimo" in nhr) and "act" not in nhr and "actual" not in nhr and "cant" not in nhr and "disp" not in nhr:
            continue
        score = 0
        if "actual" in nhr or nhr.endswith("act"):
            score += 100
        if "dispon" in nhr:
            score += 90
        if "stock" in nhr and "min" not in nhr:
            score += 70
        if "cant" in nhr or "qty" in nhr:
            score += 65
        if "minimo" in nhr or (nhr.startswith("min") and "stock" not in nhr):
            score -= 100
        if score > 0:
            scored.append((score, c))
    if scored:
        scored.sort(key=lambda x: -x[0])
        result["stock"] = scored[0][1]
    else:
        for c in cols:
            nh = _norm_nospace(c)
            if "minimo" in nh or nh == "min" or (nh.endswith("min") and "act" not in nh and "cant" not in nh):
                continue
            sl = str(c).lower()
            if "stock" in sl or "act" in sl or "cant" in sl:
                result["stock"] = c
                break

    # --- stock_minimo ---
    for c in cols:
        nh = _norm_nospace(c)
        if nh in ("min", "minimo") or "minimo" in nh or nh.endswith("min"):
            result["stock_minimo"] = c
            break
    if "stock_minimo" not in result:
        for c in cols:
            nh = _norm_header(c)
            if "min" in nh:
                result["stock_minimo"] = c
                break

    # --- precio ---
    for c in cols:
        nh = _norm_nospace(c)
        if nh in ("preciounitario", "pu", "punit", "costouni", "costo uni"):
            result["precio_unitario"] = c
            break
        if nh == "preciounitario" or nh == "costouni":
            result["precio_unitario"] = c
            break
    if "precio_unitario" not in result:
        for c in cols:
            nh = _norm_header(c)
            if "precio" in nh:
                result["precio_unitario"] = c
                break
            if "costo" in nh and "uni" in nh:
                result["precio_unitario"] = c
                break

    # --- ubicacion ---
    for c in cols:
        nh = _norm_header(c)
        if "ubic" in nh or "pos" in nh or "estant" in nh or "almacen" in nh:
            # Prefer ubicacion
            if "ubic" in nh:
                result["ubicacion"] = c
                break
    if "ubicacion" not in result:
        for c in cols:
            nh = _norm_header(c)
            if "ubic" in nh or "estant" in nh or "almacen" in nh:
                result["ubicacion"] = c
                break

    # --- importancia / criticidad ---
    for c in cols:
        nh = _norm_header(c)
        if "importancia" in nh or "criticidad" in nh or nh == "critico" or "crit" in nh:
            result["importancia"] = c
            break
    # Avoid capturing price/desc as importancia
    if "importancia" in result and result["importancia"] in (result.get("descripcion"), result.get("precio_unitario")):
        # If duplicate, try more specific
        for c in cols:
            nh = _norm_header(c)
            if nh == "importancia" or nh == "criticidad":
                result["importancia"] = c
                break

    # --- categoria ---
    for c in cols:
        nh = _norm_header(c)
        if nh in ("categoria", "categoria_articulo", "familia", "rubro", "grupo"):
            result["categoria"] = c
            break
    if "categoria" not in result:
        for c in cols:
            nh = _norm_header(c)
            if "categoria" in nh or "familia" in nh:
                result["categoria"] = c
                break

    return result


def _resolve_excel_path(excel_arg: str | None) -> Path | None:
    if excel_arg:
        p = Path(excel_arg)
        if p.is_file():
            return p
        # Try resolving relative to repo root
        repo_root = Path(__file__).resolve().parents[2]
        cand = repo_root / excel_arg
        if cand.is_file():
            return cand
        print(f"[seed] Provided --excel not found: {excel_arg}")
        return None

    candidates: list[Path] = []
    # 1) Prod pañol base (shared drive)
    candidates.append(Path(r"G:\Unidades compartidas\Mantenimiento\MANTENIMIENTO  OZLA 2024-2025\17. Pañol\pañol v5.0\base_datos.xlsx"))
    candidates.append(Path(r"G:\Unidades compartidas\Mantenimiento\MANTENIMIENTO  OZLA 2024-2025\17. Pañol\pañol v5.0\master_codes.xlsx"))
    # 2) Local en migración (repo / desktop)
    candidates.append(Path(r"C:\Users\Pañol\Desktop\sistemas_panol\Local en migración\LABORATORIO BASE\base_datos.xlsx"))
    candidates.append(Path(r"C:\Users\Pañol\Desktop\sistemas_panol\Local en migración\LABORATORIO BASE\master_codes.xlsx"))
    candidates.append(Path(r"C:\Users\Pañol\Desktop\sistemas_panol\LABORATORIO BASE\base_datos.xlsx"))
    candidates.append(Path(r"C:\Users\Pañol\Desktop\sistemas_panol\LABORATORIO BASE\master_codes.xlsx"))
    # 3) Repo relative LAB... (when run from different cwd)
    repo_root2 = _SCRIPT_DIR.parents[1]
    candidates.append(repo_root2 / "LABORATORIO BASE" / "base_datos.xlsx")
    candidates.append(repo_root2 / "LABORATORIO BASE" / "master_codes.xlsx")
    candidates.append(repo_root2.parent / "LABORATORIO BASE" / "base_datos.xlsx")
    # 4) Data prueba fallback (backend/salidas/data_prueba)
    candidates.append(_SALIDAS_DIR / "data_prueba" / "base_datos.xlsx")
    candidates.append(_SALIDAS_DIR / "data_prueba" / "master_codes.xlsx")
    # 5) Project root direct
    candidates.append(Path("LABORATORIO BASE/base_datos.xlsx").resolve())
    candidates.append(Path("master_codes.xlsx").resolve())

    for p in candidates:
        try:
            if p.is_file():
                return p
        except Exception:
            continue
    return None


def _get_connection():
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
    )


def _ensure_tables(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS `maestro_stock` (
              `codigo` VARCHAR(40) COLLATE utf8mb4_unicode_ci NOT NULL,
              `descripcion` TEXT COLLATE utf8mb4_unicode_ci NOT NULL,
              `stock` DECIMAL(10,2) NOT NULL DEFAULT 0.00,
              `stock_minimo` DECIMAL(10,2) NOT NULL DEFAULT 0.00,
              `ubicacion` VARCHAR(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
              `precio_unitario` DECIMAL(12,2) NOT NULL DEFAULT 0.00,
              `importancia` ENUM('CRITICO','ALTA FRECUENCIA','BASE') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'BASE',
              `categoria` VARCHAR(80) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
              `activo` TINYINT(1) NOT NULL DEFAULT 1,
              `creado_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              `actualizado_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
              PRIMARY KEY (`codigo`),
              KEY `idx_maestro_stock_ubicacion` (`ubicacion`),
              KEY `idx_maestro_stock_importancia` (`importancia`),
              KEY `idx_maestro_stock_categoria` (`categoria`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        )
    conn.commit()


def seed(excel_path: Path | None, dry_run: bool = False) -> dict[str, Any]:
    start = time.time()
    resolved = excel_path or _resolve_excel_path(None)
    if not resolved or not resolved.is_file():
        print(f"[seed] Excel not found. Tried candidates; use --excel PATH to specify.")
        if excel_path:
            print(f"  Provided: {excel_path}")
        return {"error": "Excel not found", "leidos": 0}

    print(f"[seed] Reading {resolved} sheet={HOJA_ARTICULOS}")
    try:
        # Use dtype=object to preserve raw values
        xls = pd.ExcelFile(resolved, engine="openpyxl")
        sheet_name = HOJA_ARTICULOS if HOJA_ARTICULOS in xls.sheet_names else xls.sheet_names[0]
        print(f"[seed] Using sheet: {sheet_name} (available: {xls.sheet_names})")
        df_raw = pd.read_excel(xls, sheet_name=sheet_name, dtype=object)
    except Exception as e:
        print(f"[seed] Failed to read Excel: {e}")
        return {"error": str(e), "leidos": 0}

    if df_raw is None or df_raw.empty:
        print("[seed] Sheet empty")
        return {"leidos": 0, "insertados": 0, "actualizados": 0, "sin_precio": 0}

    # Drop fully empty columns/rows
    df_raw = df_raw.dropna(axis=1, how="all")
    df_raw = df_raw.dropna(axis=0, how="all")
    print(f"[seed] Raw rows: {len(df_raw)}, cols: {list(df_raw.columns)[:10]}...")

    col_map = _detectar_columnas(df_raw)
    print(f"[seed] Detected columns: {col_map}")
    if "codigo" not in col_map:
        print(f"[seed] ERROR: could not detect codigo column. Columns: {list(df_raw.columns)}")
        return {"error": "codigo column not found", "leidos": len(df_raw)}

    leidos = 0
    insertados = 0
    actualizados = 0
    sin_precio = 0

    # Pre-clean and collect rows
    rows: list[dict[str, Any]] = []
    for _, r in df_raw.iterrows():
        cod_raw = r.get(col_map["codigo"])
        codigo = _limpiar_codigo(cod_raw)
        if not codigo or codigo in ("NAN", "NONE"):
            continue
        leidos += 1
        # Descripcion
        desc = ""
        if "descripcion" in col_map:
            v = r.get(col_map["descripcion"])
            if pd.notna(v):
                desc = str(v).strip()
        if not desc:
            desc = codigo  # fallback to codigo if empty, to satisfy NOT NULL
        # Stock
        stock = None
        if "stock" in col_map:
            stock = _parse_decimal(r.get(col_map["stock"]))
        stock = stock if stock is not None else 0.0
        # Stock minimo
        stock_min = None
        if "stock_minimo" in col_map:
            stock_min = _parse_decimal(r.get(col_map["stock_minimo"]))
        stock_min = stock_min if stock_min is not None else 0.0
        # Ubicacion
        ubic = None
        if "ubicacion" in col_map:
            v = r.get(col_map["ubicacion"])
            if pd.notna(v):
                s = str(v).strip()
                if s and s.lower() not in ("nan", "none"):
                    ubic = s
        # Precio
        precio = None
        if "precio_unitario" in col_map:
            precio = _parse_decimal(r.get(col_map["precio_unitario"]))
        precio = precio if precio is not None else 0.0
        # Importancia
        imp = "BASE"
        if "importancia" in col_map:
            imp = _normalize_importancia(r.get(col_map["importancia"]))
        # Categoria
        cat = None
        if "categoria" in col_map:
            v = r.get(col_map["categoria"])
            if pd.notna(v):
                s = str(v).strip()
                if s and s.lower() not in ("nan", "none"):
                    cat = s
        rows.append(
            {
                "codigo": codigo,
                "descripcion": desc,
                "stock": stock,
                "stock_minimo": stock_min,
                "ubicacion": ubic,
                "precio_unitario": precio,
                "importancia": imp,
                "categoria": cat,
            }
        )

    print(f"[seed] Clean rows to upsert: {len(rows)} (leidos={leidos})")
    if not rows:
        return {"leidos": leidos, "insertados": 0, "actualizados": 0, "sin_precio": 0}

    if dry_run:
        # Count sin_precio in memory without DB
        sin_precio = sum(1 for row in rows if not row["precio_unitario"] or float(row["precio_unitario"]) <= 0)
        elapsed = time.time() - start
        print(f"[dry-run] Would upsert {len(rows)} rows. sin_precio={sin_precio} elapsed={elapsed:.1f}s")
        print(f"[dry-run] Sample: {rows[:2]}")
        return {"leidos": leidos, "insertados": 0, "actualizados": 0, "sin_precio": sin_precio, "dry_run": True, "elapsed_s": elapsed}

    # DB upsert in batches
    conn = _get_connection()
    try:
        _ensure_tables(conn)
        # Fetch existing codigos to distinguish insert vs update (for reporting)
        existing: set[str] = set()
        with conn.cursor() as cur:
            cur.execute("SELECT codigo FROM maestro_stock")
            for row in cur.fetchall():
                existing.add(str(row["codigo"]).strip().upper())

        # Also fetch existing prices for price rule? We'll handle per row by checking DB row if needed.
        # For simplicity, we fetch existing prices in bulk as dict
        existing_prices: dict[str, float] = {}
        with conn.cursor() as cur:
            cur.execute("SELECT codigo, precio_unitario FROM maestro_stock")
            for row in cur.fetchall():
                try:
                    existing_prices[str(row["codigo"]).strip().upper()] = float(row["precio_unitario"] or 0)
                except Exception:
                    existing_prices[str(row["codigo"]).strip().upper()] = 0

        total_inserted = 0
        total_updated = 0

        # Deduplicate rows by codigo - last occurrence wins
        dedup: dict[str, dict[str, Any]] = {}
        for row in rows:
            dedup[row["codigo"]] = row
        uniq_rows = list(dedup.values())
        print(f"[seed] Deduped to {len(uniq_rows)} unique codigos (from {len(rows)})")

        for i in range(0, len(uniq_rows), BATCH_SIZE):
            batch = uniq_rows[i : i + BATCH_SIZE]
            with conn.cursor() as cur:
                for row in batch:
                    cod = row["codigo"]
                    is_new = cod not in existing
                    # Price rule: if incoming price 0 and existing >0, keep existing
                    precio_to_write = row["precio_unitario"]
                    if float(precio_to_write) == 0.0 and cod in existing_prices and float(existing_prices[cod]) > 0:
                        precio_to_write = existing_prices[cod]
                    # For seed, we do full upsert (no file-type restrictions). Empty already handled.
                    cur.execute(
                        """
                        INSERT INTO maestro_stock
                          (codigo, descripcion, stock, stock_minimo, ubicacion, precio_unitario, importancia, categoria, activo)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,1)
                        ON DUPLICATE KEY UPDATE
                          descripcion=VALUES(descripcion),
                          stock=VALUES(stock),
                          stock_minimo=VALUES(stock_minimo),
                          ubicacion=VALUES(ubicacion),
                          precio_unitario=VALUES(precio_unitario),
                          importancia=VALUES(importancia),
                          categoria=VALUES(categoria),
                          activo=1
                        """,
                        (
                            cod,
                            row["descripcion"],
                            row["stock"],
                            row["stock_minimo"],
                            row["ubicacion"],
                            precio_to_write,
                            row["importancia"],
                            row["categoria"],
                        ),
                    )
                    # Update counters via rowcount heuristic: 1=insert, 2=update
                    # pymysql rowcount for ON DUPLICATE: 1 inserted, 2 updated, 0 no change (but our values likely change)
                    # Fallback to is_new check
                    if is_new:
                        total_inserted += 1
                    else:
                        total_updated += 1
                    # Track price for subsequent rows in same batch
                    existing_prices[cod] = float(precio_to_write)
                    existing.add(cod)
            conn.commit()
            print(f"[seed] Batch {i//BATCH_SIZE+1} committed ({len(batch)} rows)")

        # Final sin_precio count from DB
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS cnt FROM maestro_stock WHERE precio_unitario IS NULL OR precio_unitario <= 0")
            row = cur.fetchone()
            sin_precio = int(row["cnt"]) if row else 0

        elapsed = time.time() - start
        print(f"[seed] Done. leidos={leidos} uniq={len(uniq_rows)} insertados={total_inserted} actualizados={total_updated} sin_precio={sin_precio} elapsed={elapsed:.1f}s")
        return {
            "leidos": leidos,
            "insertados": total_inserted,
            "actualizados": total_updated,
            "sin_precio": sin_precio,
            "elapsed_s": elapsed,
            "excel": str(resolved),
        }
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print(f"[seed] DB error: {e}")
        import traceback

        traceback.print_exc()
        return {"error": str(e), "leidos": leidos}
    finally:
        try:
            conn.close()
        except Exception:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed maestro_stock from Excel")
    parser.add_argument("--excel", type=str, default=None, help="Path to base_datos.xlsx or master_codes.xlsx")
    parser.add_argument("--dry-run", action="store_true", help="Parse Excel and report without DB writes")
    args = parser.parse_args()

    excel_arg = Path(args.excel) if args.excel else None
    result = seed(excel_arg, dry_run=args.dry_run)
    if "error" in result:
        print(f"[seed] Finished with error: {result['error']}")
        sys.exit(1)
    # Pretty summary
    print("--- Summary ---")
    for k, v in result.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
