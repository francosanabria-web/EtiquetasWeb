# -*- coding: utf-8 -*-
"""Bulk load Septiembre 2026 -> salida_historial (sin pisar live 21-22 Sep).

- No borra ni modifica las 65 filas existentes (21-22 Sep).
- Dedup por clave corta FECHA+CODIGO+CANTIDAD+NUMERO_ORDEN (igual a sync_salidas_diaria / ReportesStore._row_key).
- Lee:
    * G:\\...\\pañol v5.0\\salidas_*.xlsx (raiz)
    * G:\\...\\pañol v5.0\\salidas_diaria\\salidas_*.xlsx
    * G:\\...\\pañol v5.0\\master_salidas.xlsx (hoja Movimientos) filtrando Septiembre
- Solo inserta filas con fecha 2026-09-01..2026-09-30 no existentes en DB.
- Usa pymysql directo (mismo DSN que backend/salidas/config.py).
- Log: archivos, filas Excel, insertadas, dupes, fuera de mes.
"""

from __future__ import annotations

import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import pymysql
from pymysql.cursors import DictCursor

# ── Config ──────────────────────────────────────────────────────────────
DB_HOST = os.environ.get("SALIDAS_DB_HOST", os.environ.get("DB_HOST", "127.0.0.1"))
DB_PORT = int(os.environ.get("SALIDAS_DB_PORT", os.environ.get("DB_PORT", "3306")))
DB_USER = os.environ.get("SALIDAS_DB_USER", os.environ.get("DB_USER", "root"))
DB_PASSWORD = os.environ.get("SALIDAS_DB_PASSWORD", os.environ.get("DB_PASSWORD", ""))
DB_NAME = os.environ.get("SALIDAS_DB_NAME", os.environ.get("DB_NAME", "panol"))

DEFAULT_PROD_BASE = Path(r"G:\Unidades compartidas\Mantenimiento\MANTENIMIENTO  OZLA 2024-2025\17. Pañol\pañol v5.0")
MASTER_PATH = DEFAULT_PROD_BASE / "master_salidas.xlsx"

MES_NOMBRES = {
    1: "Enero.", 2: "Febrero.", 3: "Marzo.", 4: "Abril.", 5: "Mayo.", 6: "Junio.",
    7: "Julio.", 8: "Agosto.", 9: "Septiembre.", 10: "Octubre.", 11: "Noviembre.", 12: "Diciembre.",
}

COLUMNAS = ["FECHA","MES","AÑO","CODIGO","DESCRIPCION","UBICACION","CANTIDAD","TIPO_COMPROBANTE","NUMERO_ORDEN","MAQUINA_SITIO","PRECIO_UNITARIO","MONTO_TOTAL_SALIDA","OPERARIO","SECTOR"]

# ── Helpers ─────────────────────────────────────────────────────────────

def nombre_mes(m: int) -> str:
    return MES_NOMBRES.get(int(m), "")

def _norm_header(name: object) -> str:
    s = str(name or "").strip().upper().replace(" ", "_").replace(".", "")
    alias = {
        "ANO": "AÑO", "ANIO": "AÑO", "A¿O": "AÑO", "AÑO": "AÑO",
        "PRECIO": "PRECIO_UNITARIO", "COSTO_UNITARIO": "PRECIO_UNITARIO",
        "MONTO": "MONTO_TOTAL_SALIDA", "MONTO_TOTAL": "MONTO_TOTAL_SALIDA", "TOTAL": "MONTO_TOTAL_SALIDA",
        "ORDEN": "NUMERO_ORDEN", "NRO_ORDEN": "NUMERO_ORDEN", "NUM_ORDEN": "NUMERO_ORDEN",
        "COMPROBANTE": "TIPO_COMPROBANTE", "TIPO": "TIPO_COMPROBANTE",
        "MAQUINA": "MAQUINA_SITIO", "SITIO": "MAQUINA_SITIO",
        "UBICACIÓN": "UBICACION", "DESCRIPCIÓN": "DESCRIPCION",
    }
    # Fix garbled encoding variants: A�O, A?O, etc -> normalize
    if s in ("A�O", "A?O", "AÑO", "ANO"):
        return "AÑO"
    return alias.get(s, s)

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
    if isinstance(val, pd.Timestamp):
        if pd.isna(val):
            return None
        return val.date()
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        try:
            if 20000 < float(val) < 60000:
                return pd.to_datetime(float(val), unit="D", origin="1899-12-30").date()
        except Exception:
            pass
    s = str(val).strip()
    if not s or s.lower() in ("nan","none","nat",""):
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    # dayfirst fallback
    ts = pd.to_datetime(s, errors="coerce", dayfirst=True)
    if not pd.isna(ts):
        return ts.date()
    ts = pd.to_datetime(s, errors="coerce", dayfirst=False)
    if not pd.isna(ts):
        return ts.date()
    return None

