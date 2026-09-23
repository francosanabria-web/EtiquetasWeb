# -*- coding: utf-8 -*-
"""Bulk load salida_activos.xlsx -> MariaDB tabla salida_activos.

- Lee G:\\...\\pañol v5.0\\salida_activos.xlsx (2 hojas: FUERA_DE_PLANTA / INGRESADO_A_PLANTA)
- Normaliza ambas hojas a un schema unificado con columna estado.
- Dedup por fingerprint: CODIGO|NUMERO_REMITO|NUMERO_PEDIDO|NUMERO_OC|NRO_SERIE|FECHA_SALIDA|EQUIPO_REPUESTO
- Idempotente: segunda corrida 0 dupes (verifica fingerprint existente en DB).
- Log: filas leidas, insertadas, dupes, errores.
- No borra el Excel original, solo migra.

Uso:
    python scripts/bulk_load_activos.py
    ACTIVOS_DB_ENABLED=1 python scripts/bulk_load_activos.py  # modo debug
"""

from __future__ import annotations

import os
import sys
import time
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import pymysql
from pymysql.cursors import DictCursor

# ── Config ──────────────────────────────────────────────────────

DEFAULT_PROD_BASE = Path(
    r"G:\Unidades compartidas\Mantenimiento\MANTENIMIENTO  OZLA 2024-2025\17. Pañol\pañol v5.0"
)
EXCEL_NAME = "salida_activos.xlsx"
SHEET_FUERA = "FUERA_DE_PLANTA"
SHEET_INGRESADOS = "INGRESADO_A_PLANTA"

DB_HOST = os.environ.get("ACTIVOS_DB_HOST", os.environ.get("DB_HOST", "127.0.0.1"))
DB_PORT = int(os.environ.get("ACTIVOS_DB_PORT", os.environ.get("DB_PORT", "3306")))
DB_USER = os.environ.get("ACTIVOS_DB_USER", os.environ.get("DB_USER", "root"))
DB_PASSWORD = os.environ.get("ACTIVOS_DB_PASSWORD", os.environ.get("DB_PASSWORD", ""))
DB_NAME = os.environ.get("ACTIVOS_DB_NAME", os.environ.get("DB_NAME", "panol"))

COLUMNAS = [
    "NUMERO_PEDIDO", "NUMERO_OC", "NUMERO_REMITO", "SECTOR", "CODIGO",
    "EQUIPO_REPUESTO", "CANTIDAD", "NRO_SERIE", "FECHA_SALIDA",
    "PROVEEDOR", "FECHA_REGRESO", "ESTADO_AL_INGRESO", "OBSERVACIONES",
    "DIAS_FUERA", "ESTADO",
]

_ALIAS = {
    "NUMERO PEDIDO": "NUMERO_PEDIDO", "NUMERO OC": "NUMERO_OC",
    "NUMERO REMITO": "NUMERO_REMITO", "EQUIPO REPUESTO": "EQUIPO_REPUESTO",
    "NRO SERIE": "NRO_SERIE", "FECHA SALIDA": "FECHA_SALIDA",
    "FECHA REGRESO": "FECHA_REGRESO", "ESTADO AL INGRESO": "ESTADO_AL_INGRESO",
    "DIAS FUERA": "DIAS_FUERA",
}

# ── Helpers ─────────────────────────────────────────────────────

def _norm_header(name: object) -> str:
    s = str(name or "").strip().upper()
    return _ALIAS.get(s, s.replace(" ", "_"))


def _mapear_columnas(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=COLUMNAS)
    ren = {c: _norm_header(c) for c in df.columns}
    out = df.rename(columns=ren)
    out = out.loc[:, ~out.columns.duplicated()]
    for col in COLUMNAS:
        if col not in out.columns:
            out[col] = ""
    return out[COLUMNAS].copy()


def _parse_fecha(val: object) -> date | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    s = str(val).strip()
    if not s or s.lower() in ("nan", "nat", "none", "-", "0", "0.0"):
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    ts = pd.to_datetime(s, errors="coerce", dayfirst=True)
    if not pd.isna(ts):
        return ts.date()
    return None


def _norm_doc(val: object) -> str:
    s = str(val or "").strip()
    if s.endswith(".0") and s[:-2].isdigit():
        return s[:-2]
    return s if s and s.lower() not in ("nan", "none") else ""


def _norm_text(val: object) -> str:
    s = str(val or "").strip()
    return "" if s.lower() in ("nan", "none", "nat") else s


def _norm_cantidad(val: object) -> int:
    try:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return 1
        s = str(val).strip().replace(",", ".")
        if not s or s.lower() in ("nan", "-", ""):
            return 1
        return max(1, int(float(s)))
    except (TypeError, ValueError):
        return 1


