# -*- coding: utf-8 -*-
"""Read-only loader for movimientos from CSV/XLSX (master_salidas).

Never writes to the Excel. Store layer is swappable: tomorrow it can read
MariaDB or the Salidas API without changing service/main.

Live in-memory merge: master_salidas.xlsx is the base (same source as KPIs),
plus any pending daily files salidas_*.xlsx that are not yet consolidated
into master. The merge happens purely in memory, without touching the file
on disk, so formatting is preserved.
"""

from __future__ import annotations

import io
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

import drive_source
from config import COLUMNAS, HOJA_MOVIMIENTOS, movimientos_path

try:
    from config import (
        DEFAULT_PROD_BASE,  # type: ignore
        REPORTES_DB_ENABLED,
        REPORTES_DB_HOST,
        REPORTES_DB_NAME,
        REPORTES_DB_PASSWORD,
        REPORTES_DB_PORT,
        REPORTES_DB_USER,
    )
except Exception:  # fallback if config changes
    DEFAULT_PROD_BASE = Path(
        r"G:\Unidades compartidas\Mantenimiento\MANTENIMIENTO  OZLA 2024-2025\17. Pañol\pañol v5.0"
    )
    REPORTES_DB_ENABLED = False
    REPORTES_DB_HOST = "127.0.0.1"
    REPORTES_DB_PORT = 3306
    REPORTES_DB_USER = "root"
    REPORTES_DB_PASSWORD = ""
    REPORTES_DB_NAME = "panol"

# Alias for backward compat with older config that may not expose DB vars
try:
    _ = REPORTES_DB_ENABLED
except NameError:
    REPORTES_DB_ENABLED = False

log = logging.getLogger("reportes.store")


# ── DB helpers ────────────────────────────────────────────────────────────

def _db_enabled() -> bool:
    try:
        return bool(REPORTES_DB_ENABLED)
    except Exception:
        return False