def _normalizar_orden(val: object) -> str:
    s = str(val or "").strip()
    if not s or s.lower() in ("nan","none","nat"):
        return ""
    # mimic excel_io.normalizar_orden but keep as string for DB VARCHAR
    s2 = s.replace(",", ".")
    try:
        f = float(s2)
        if f == int(f):
            return str(int(f))
        # keep as string without scientific
        return str(f).rstrip("0").rstrip(".") if "." in str(f) else str(f)
    except ValueError:
        return s

def _cant_key_str(val: object) -> str:
    try:
        f = float(val)
        f = round(f, 4)
        if f == 0:
            f = 0.0
        return str(f)
    except Exception:
        return "0.0"

def _row_key(fecha_iso: str, codigo: str, cantidad: object, numero_orden: str) -> tuple[str,str,str,str]:
    cod = str(codigo or "").strip().upper()
    num = _normalizar_orden(numero_orden).upper()
    cant_s = _cant_key_str(cantidad)
    return (fecha_iso, cod, cant_s, num)

def _leer_excel_normalizado(path: Path) -> pd.DataFrame:
    """Lee excel (sheet Movimientos si existe) y normaliza a COLUMNAS + _fecha."""
    xls = pd.ExcelFile(path, engine="openpyxl")
    sheet = "Movimientos" if "Movimientos" in xls.sheet_names else 0
    raw = pd.read_excel(xls, sheet_name=sheet)
    df = _mapear_columnas(raw)
    # parse FECHA -> _fecha date
    def _pf(v):
        return _parse_fecha(v)
    fechas = df["FECHA"].map(_pf)
    df["_fecha"] = fechas
    # fill MES/AÑO from FECHA if empty
    def _is_empty(v):
        s = str(v).strip() if not pd.isna(v) else ""
        return s in ("", "nan", "None", "NaT", "0", "0.0")
    for idx, row in df.iterrows():
        f = row["_fecha"]
        if isinstance(f, date):
            if _is_empty(row["MES"]):
                df.at[idx, "MES"] = nombre_mes(f.month)
            if _is_empty(row["AÑO"]):
                df.at[idx, "AÑO"] = str(f.year)
        # cantidad numeric
    for col in ("CANTIDAD","PRECIO_UNITARIO","MONTO_TOTAL_SALIDA"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    for col in ("CODIGO","DESCRIPCION","UBICACION","TIPO_COMPROBANTE","NUMERO_ORDEN","MAQUINA_SITIO","OPERARIO","SECTOR"):
        df[col] = df[col].astype(str).str.strip().replace({"nan":"","None":"","NaT":""})
    df["TIPO_COMPROBANTE"] = df["TIPO_COMPROBANTE"].str.upper()
    df.loc[df["TIPO_COMPROBANTE"].isin(("PAÑ","PAN","PANOL")), "TIPO_COMPROBANTE"] = "PAÑOL"
    # PAÑ handling with accent
    df.loc[df["TIPO_COMPROBANTE"].str.upper().isin(("PAÑ","PAÑOL")), "TIPO_COMPROBANTE"] = "PAÑOL"
    df["SECTOR"] = df["SECTOR"].str.upper()
    return df

def _collect_excel_paths() -> list[Path]:
    paths: list[Path] = []
    seen: set[str] = set()
    # root
    if DEFAULT_PROD_BASE.is_dir():
        for p in sorted(DEFAULT_PROD_BASE.glob("salidas_*.xlsx")):
            if p.name.lower() == "master_salidas.xlsx":
                continue
            low = p.name.lower()
            if low not in seen:
                seen.add(low)
                paths.append(p)
        sd = DEFAULT_PROD_BASE / "salidas_diaria"
        if sd.is_dir():
            for p in sorted(sd.glob("salidas_*.xlsx")):
                if p.name.lower() == "master_salidas.xlsx":
                    continue
                low = p.name.lower()
                if low not in seen:
                    seen.add(low)
                    paths.append(p)
                else:
                    # keep larger/newer if duplicate name in both dirs
                    ex = next((x for x in paths if x.name.lower() == low), None)
                    if ex:
                        try:
                            if p.stat().st_size > ex.stat().st_size or (p.stat().st_size == ex.stat().st_size and p.stat().st_mtime > ex.stat().st_mtime):
                                paths.remove(ex)
                                paths.append(p)
                        except OSError:
                            pass
    # master last (so dedup prefers master? but we want pending dedup, order doesn't matter much)
    # We'll put master first so pending set fills from master then diarios are considered dupes
    if MASTER_PATH.is_file():
        # Move master to front
        paths = [MASTER_PATH] + [p for p in paths if p != MASTER_PATH]
    return paths

def get_connection():
    return pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, database=DB_NAME, charset="utf8mb4", cursorclass=DictCursor, autocommit=False)