def _fingerprint(row: pd.Series) -> str:
    """Clave dedup basada en fingerprint_row de excel_io.py."""
    parts = [
        _norm_doc(row.get("CODIGO", "")),
        _norm_doc(row.get("NUMERO_REMITO", "")),
        _norm_doc(row.get("NUMERO_PEDIDO", "")),
        _norm_doc(row.get("NUMERO_OC", "")),
        _norm_text(row.get("NRO_SERIE", "")),
        _parse_fecha(row.get("FECHA_SALIDA")) and _parse_fecha(row.get("FECHA_SALIDA")).isoformat(),
        _norm_text(row.get("EQUIPO_REPUESTO", "")),
    ]
    return "|".join(parts)


def _get_connection() -> pymysql.connections.Connection:
    return pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD,
        database=DB_NAME, charset="utf8mb4", cursorclass=DictCursor, autocommit=False,
    )


def _leer_hoja(xls: pd.ExcelFile, sheet_name: str, fuera: bool) -> pd.DataFrame:
    """Lee una hoja del Excel y la normaliza."""
    raw = pd.read_excel(xls, sheet_name=sheet_name)
    df = _mapear_columnas(raw)
    # Parsear fechas
    df["_fecha"] = df["FECHA_SALIDA"].map(_parse_fecha)
    df["FECHA_SALIDA"] = df["_fecha"]
    # Normalizar campos
    for col in ("CODIGO", "EQUIPO_REPUESTO", "SECTOR", "PROVEEDOR", "OBSERVACIONES",
                "NUMERO_PEDIDO", "NUMERO_OC", "NUMERO_REMITO", "NRO_SERIE",
                "ESTADO_AL_INGRESO", "ESTADO"):
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().replace({"nan": "", "None": "", "NaT": ""})
    df["CANTIDAD"] = df["CANTIDAD"].map(_norm_cantidad)
    df["DIAS_FUERA"] = pd.to_numeric(df.get("DIAS_FUERA", 0), errors="coerce").fillna(0).astype(int)
    df["ESTADO"] = df["ESTADO"].str.upper().replace({"FUERA DE PLANTA": "FUERA_DE_PLANTA", "INGRESADO A PLANTA": "INGRESADO_A_PLANTA"})
    # Asegurar que estado coincida con la hoja
    df["ESTADO"] = "fuera_de_planta" if fuera else "ingresado_a_planta"
    # FECHA_REGRESO
    df["_fecha_regreso"] = df["FECHA_REGRESO"].map(_parse_fecha)
    # Calcular fingerprint
    df["_fingerprint"] = df.apply(_fingerprint, axis=1)
    return df


def _collect_excel_paths() -> list[Path]:
    """Busca salida_activos.xlsx en la ruta configurada."""
    paths: list[Path] = []
    candidate = DEFAULT_PROD_BASE / EXCEL_NAME
    if candidate.is_file():
        paths.append(candidate)
    else:
        # Buscar en subdirs cercanos
        for p in DEFAULT_PROD_BASE.glob("salida_activos*.xlsx"):
            paths.append(p)
    return paths