def _cargar_df_desde_db() -> pd.DataFrame:
    """Carga DataFrame desde salida_historial (solo filas activas).

    Mapea columnas snake_case DB -> COLUMNAS reportes (UPPER).
    Retorna DataFrame con COLUMNAS + _fecha, o DataFrame vacío si no hay filas.
    Lanza excepción si DB no disponible (para fallback a Excel).
    """
    import pymysql

    conn = pymysql.connect(
        host=REPORTES_DB_HOST,
        port=int(REPORTES_DB_PORT),
        user=REPORTES_DB_USER,
        password=REPORTES_DB_PASSWORD,
        database=REPORTES_DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with conn.cursor() as cur:
            # Check table exists quickly
            cur.execute("SELECT COUNT(*) AS c FROM salida_historial WHERE COALESCE(anulado,0)=0 LIMIT 1")
            # Real load - all active rows (September bulk is ~766, full history maybe few K)
            cur.execute(
                """
                SELECT fecha, mes, anio, codigo, descripcion, ubicacion, cantidad,
                       tipo_comprobante, numero_orden, maquina_sitio,
                       precio_unitario, monto_total,
                       operario_nombre, sector_nombre
                FROM salida_historial
                WHERE COALESCE(anulado,0)=0
                ORDER BY fecha DESC, id DESC
                LIMIT 200000
                """
            )
            rows = cur.fetchall()
            if not rows:
                return pd.DataFrame(columns=COLUMNAS + ["_fecha"])
            records: list[dict[str, Any]] = []
            for r in rows:
                fv = r.get("fecha")
                if isinstance(fv, datetime):
                    fv_date = fv.date()
                    fecha_iso = fv_date.isoformat()
                    fecha_ts = pd.Timestamp(fv_date)
                elif hasattr(fv, "isoformat"):
                    try:
                        fecha_iso = fv.isoformat()  # date
                        fecha_ts = pd.Timestamp(fv)
                    except Exception:
                        fecha_iso = str(fv)
                        fecha_ts = pd.to_datetime(fecha_iso, errors="coerce")
                else:
                    fecha_iso = str(fv or "")
                    fecha_ts = pd.to_datetime(fecha_iso, errors="coerce")
                mes = str(r.get("mes") or "").strip()
                anio = str(r.get("anio") or "").strip()
                # fallback if mes/anio empty
                if not mes or mes.lower() in ("none", "nan", "0") and not pd.isna(fecha_ts):
                    try:
                        m = int(pd.Timestamp(fecha_ts).month)
                        # replica nombre_mes from salidas config
                        _meses = {1:"Enero.",2:"Febrero.",3:"Marzo.",4:"Abril.",5:"Mayo.",6:"Junio.",7:"Julio.",8:"Agosto.",9:"Septiembre.",10:"Octubre.",11:"Noviembre.",12:"Diciembre."}
                        mes = _meses.get(m, "")
                    except Exception:
                        pass
                if (not anio or anio.lower() in ("none","nan","0")) and not pd.isna(fecha_ts):
                    try:
                        anio = str(int(pd.Timestamp(fecha_ts).year))
                    except Exception:
                        pass
                rec = {
                    "FECHA": fecha_iso,
                    "_fecha": fecha_ts,
                    "MES": mes,
                    "AÑO": anio,
                    "CODIGO": str(r.get("codigo") or "").strip().upper(),
                    "DESCRIPCION": str(r.get("descripcion") or "").strip().upper(),
                    "UBICACION": str(r.get("ubicacion") or "").strip().upper(),
                    "CANTIDAD": float(r.get("cantidad") or 0),
                    "TIPO_COMPROBANTE": str(r.get("tipo_comprobante") or "").strip().upper(),
                    "NUMERO_ORDEN": str(r.get("numero_orden") or "").strip(),
                    "MAQUINA_SITIO": str(r.get("maquina_sitio") or "").strip().upper(),
                    "PRECIO_UNITARIO": float(r.get("precio_unitario") or 0),
                    "MONTO_TOTAL_SALIDA": float(r.get("monto_total") or 0),
                    "OPERARIO": str(r.get("operario_nombre") or "").strip().upper(),
                    "SECTOR": str(r.get("sector_nombre") or "").strip().upper(),
                }
                # PAÑ normalization
                if rec["TIPO_COMPROBANTE"] in ("PAÑ", "PAN", "PANOL"):
                    rec["TIPO_COMPROBANTE"] = "PAÑOL"
                records.append(rec)
            df = pd.DataFrame(records, columns=COLUMNAS + ["_fecha"])
            # ensure _fecha is datetime64
            df["_fecha"] = pd.to_datetime(df["FECHA"], errors="coerce")
            # Ensure numeric
            for col in ("CANTIDAD", "PRECIO_UNITARIO", "MONTO_TOTAL_SALIDA"):
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
            return df
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _file_mtime(path: Path) -> float | None:
    """Return mtime of file or None if not exists / not accessible.

    Lazy helper to detect Drive changes without breaking the service.
    """
    try:
        return path.stat().st_mtime
    except (OSError, FileNotFoundError):
        return None


class RedNoDisponibleError(Exception):
    pass


class CargandoDatosError(Exception):
    pass


def _norm_header(name: object) -> str:
    s = str(name or "").strip().upper().replace(" ", "_")
    # Frequent variants
    alias = {
        "ANO": "AÑO",
        "ANIO": "AÑO",
        "A¿O": "AÑO",
        "PRECIO": "PRECIO_UNITARIO",
        "COSTO_UNITARIO": "PRECIO_UNITARIO",
        "MONTO": "MONTO_TOTAL_SALIDA",
        "MONTO_TOTAL": "MONTO_TOTAL_SALIDA",
        "TOTAL": "MONTO_TOTAL_SALIDA",
        "ORDEN": "NUMERO_ORDEN",
        "NRO_ORDEN": "NUMERO_ORDEN",
        "NUM_ORDEN": "NUMERO_ORDEN",
        "COMPROBANTE": "TIPO_COMPROBANTE",
        "TIPO": "TIPO_COMPROBANTE",
        "MAQUINA": "MAQUINA_SITIO",
        "SITIO": "MAQUINA_SITIO",
        "UBICACIÓN": "UBICACION",
        "DESCRIPCIÓN": "DESCRIPCION",
    }
    return alias.get(s, s)


def _mapear_columnas(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=COLUMNAS)
    ren = {c: _norm_header(c) for c in df.columns}
    out = df.rename(columns=ren)
    # If duplicate columns after alias, keep first
    out = out.loc[:, ~out.columns.duplicated()]
    for col in COLUMNAS:
        if col not in out.columns:
            out[col] = ""
    return out[COLUMNAS].copy()


def _parse_fecha(val: object) -> pd.Timestamp | pd.NaT:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return pd.NaT
    if isinstance(val, datetime):
        return pd.Timestamp(val).normalize()
    if isinstance(val, pd.Timestamp):
        return val.normalize()
    # Excel serial
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        try:
            if 20000 < float(val) < 60000:
                return pd.to_datetime(float(val), unit="D", origin="1899-12-30").normalize()
        except (ValueError, OverflowError, OSError):
            pass
    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", "nat"):
        return pd.NaT
    # ISO first (sample CSV); then dayfirst (DD/MM/YYYY typical AR)
    ts = pd.to_datetime(s, errors="coerce", format="%Y-%m-%d")
    if not pd.isna(ts):
        return ts.normalize()
    ts = pd.to_datetime(s, errors="coerce", dayfirst=True)
    if not pd.isna(ts):
        return ts.normalize()
    ts = pd.to_datetime(s, errors="coerce", dayfirst=False)
    if not pd.isna(ts):
        return ts.normalize()
    return pd.NaT


def _normalizar_df(df: pd.DataFrame) -> pd.DataFrame:
    df = _mapear_columnas(df)
    if df.empty:
        return df

    fechas = df["FECHA"].map(_parse_fecha)
    df["_fecha"] = fechas
    # MES / AÑO as text; fill from FECHA if missing
    df["MES"] = df["MES"].map(lambda v: "" if pd.isna(v) else str(v).strip())
    df["AÑO"] = df["AÑO"].map(lambda v: "" if pd.isna(v) else str(v).strip())
    mes_num = fechas.dt.month
    anio_num = fechas.dt.year
    vacio_mes = df["MES"].isin(("", "nan", "None", "NaT", "0", "0.0"))
    vacio_anio = df["AÑO"].isin(("", "nan", "None", "NaT", "0", "0.0"))
    df.loc[vacio_mes, "MES"] = (
        mes_num.loc[vacio_mes].fillna(0).astype(int).astype(str).replace({"0": ""})
    )
    df.loc[vacio_anio, "AÑO"] = (
        anio_num.loc[vacio_anio].fillna(0).astype(int).astype(str).replace({"0": ""})
    )
    # Strip .0 from numeric CSV reads
    df["MES"] = df["MES"].str.replace(r"\.0$", "", regex=True)
    df["AÑO"] = df["AÑO"].str.replace(r"\.0$", "", regex=True)
    # Human-readable ISO date
    df["FECHA"] = fechas.dt.strftime("%Y-%m-%d").fillna("")

    for col in ("CANTIDAD", "PRECIO_UNITARIO", "MONTO_TOTAL_SALIDA"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    for col in (
        "CODIGO",
        "DESCRIPCION",
        "UBICACION",
        "TIPO_COMPROBANTE",
        "NUMERO_ORDEN",
        "MAQUINA_SITIO",
        "OPERARIO",
        "SECTOR",
    ):
        df[col] = (
            df[col]
            .astype(str)
            .str.strip()
            .replace({"nan": "", "None": "", "NaT": ""})
        )

    df["SECTOR"] = df["SECTOR"].str.upper()
    df["TIPO_COMPROBANTE"] = df["TIPO_COMPROBANTE"].str.upper()
    # PAÑ / PAÑOL → PAÑOL (same logic as desktop)
    df.loc[df["TIPO_COMPROBANTE"].isin(("PAÑ", "PAÑOL", "PAN", "PANOL")), "TIPO_COMPROBANTE"] = "PAÑOL"

    return df.reset_index(drop=True)


def _leer_excel(path: Path) -> pd.DataFrame:
    """Read XLSX; prefer sheet Movimientos (same contract as Salidas)."""
    xls = pd.ExcelFile(path, engine="openpyxl")
    sheet: str | int = (
        HOJA_MOVIMIENTOS if HOJA_MOVIMIENTOS in xls.sheet_names else 0
    )
    return pd.read_excel(xls, sheet_name=sheet)


def _leer_excel_bytes(data: bytes) -> pd.DataFrame:
    """Read XLSX from in-memory bytes; prefer sheet Movimientos."""
    xls = pd.ExcelFile(io.BytesIO(data), engine="openpyxl")
    sheet: str | int = (
        HOJA_MOVIMIENTOS if HOJA_MOVIMIENTOS in xls.sheet_names else 0
    )
    return pd.read_excel(xls, sheet_name=sheet)


def _leer_master_drive() -> pd.DataFrame:
    """Download master from Google Drive into memory and normalize it."""
    raw = _leer_excel_bytes(drive_source.download_bytes())
    return _normalizar_df(raw)


def _leer_archivo(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"No se encontró archivo de movimientos: {path}. "
            "Configure REPORTES_MOVIMIENTOS_FILE, REPORTES_DATA_PATH, "
            "o verifique el master_salidas de producción (mismo path que KPIs)."
        )
    suffix = path.suffix.lower()
    if suffix == ".csv":
        # utf-8-sig for Excel export; fallback latin-1
        try:
            raw = pd.read_csv(path, encoding="utf-8-sig")
        except UnicodeDecodeError:
            raw = pd.read_csv(path, encoding="latin-1")
    elif suffix in (".xlsx", ".xls"):
        raw = _leer_excel(path)
    else:
        raise ValueError(f"Formato no soportado ({suffix}). Use .csv o .xlsx.")
    return _normalizar_df(raw)


# ── Live merge helpers (in-memory only, never writes to disk) ─────────────

def _diarios_base_dirs() -> list[Path]:
    """Directories where daily files salidas_*.xlsx may live.

    Covers:
    - Production base (G:\\...\\pañol v5.0) and its salidas_diaria subfolder
    - Parent of the resolved master file (handles REPORTES_MOVIMIENTOS_FILE overrides)
    Deduplicated, order-preserving.
    """
    dirs: list[Path] = []
    # 1) Production base (authoritative, same as KPIs)
    try:
        if DEFAULT_PROD_BASE not in dirs:
            dirs.append(DEFAULT_PROD_BASE)
        sd = DEFAULT_PROD_BASE / "salidas_diaria"
        if sd not in dirs:
            dirs.append(sd)
    except Exception:
        pass
    # 2) Also cover master parent (env overrides / tests)
    try:
        mp = movimientos_path()
        parent = mp.parent
        for d in (parent, parent / "salidas_diaria"):
            if d not in dirs:
                dirs.append(d)
    except Exception:
        pass
    # Deduplicate case-insensitive (Windows)
    seen: set[str] = set()
    uniq: list[Path] = []
    for d in dirs:
        key = str(d).lower()
        if key not in seen:
            seen.add(key)
            uniq.append(d)
    return uniq


def _collect_diarios_paths() -> list[Path]:
    """Collect unique daily file paths salidas_*.xlsx from known dirs.

    Deduplicates by filename (case-insensitive), keeping the larger/newer
    file when a duplicate exists in both base and salidas_diaria.
    """
    paths: list[Path] = []
    seen_names: set[str] = set()
    for folder in _diarios_base_dirs():
        if not folder.is_dir():
            continue
        try:
            candidates = sorted(folder.glob("salidas_*.xlsx"))
        except Exception:
            continue
        for p in candidates:
            # Skip master itself if pattern ever matched (defensive)
            if p.name.lower() == "master_salidas.xlsx":
                continue
            name_low = p.name.lower()
            if name_low in seen_names:
                existing = next((x for x in paths if x.name.lower() == name_low), None)
                if existing is None:
                    continue
                try:
                    cur_size = p.stat().st_size
                    cur_mtime = p.stat().st_mtime
                    ex_size = existing.stat().st_size
                    ex_mtime = existing.stat().st_mtime
                    if cur_size > ex_size or (cur_size == ex_size and cur_mtime > ex_mtime):
                        paths.remove(existing)
                        paths.append(p)
                except OSError:
                    continue
                continue
            seen_names.add(name_low)
            paths.append(p)
    return sorted(paths, key=lambda p: p.name.lower())


def _diarios_max_mtime(paths: list[Path] | None = None) -> float | None:
    """Max mtime among daily files, or None if none exist / accessible."""
    if paths is None:
        paths = _collect_diarios_paths()
    best: float | None = None
    for p in paths:
        m = _file_mtime(p)
        if m is not None and (best is None or m > best):
            best = m
    return best


def _parse_diario_fecha(path: Path) -> pd.Timestamp | None:
    """Extract date from filename salidas_DD-MM-YYYY.xlsx."""
    import re

    m = re.search(r"(\d{1,2})-(\d{1,2})-(\d{4})", path.name)
    if not m:
        return None
    try:
        d, mo, y = map(int, m.groups())
        return pd.Timestamp(datetime(y, mo, d)).normalize()
    except Exception:
        return None


def _row_key(row: pd.Series) -> tuple[str, str, float, str]:
    """Dedupe key: NUMERO_ORDEN + CODIGO + CANTIDAD + FECHA.

    - NUMERO_ORDEN/CODIGO upper+stripped
    - CANTIDAD as float rounded to 4 decimals (1 vs 1.0)
    - FECHA as ISO YYYY-MM-DD string (already normalized)
    Matches rebuild_master_salidas intent without writing to disk.
    """
    num = str(row.get("NUMERO_ORDEN") or "").strip().upper()
    cod = str(row.get("CODIGO") or "").strip().upper()
    try:
        cant = float(row.get("CANTIDAD") or 0)
        cant = round(cant, 4)
        if cant == 0:
            cant = 0.0
    except Exception:
        cant = 0.0
    fecha = str(row.get("FECHA") or "").strip()
    return (num, cod, cant, fecha)


def _leer_diarios_pendientes(df_master: pd.DataFrame) -> pd.DataFrame:
    """Read daily files and return only rows not yet in master (in-memory).

    - Lists G:\\...\\salidas_*.xlsx and G:\\...\\salidas_diaria\\salidas_*.xlsx
    - Reads each with pandas/openpyxl, normalizes via _normalizar_df()
    - Filters to rows whose key (NUMERO_ORDEN+CODIGO+CANTIDAD+FECHA) is not in master
    - Deduplicates among pending files themselves (idempotent)
    - Never writes to disk; returns empty DataFrame if no pending rows.
    - Optimization: only reads diarios with date >= last master date (minus 7-day lookback)
      or with mtime recent (within 7 days of master mtime), to keep refresh fast
      without reading 140+ old files already consolidated.
    """
    # Build master key set
    master_keys: set[tuple[str, str, float, str]] = set()
    if df_master is not None and not df_master.empty:
        for _, r in df_master.iterrows():
            # Skip entirely empty placeholder rows
            if not str(r.get("NUMERO_ORDEN") or "").strip() and not str(r.get("CODIGO") or "").strip():
                continue
            master_keys.add(_row_key(r))

    pending_frames: list[pd.DataFrame] = []
    seen_pending: set[tuple[str, str, float, str]] = set()

    paths = _collect_diarios_paths()
    if not paths:
        # No daily files found -> no pending
        if df_master is not None and not df_master.empty:
            return pd.DataFrame(columns=df_master.columns)
        return pd.DataFrame(columns=COLUMNAS + ["_fecha"])

    # ── Fast-path filter: avoid reading 140+ old files already in master ──
    # Only consider diarios whose filename date is recent or whose mtime is recent.
    # Fallback to reading all if master has no valid max date.
    try:
        if df_master is not None and not df_master.empty and "_fecha" in df_master.columns:
            max_fecha = df_master["_fecha"].max()
        else:
            max_fecha = pd.NaT
    except Exception:
        max_fecha = pd.NaT

    filtered_paths: list[Path]
    if pd.isna(max_fecha):
        filtered_paths = paths
    else:
        try:
            max_ts = pd.Timestamp(max_fecha).normalize()
            threshold = max_ts - pd.Timedelta(days=7)
        except Exception:
            threshold = pd.Timestamp("2020-01-01")
        try:
            master_path = movimientos_path()
            master_mtime = _file_mtime(master_path)
        except Exception:
            master_mtime = None
        # 7-day window for mtime fallback
        mtime_cutoff = (master_mtime - 7 * 86400) if master_mtime is not None else None
        filtered_paths = []
        for p in paths:
            ts = _parse_diario_fecha(p)
            if ts is not None and ts >= threshold:
                filtered_paths.append(p)
                continue
            # Fallback: if date older but file was modified recently (new daily not yet consolidated)
            if mtime_cutoff is not None:
                m = _file_mtime(p)
                if m is not None and m > mtime_cutoff:
                    filtered_paths.append(p)
                    continue
            # Also handle files with unparseable dates (keep them)
            if ts is None:
                filtered_paths.append(p)
        # If filter was too aggressive and left 0 candidates, keep at least files with mtime in last 30 days
        if not filtered_paths:
            # No recent files by date; try mtime last 30 days as safety net
            now = datetime.now(timezone.utc).timestamp()
            for p in paths:
                m = _file_mtime(p)
                if m is not None and m > now - 30 * 86400:
                    filtered_paths.append(p)
            # If still none, no pending anyway
            if not filtered_paths:
                if df_master is not None and not df_master.empty:
                    return pd.DataFrame(columns=df_master.columns)
                return pd.DataFrame(columns=COLUMNAS + ["_fecha"])
        paths = filtered_paths

    for p in paths:
        try:
            # Skip tiny/empty files quickly
            try:
                if p.stat().st_size < 100:
                    continue
            except OSError:
                continue
            # Read excel (same sheet logic as master)
            try:
                raw = _leer_excel(p)
            except Exception as e:
                log.debug("Reportes: skip diario %s (read error: %s)", p.name, e)
                continue
            if raw is None or raw.empty:
                continue
            df_norm = _normalizar_df(raw)
            if df_norm.empty:
                continue
            # Filter rows not in master and not already seen in pending
            # Vectorized approach would be faster, but row-wise is clearer and fine for ~40 rows/file
            to_keep: list[bool] = []
            for _, r in df_norm.iterrows():
                key = _row_key(r)
                # Rows without FECHA (empty) are invalid -> skip
                if not key[3]:
                    to_keep.append(False)
                    continue
                if key in master_keys or key in seen_pending:
                    to_keep.append(False)
                else:
                    to_keep.append(True)
                    seen_pending.add(key)
            if any(to_keep):
                filtered = df_norm.loc[to_keep].copy()
                pending_frames.append(filtered)
        except Exception as e:
            log.debug("Reportes: error processing diario %s: %s", p.name, e)
            continue

    if not pending_frames:
        if df_master is not None and not df_master.empty:
            return pd.DataFrame(columns=df_master.columns)
        return pd.DataFrame(columns=COLUMNAS + ["_fecha"])

    combined = pd.concat(pending_frames, ignore_index=True)
    return combined.reset_index(drop=True)


class ReportesStore:
    # RLock to allow _ensure_fresh() to call refresh() without deadlock
    # (refresh already holds the lock; the lazy check also needs it).
    _lock = threading.RLock()
    _instance: ReportesStore | None = None

    def __init__(self) -> None:
        self.ultima_actualizacion: datetime | None = None
        self._cargando = False
        self._error_carga: str | None = None
        self.df: pd.DataFrame = pd.DataFrame(columns=COLUMNAS + ["_fecha"])
        self.archivo_ok = False
        self.path_usado: str = ""
        self._last_mtime: float | None = None
        self._last_diarios_mtime: float | None = None
        # Drive freshness token (modifiedTime|md5Checksum) when Drive mode is on
        self._last_drive_etag: str | None = None

    @classmethod
    def get(cls) -> ReportesStore:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = ReportesStore()
        return cls._instance

    def timestamp_iso(self) -> str:
        if self.ultima_actualizacion is None:
            return ""
        return self.ultima_actualizacion.astimezone().isoformat()

    def registrar_error_carga(self, mensaje: str) -> None:
        self._error_carga = mensaje
        self._cargando = False

    def _ensure_fresh(self) -> None:
        """Lazy mtime check: auto-reload if master or any daily changed.
        En modo DB (REPORTES_DB_ENABLED=1) verifica COUNT en salida_historial
        para detectar inserciones (bulk o live) sin depender de mtimes.

        Runs on each request (require_loaded / ensure_loaded) and also from
        the 60s poll loop in main.py.
        - Only if a successful load already happened (ultima_actualizacion is not None).
        - Compares mtime of master and max mtime of diarios vs cached values (1s tolerance for Drive/SMB).
        - If either changed, calls refresh() automatically.
        - If refresh fails, logs and keeps serving old data (does not bring down service).
        - Thread-safe: uses RLock to read/compare without races.
        """
        if self.ultima_actualizacion is None:
            return
        if self._cargando:
            return
        # ── DB mode: poll COUNT to detect new rows (no mtime/Drive needed) ──
        if _db_enabled():
            try:
                import pymysql

                conn = pymysql.connect(
                    host=REPORTES_DB_HOST,
                    port=int(REPORTES_DB_PORT),
                    user=REPORTES_DB_USER,
                    password=REPORTES_DB_PASSWORD,
                    database=REPORTES_DB_NAME,
                    charset="utf8mb4",
                    cursorclass=pymysql.cursors.DictCursor,
                )
                try:
                    with conn.cursor() as cur:
                        cur.execute("SELECT COUNT(*) AS c FROM salida_historial WHERE COALESCE(anulado,0)=0")
                        row = cur.fetchone()
                        cnt = int(row["c"] if row and "c" in row else 0)
                        if cnt != int(len(self.df)):
                            log.info("Reportes: DB count changed %d -> %d, recargando desde DB...", len(self.df), cnt)
                            # snapshot old for rollback on error
                            snapshot_df = self.df.copy()
                            snapshot_ok = self.archivo_ok
                            snapshot_path = self.path_usado
                            snapshot_ts = self.ultima_actualizacion
                            snapshot_err = self._error_carga
                            try:
                                self.refresh()
                            except Exception as e:
                                with self._lock:
                                    self.df = snapshot_df
                                    self.archivo_ok = snapshot_ok
                                    self.path_usado = snapshot_path
                                    self.ultima_actualizacion = snapshot_ts
                                    self._error_carga = snapshot_err
                                    self._cargando = False
                                log.warning("Reportes: auto-refresh DB falló, se siguen sirviendo datos viejos: %s", e)
                finally:
                    try:
                        conn.close()
                    except Exception:
                        pass
            except Exception as e:
                log.debug("Reportes: check DB freshness ignorado: %s", e)
            return
        try:
            path = movimientos_path()
            use_drive = drive_source.is_enabled()
            if use_drive:
                # Drive freshness: modifiedTime/md5Checksum instead of file mtime
                etag = drive_source.get_modified_etag()
                if etag is None:
                    return
                if self._last_drive_etag is None:
                    with self._lock:
                        if self._last_drive_etag is None:
                            self._last_drive_etag = etag
                    # Also init diarios mtime tracking without triggering reload
                    try:
                        with self._lock:
                            if self._last_diarios_mtime is None:
                                self._last_diarios_mtime = _diarios_max_mtime()
                    except Exception:
                        pass
                    return
                master_changed = etag != self._last_drive_etag
                actual = None
            else:
                actual = _file_mtime(path)
                if actual is None:
                    return
                # First time mtime registration (e.g. old initial load without _last_mtime)
                if self._last_mtime is None:
                    with self._lock:
                        if self._last_mtime is None:
                            self._last_mtime = actual
                    # Also init diarios mtime tracking without triggering reload
                    try:
                        with self._lock:
                            if self._last_diarios_mtime is None:
                                self._last_diarios_mtime = _diarios_max_mtime()
                    except Exception:
                        pass
                    return
                master_changed = actual > self._last_mtime + 1.0

            # Check diarios max mtime as well
            try:
                actual_diarios = _diarios_max_mtime()
            except Exception as e:
                log.debug("Reportes: diarios mtime check ignored: %s", e)
                actual_diarios = None

            last_diarios = self._last_diarios_mtime
            # If this is the first time we track diarios, init without triggering reload
            # (refresh already merged pending at startup)
            if actual_diarios is not None and last_diarios is None:
                with self._lock:
                    if self._last_diarios_mtime is None:
                        self._last_diarios_mtime = actual_diarios
                # Do not treat as change on first observation
                diarios_changed = False
            elif actual_diarios is not None and last_diarios is not None:
                diarios_changed = actual_diarios > last_diarios + 1.0
            else:
                diarios_changed = False

            if master_changed or diarios_changed:
                reason = []
                if master_changed:
                    if use_drive:
                        reason.append("drive etag changed")
                    else:
                        reason.append(f"master mtime {self._last_mtime:.0f} -> {actual:.0f}")
                if diarios_changed:
                    reason.append(f"diarios mtime {last_diarios:.0f} -> {actual_diarios:.0f}")  # type: ignore
                log.info(
                    "Reportes: detectado cambio (%s), recargando... path=%s",
                    ", ".join(reason),
                    path,
                )
                # Snapshot to keep serving old data if refresh fails
                # (refresh() sets _error_carga and archivo_ok=False on error;
                # for auto-refresh we want to keep serving old data).
                snapshot_df = self.df.copy()
                snapshot_ok = self.archivo_ok
                snapshot_path = self.path_usado
                snapshot_ts = self.ultima_actualizacion
                snapshot_mtime = self._last_mtime
                snapshot_diarios_mtime = self._last_diarios_mtime
                snapshot_drive_etag = self._last_drive_etag
                snapshot_err = self._error_carga
                try:
                    self.refresh()
                except Exception as e:
                    # Restore previous state: keep serving old data
                    with self._lock:
                        self.df = snapshot_df
                        self.archivo_ok = snapshot_ok
                        self.path_usado = snapshot_path
                        self.ultima_actualizacion = snapshot_ts
                        self._last_mtime = snapshot_mtime
                        self._last_diarios_mtime = snapshot_diarios_mtime
                        self._last_drive_etag = snapshot_drive_etag
                        self._error_carga = snapshot_err
                        self._cargando = False
                    log.warning(
                        "Reportes: auto-refresh falló, se siguen sirviendo datos viejos: %s",
                        e,
                    )
        except Exception as e:
            # Best-effort check: never break request due to mtime error
            log.debug("Reportes: check mtime ignorado: %s", e)

    def require_loaded(self) -> None:
        # Lazy refresh attempt before validating state
        try:
            self._ensure_fresh()
        except Exception:
            # _ensure_fresh already logs; do not block request
            pass
        if self._error_carga:
            raise RedNoDisponibleError(self._error_carga)
        if self.ultima_actualizacion is None:
            raise CargandoDatosError(
                "Datos de reportes aún cargando. Reintente en unos segundos."
            )

    def ensure_loaded(self) -> None:
        self.require_loaded()

    def refresh(self) -> datetime:
        with self._lock:
            self._cargando = True
            self._error_carga = None
            # ── Intento DB primero si flag activo ──
            if _db_enabled():
                try:
                    df_db = _cargar_df_desde_db()
                    # Si DB tiene datos, usar DB (aunque sea 0? fallback a Excel si vacía)
                    if df_db is not None and not df_db.empty:
                        self.df = df_db
                        self.archivo_ok = True
                        self.path_usado = f"db:{REPORTES_DB_NAME}.salida_historial"
                        # reset mtimes para no confundir fallback
                        self._last_mtime = None
                        self._last_diarios_mtime = None
                        self._last_drive_etag = None
                        self.ultima_actualizacion = datetime.now(timezone.utc)
                        log.info("Reportes: cargado desde DB salida_historial (%d filas) [REPORTES_DB_ENABLED=1]", len(df_db))
                        return self.ultima_actualizacion
                    else:
                        log.info("Reportes: DB vacía o sin filas activas (%s), fallback a Excel", len(df_db) if df_db is not None else "None")
                except Exception as e:
                    log.warning("Reportes: DB load falló, fallback a Excel: %s", e)
                    # no raise, continúa a Excel
            path = movimientos_path()
            use_drive = drive_source.is_enabled()
            try:
                if use_drive:
                    df_master = _leer_master_drive()
                else:
                    df_master = _leer_archivo(path)
                master_len = len(df_master)
                # In-memory merge of pending daily files (never writes to disk)
                try:
                    df_pending = _leer_diarios_pendientes(df_master)
                except Exception as e:
                    log.warning(
                        "Reportes: error leyendo diarios pendientes (se ignora, solo master): %s",
                        e,
                    )
                    df_pending = pd.DataFrame(columns=df_master.columns)

                if not df_pending.empty:
                    # Concatenate master + pending (idempotent due to dedupe)
                    combined = pd.concat([df_master, df_pending], ignore_index=True)
                    self.df = combined
                    log.info(
                        "Reportes: merge en memoria master=%d + diarios_pendientes=%d -> total=%d (sin tocar disco)",
                        master_len,
                        len(df_pending),
                        len(combined),
                    )
                else:
                    self.df = df_master
                    log.info("Reportes: sin diarios pendientes, master=%d filas", master_len)

                self.archivo_ok = True
                if use_drive:
                    self.path_usado = "drive:master_salidas.xlsx"
                    self._last_drive_etag = drive_source.get_modified_etag()
                else:
                    self.path_usado = str(path)
                    self._last_mtime = _file_mtime(path)
                try:
                    self._last_diarios_mtime = _diarios_max_mtime()
                except Exception:
                    self._last_diarios_mtime = None
                self.ultima_actualizacion = datetime.now(timezone.utc)
                return self.ultima_actualizacion
            except Exception as e:
                self.archivo_ok = False
                self.path_usado = str(path)
                self._error_carga = str(e)
                raise
            finally:
                self._cargando = False

    def meta(self) -> dict[str, Any]:
        base = {
            "archivo_ok": self.archivo_ok,
            "path": self.path_usado or str(movimientos_path()),
            "filas": int(len(self.df)),
            "ultima_actualizacion": self.timestamp_iso(),
            "error": self._error_carga,
            "db_enabled": bool(_db_enabled()),
            "fuente": "db" if str(self.path_usado).startswith("db:") else ("drive" if str(self.path_usado).startswith("drive:") else "excel"),
        }
        # compat keys for older frontends
        return base