def main():
    t0 = time.time()
    print("== Bulk load Septiembre 2026 -> salida_historial ==")
    print(f"DB: {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
    print(f"Base: {DEFAULT_PROD_BASE}")
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS c FROM salida_historial")
            tot0 = cur.fetchone()["c"]
            print(f"DB total antes: {tot0}")
            cur.execute("SELECT fecha, COUNT(*) AS c FROM salida_historial WHERE fecha BETWEEN %s AND %s GROUP BY fecha ORDER BY fecha", ("2026-09-01","2026-09-30"))
            rows_pre = cur.fetchall()
            print(f"Septiembre antes: {[ (str(r['fecha']), r['c']) for r in rows_pre ]}")
            cur.execute("SELECT fecha, codigo, cantidad, numero_orden FROM salida_historial WHERE fecha BETWEEN %s AND %s", ("2026-09-01","2026-09-30"))
            existing = cur.fetchall()
            db_keys: set[tuple[str,str,str,str]] = set()
            for r in existing:
                fecha_iso = r["fecha"].isoformat() if isinstance(r["fecha"], (date, datetime)) else str(r["fecha"])
                key = _row_key(fecha_iso, r["codigo"], r["cantidad"], r["numero_orden"])
                db_keys.add(key)
            print(f"Keys existentes en DB Sept: {len(db_keys)}")
    finally:
        conn.close()

    paths = _collect_excel_paths()
    print(f"Archivos candidatos: {len(paths)}")
    for p in paths:
        print(f"  - {p.name} ({p})")

    total_excel_rows = 0
    total_fuera_mes = 0
    total_ceros = 0
    total_dup_db = 0
    total_dup_run = 0
    total_a_insertar = 0
    pending_keys: set[tuple[str,str,str,str]] = set()
    filas_db: list[dict] = []

    for p in paths:
        try:
            if p.stat().st_size < 100:
                print(f"Skip tiny: {p.name}")
                continue
        except OSError:
            continue
        try:
            df = _leer_excel_normalizado(p)
        except Exception as e:
            print(f"ERROR leyendo {p.name}: {e}")
            continue
        print(f"Leyendo {p.name}: {len(df)} filas")
        for idx, row in df.iterrows():
            total_excel_rows += 1
            fecha_d = row.get("_fecha")
            if not isinstance(fecha_d, date):
                total_fuera_mes += 1
                continue
            if fecha_d < date(2026,9,1) or fecha_d > date(2026,9,30):
                total_fuera_mes += 1
                continue
            codigo = str(row.get("CODIGO") or "").strip().upper()
            if not codigo:
                total_ceros += 1
                continue
            try:
                cantidad = float(row.get("CANTIDAD") or 0)
            except Exception:
                cantidad = 0.0
            if cantidad == 0:
                total_ceros += 1
                continue
            numero_orden = _normalizar_orden(row.get("NUMERO_ORDEN"))
            fecha_iso = fecha_d.isoformat()
            key = _row_key(fecha_iso, codigo, cantidad, numero_orden)
            if key in db_keys:
                total_dup_db += 1
                continue
            if key in pending_keys:
                total_dup_run += 1
                continue
            # preparar fila DB
            # mes nombre y anio
            mes_nombre = str(row.get("MES") or "").strip()
            if not mes_nombre or mes_nombre.lower() in ("nan","none","", "0"):
                mes_nombre = nombre_mes(fecha_d.month)
            try:
                anio_val = int(float(str(row.get("AÑO") or fecha_d.year)))
            except Exception:
                anio_val = fecha_d.year
            descripcion = str(row.get("DESCRIPCION") or "").strip().upper()
            ubicacion = str(row.get("UBICACION") or "").strip().upper()
            tipo_comp = str(row.get("TIPO_COMPROBANTE") or "").strip().upper()
            if tipo_comp in ("PAÑ","PAN"):
                tipo_comp = "PAÑOL"
            maquina = str(row.get("MAQUINA_SITIO") or "").strip().upper()
            try:
                precio = float(row.get("PRECIO_UNITARIO") or 0)
            except Exception:
                precio = 0.0
            try:
                monto = float(row.get("MONTO_TOTAL_SALIDA") or 0)
            except Exception:
                monto = round(abs(cantidad) * abs(precio), 2)
            if monto == 0 and precio != 0:
                monto = round(abs(cantidad) * abs(precio), 2)
                if cantidad < 0:
                    monto = -monto
            operario = str(row.get("OPERARIO") or "").strip().upper()
            sector = str(row.get("SECTOR") or "").strip().upper()
            es_dev = 1 if cantidad < 0 else 0
            fila = {
                "fecha": fecha_d,
                "mes": mes_nombre,
                "anio": anio_val,
                "codigo": codigo,
                "descripcion": descripcion if descripcion else None,
                "ubicacion": ubicacion if ubicacion else None,
                "cantidad": cantidad,
                "tipo_comprobante": tipo_comp if tipo_comp else None,
                "numero_orden": numero_orden if numero_orden else None,
                "maquina_sitio": maquina if maquina else None,
                "precio_unitario": precio if precio != 0 else None,
                "monto_total": monto if monto != 0 else None,
                "operario_nombre": operario if operario else None,
                "sector_nombre": sector if sector else None,
                "es_devolucion": es_dev,
                "creado_por": "bulk_septiembre_2026",
            }
            filas_db.append(fila)
            pending_keys.add(key)
            total_a_insertar += 1
        # debug per file
        print(f"  -> acumulado a insertar: {total_a_insertar}, dup_db: {total_dup_db}, dup_run: {total_dup_run}")

    print("--- Resumen lectura ---")
    print(f"Total filas Excel leidas: {total_excel_rows}")
    print(f"Fuera de Septiembre o fecha invalida: {total_fuera_mes}")
    print(f"Ceros/codigo vacio: {total_ceros}")
    print(f"Dupes existentes DB: {total_dup_db}")
    print(f"Dupes dentro del run: {total_dup_run}")
    print(f"A insertar: {len(filas_db)}")

    if not filas_db:
        print("Nada para insertar.")
    else:
        # Insercion batch transaccional
        conn2 = get_connection()
        try:
            with conn2.cursor() as cur:
                ids = []
                for fila in filas_db:
                    cur.execute(
                        """
                        INSERT INTO salida_historial
                          (fecha, mes, anio, codigo, descripcion, ubicacion, cantidad,
                           tipo_comprobante, numero_orden, maquina_sitio,
                           precio_unitario, monto_total,
                           operario_nombre, sector_nombre,
                           es_devolucion, creado_por)
                        VALUES
                          (%(fecha)s, %(mes)s, %(anio)s, %(codigo)s, %(descripcion)s, %(ubicacion)s, %(cantidad)s,
                           %(tipo_comprobante)s, %(numero_orden)s, %(maquina_sitio)s,
                           %(precio_unitario)s, %(monto_total)s,
                           %(operario_nombre)s, %(sector_nombre)s,
                           %(es_devolucion)s, %(creado_por)s)
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

    # Verificacion
    conn3 = get_connection()
    try:
        with conn3.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS c FROM salida_historial")
            tot1 = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) AS c FROM salida_historial WHERE fecha BETWEEN %s AND %s", ("2026-09-01","2026-09-30"))
            sept1 = cur.fetchone()["c"]
            cur.execute("SELECT fecha, COUNT(*) AS c FROM salida_historial WHERE fecha BETWEEN %s AND %s GROUP BY fecha ORDER BY fecha", ("2026-09-01","2026-09-30"))
            rows_post = cur.fetchall()
            print(f"DB total despues: {tot1} (antes {tot0}, delta {tot1-tot0})")
            print(f"Septiembre despues: {sept1}")
            for r in rows_post:
                print(f"  {r['fecha'].isoformat()}: {r['c']}")
            # verificar que 21-22 preservados
            cur.execute("SELECT COUNT(*) AS c FROM salida_historial WHERE fecha IN (%s,%s)", ("2026-09-21","2026-09-22"))
            c2122 = cur.fetchone()["c"]
            print(f"21-22 Sep count (debe ser 65): {c2122}")
    finally:
        conn3.close()

    print(f"Duracion: {time.time()-t0:.1f}s")
    return 0

if __name__ == "__main__":
    sys.exit(main())