def main() -> int:
    t0 = time.time()
    print("== Bulk load salida_activos.xlsx -> MariaDB salida_activos ==")
    print(f"DB: {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
    print(f"Excel: {DEFAULT_PROD_BASE / EXCEL_NAME}")

    # ── Verificar Excel ──
    excel_path = DEFAULT_PROD_BASE / EXCEL_NAME
    if not excel_path.is_file():
        print(f"ERROR: No se encontro {excel_path}")
        return 1

    # ── Verificar DB y table ──
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS c FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s",
                (DB_NAME, "salida_activos"),
            )
            table_exists = cur.fetchone()["c"] > 0
            if not table_exists:
                print("ERROR: Tabla salida_activos no existe. Ejecutar primero activos_migracion_v1.sql")
                return 1
            cur.execute("SELECT fingerprint FROM salida_activos")
            existing_fingerprints: set[str] = set()
            for r in cur.fetchall():
                existing_fingerprints.add(r["fingerprint"])
            print(f"Fingerprints existentes en DB: {len(existing_fingerprints)}")
    finally:
        conn.close()

    # ── Leer Excel ──
    xls = pd.ExcelFile(excel_path, engine="openpyxl")
    print(f"Hojas encontradas: {xls.sheet_names}")

    df_fuera = _leer_hoja(xls, SHEET_FUERA, fuera=True)
    df_ing = _leer_hoja(xls, SHEET_INGRESADOS, fuera=False)
    xls.close()

    df = pd.concat([df_fuera, df_ing], ignore_index=True, sort=False)
    print(f"Filas Excel: FUERA={len(df_fuera)}, INGRESADO={len(df_ing)}, TOTAL={len(df)}")

    # ── Preparar filas para DB ──
    filas_db: list[dict] = []
    total_dup_db = 0
    total_dup_run = 0
    total_sin_fecha = 0
    pending_fps: set[str] = set()

    for _, row in df.iterrows():
        fp = row.get("_fingerprint", "")
        fecha_d = row.get("_fecha")
        if not isinstance(fecha_d, date):
            total_sin_fecha += 1
            continue
        if fp in existing_fingerprints:
            total_dup_db += 1
            continue
        if fp in pending_fps:
            total_dup_run += 1
            continue
        pending_fps.add(fp)
        filas_db.append({
            "fecha": fecha_d,
            "equipo": str(row.get("EQUIPO_REPUESTO") or "").strip(),
            "codigo": str(row.get("CODIGO") or "").strip(),
            "descripcion": str(row.get("EQUIPO_REPUESTO") or "").strip(),
            "sector": str(row.get("SECTOR") or "").strip(),
            "cantidad": int(row.get("CANTIDAD") or 1),
            "nro_serie": str(row.get("NRO_SERIE") or "").strip(),
            "numero_pedido": str(row.get("NUMERO_PEDIDO") or "").strip(),
            "numero_oc": str(row.get("NUMERO_OC") or "").strip(),
            "numero_remito": str(row.get("NUMERO_REMITO") or "").strip(),
            "proveedor": str(row.get("PROVEEDOR") or "").strip(),
            "fecha_salida": fecha_d,
            "fecha_regreso": row.get("_fecha_regreso") if isinstance(row.get("_fecha_regreso"), date) else None,
            "estado_al_ingreso": str(row.get("ESTADO_AL_INGRESO") or "").strip(),
            "observaciones": str(row.get("OBSERVACIONES") or "").strip(),
            "dias_fuera": int(row.get("DIAS_FUERA") or 0),
            "estado": str(row.get("ESTADO") or "fuera_de_planta").strip(),
            "fingerprint": fp,
        })

    print("--- Resumen lectura ---")
    print(f"Total filas Excel leidas: {len(df)}")
    print(f"Filas sin fecha valida: {total_sin_fecha}")
    print(f"Dupes existentes DB: {total_dup_db}")
    print(f"Dupes dentro del run: {total_dup_run}")
    print(f"A insertar: {len(filas_db)}")

    if not filas_db:
        print("Nada para insertar. Todo esta sincronizado.")
        return 0

    # ── Insercion batch transaccional ──
    conn2 = _get_connection()
    try:
        with conn2.cursor() as cur:
            ids = []
            for fila in filas_db:
                cur.execute(
                    """
                    INSERT INTO salida_activos
                      (fecha, equipo, codigo, descripcion, sector, cantidad,
                       nro_serie, numero_pedido, numero_oc, numero_remito,
                       proveedor, fecha_salida, fecha_regreso,
                       estado_al_ingreso, observaciones, dias_fuera,
                       estado, fingerprint, creado_en, actualizado_en)
                    VALUES
                      (%(fecha)s, %(equipo)s, %(codigo)s, %(descripcion)s, %(sector)s, %(cantidad)s,
                       %(nro_serie)s, %(numero_pedido)s, %(numero_oc)s, %(numero_remito)s,
                       %(proveedor)s, %(fecha_salida)s, %(fecha_regreso)s,
                       %(estado_al_ingreso)s, %(observaciones)s, %(dias_fuera)s,
                       %(estado)s, %(fingerprint)s, NOW(), NOW())
                    """,
                    fila,
                )
                ids.append(cur.lastrowid)
        conn2.commit()
        print(f"Insertados {len(ids)} filas. Primeros ids: {ids[:5]}")
    except Exception as e:
        try:
            conn2.rollback()
        except Exception:
            pass
        print(f"ERROR insert: {e}")
        raise
    finally:
        try:
            conn2.close()
        except Exception:
            pass

    # ── Verificacion ──
    conn3 = _get_connection()
    try:
        with conn3.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS c FROM salida_activos")
            total = cur.fetchone()["c"]
            cur.execute("SELECT estado, COUNT(*) AS c FROM salida_activos GROUP BY estado")
            por_estado = cur.fetchall()
            print(f"DB total salida_activos: {total}")
            for r in por_estado:
                print(f"  estado={r['estado']}: {r['c']}")
    finally:
        conn3.close()

    print(f"Duracion: {time.time()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
