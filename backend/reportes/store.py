# -*- coding: utf-8 -*-
"""Read-only loader for movimientos desde MariaDB (salida_historial).

DB es la única fuente de datos. No lee Excel, Drive ni G:\.
Si DB no tiene datos o falla, se levanta excepción (sin fallback).
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from config import COLUMNAS, REPORTES_DB_ENABLED, REPORTES_DB_HOST, REPORTES_DB_NAME, REPORTES_DB_PASSWORD, REPORTES_DB_PORT, REPORTES_DB_USER


log = logging.getLogger("reportes.store")


# ── DB helpers ────────────────────────────────────────────────────

def _db_enabled() -> bool:
    try:
        return bool(REPORTES_DB_ENABLED)
    except Exception:
        return False


def _cargar_df_desde_db() -> pd.DataFrame:
    """Carga DataFrame desde salida_historial (solo filas activas).

    Mapea columnas snake_case DB -> COLUMNAS reportes (UPPER).
    Retorna DataFrame con COLUMNAS + _fecha, o DataFrame vacío si no hay filas.
    Lanza excepción si DB no disponible.
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
            # Real load - all active rows
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
                if not mes or mes.lower() in ("none", "nan", "0") and not pd.isna(fecha_ts):
                    try:
                        m = int(pd.Timestamp(fecha_ts).month)
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
                if rec["TIPO_COMPROBANTE"] in ("PAÑ", "PAN", "PANOL"):
                    rec["TIPO_COMPROBANTE"] = "PAÑOL"
                records.append(rec)
            df = pd.DataFrame(records, columns=COLUMNAS + ["_fecha"])
            df["_fecha"] = pd.to_datetime(df["FECHA"], errors="coerce")
            for col in ("CANTIDAD", "PRECIO_UNITARIO", "MONTO_TOTAL_SALIDA"):
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
            return df
    finally:
        try:
            conn.close()
        except Exception:
            pass


class RedNoDisponibleError(Exception):
    pass


class CargandoDatosError(Exception):
    pass


# ── Helpers ───────────────────────────────────────────────────────

def _norm_header(name: object) -> str:
    s = str(name or "").strip().upper().replace(" ", "_")
    alias = {
        "ANO": "AÑO", "ANIO": "AÑO", "A¿O": "AÑO",
        "PRECIO": "PRECIO_UNITARIO", "COSTO_UNITARIO": "PRECIO_UNITARIO",
        "MONTO": "MONTO_TOTAL_SALIDA", "MONTO_TOTAL": "MONTO_TOTAL_SALIDA",
        "TOTAL": "MONTO_TOTAL_SALIDA",
        "ORDEN": "NUMERO_ORDEN", "NRO_ORDEN": "NUMERO_ORDEN", "NUM_ORDEN": "NUMERO_ORDEN",
        "COMPROBANTE": "TIPO_COMPROBANTE", "TIPO": "TIPO_COMPROBANTE",
        "MAQUINA": "MAQUINA_SITIO", "SITIO": "MAQUINA_SITIO",
        "UBICACIÓN": "UBICACION", "DESCRIPCIÓN": "DESCRIPCION",
    }
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


# ── ReportesStore ─────────────────────────────────────────────────

class ReportesStore:
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
        """Lazy mtime check: auto-reload si DB cambió (COUNT diferente).
        En modo DB (_db_enabled), verifica COUNT en salida_historial
        para detectar inserciones sin depender de mtimes ni Drive.
        """
        if self.ultima_actualizacion is None:
            return
        if self._cargando:
            return
        # ── DB mode: poll COUNT to detect new rows ──
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
                            snapshot_df = self.df.copy()
                            snapshot_ok = self.archivo_ok
                            snapshot_path = self.path_usado
                            snapshot_ts = self.ultima_actualizacion
                            snapshot_err = self._error_carga
                            snapshot_mtime = self._last_mtime
                            snapshot_diarios_mtime = self._last_diarios_mtime
                            try:
                                self.refresh()
                            except Exception as e:
                                with self._lock:
                                    self.df = snapshot_df
                                    self.archivo_ok = snapshot_ok
                                    self.path_usado = snapshot_path
                                    self.ultima_actualizacion = snapshot_ts
                                    self._error_carga = snapshot_err
                                    self._last_mtime = snapshot_mtime
                                    self._last_diarios_mtime = snapshot_diarios_mtime
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
        # Si no hay DB habilitada, no hacemos nada (sin fallback a Excel)

    def require_loaded(self) -> None:
        try:
            self._ensure_fresh()
        except Exception:
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
            # ── Solo DB: sin fallback a Excel ──
            if _db_enabled():
                try:
                    df_db = _cargar_df_desde_db()
                    if df_db is not None and not df_db.empty:
                        self.df = df_db
                        self.archivo_ok = True
                        self.path_usado = f"db:{REPORTES_DB_NAME}.salida_historial"
                        self._last_mtime = None
                        self._last_diarios_mtime = None
                        self.ultima_actualizacion = datetime.now(timezone.utc)
                        log.info("Reportes: cargado desde DB salida_historial (%d filas) [DB-ONLY]", len(df_db))
                        return self.ultima_actualizacion
                    else:
                        msg = "Reportes: DB vacía o sin filas activas — sin fallback a Excel"
                        self._error_carga = msg
                        self.registrar_error_carga(msg)
                        raise RedNoDisponibleError(msg)
                except RedNoDisponibleError:
                    raise
                except Exception as e:
                    msg = f"Reportes: DB load falló — sin fallback a Excel: {e}"
                    self._error_carga = msg
                    self.registrar_error_carga(msg)
                    raise RedNoDisponibleError(msg)
            # Si DB no habilitada, error
            msg = "Reportes: REPORTES_DB_ENABLED no activo — DB es la única fuente"
            self._error_carga = msg
            self.registrar_error_carga(msg)
            raise RedNoDisponibleError(msg)

    def meta(self) -> dict[str, Any]:
        base = {
            "archivo_ok": self.archivo_ok,
            "path": self.path_usado or "db:panol.salida_historial",
            "filas": int(len(self.df)),
            "ultima_actualizacion": self.timestamp_iso(),
            "error": self._error_carga,
            "db_enabled": bool(_db_enabled()),
            "fuente": "db",
        }
        return base
