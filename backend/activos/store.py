# -*- coding: utf-8 -*-
"""Carga read-only de salida_activos.xlsx (hojas FUERA / INGRESADO)."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from config import SHEET_FUERA, SHEET_INGRESADOS, excel_path
from db import ACTIVOS_DB_ENABLED, get_connection


class RedNoDisponibleError(Exception):
    pass


class CargandoDatosError(Exception):
    pass


def _resolver_hoja(xls: pd.ExcelFile, nombre: str) -> str | None:
    target = nombre.strip().upper()
    for s in xls.sheet_names:
        if str(s).strip().upper() == target:
            return s
    return None


def _mapear_columnas(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    alias = {
        "NUMERO PEDIDO": "NUMERO_PEDIDO",
        "NUMERO OC": "NUMERO_OC",
        "NUMERO REMITO": "NUMERO_REMITO",
        "EQUIPO REPUESTO": "EQUIPO_REPUESTO",
        "NRO SERIE": "NRO_SERIE",
        "FECHA SALIDA": "FECHA_SALIDA",
        "FECHA REGRESO": "FECHA_REGRESO",
        "ESTADO AL INGRESO": "ESTADO_AL_INGRESO",
        "DIAS FUERA": "DIAS_FUERA",
    }
    ren: dict[str, str] = {}
    for c in df.columns:
        key = str(c).strip().upper()
        ren[c] = alias.get(key, key.replace(" ", "_"))
    return df.rename(columns=ren)


def _normalizar_df(df: pd.DataFrame, *, fuera: bool) -> pd.DataFrame:
    df = _mapear_columnas(df)
    if df.empty:
        df["_fuera"] = pd.Series(dtype=bool)
        return df
    if "DIAS_FUERA" in df.columns:
        df["DIAS_FUERA"] = pd.to_numeric(df["DIAS_FUERA"], errors="coerce").fillna(0)
    else:
        df["DIAS_FUERA"] = 0
    if "SECTOR" in df.columns:
        df["SECTOR"] = df["SECTOR"].astype(str).str.strip().str.upper()
    df["_fuera"] = bool(fuera)
    return df


class ActivosStore:
    _lock = threading.Lock()
    _instance: ActivosStore | None = None

    def __init__(self) -> None:
        self.ultima_actualizacion: datetime | None = None
        self._cargando = False
        self._error_carga: str | None = None
        self.df: pd.DataFrame = pd.DataFrame()
        self.archivo_ok = False

    @classmethod
    def get(cls) -> ActivosStore:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = ActivosStore()
        return cls._instance

    def timestamp_iso(self) -> str:
        if self.ultima_actualizacion is None:
            return ""
        return self.ultima_actualizacion.astimezone().isoformat()

    def registrar_error_carga(self, mensaje: str) -> None:
        self._error_carga = mensaje
        self._cargando = False

    def require_loaded(self) -> None:
        if self._error_carga:
            raise RedNoDisponibleError(self._error_carga)
        if self.ultima_actualizacion is None:
            raise CargandoDatosError(
                "Los datos de activos se están cargando. Espere un momento e intente de nuevo."
            )

    def ensure_loaded(self) -> None:
        if self.ultima_actualizacion is not None:
            return
        if self._cargando:
            raise CargandoDatosError(
                "Los datos de activos se están cargando. Espere un momento e intente de nuevo."
            )
        with self._lock:
            if self.ultima_actualizacion is not None:
                return
            self._cargando = True
            self._error_carga = None
            try:
                self._cargar()
            finally:
                self._cargando = False

    def refresh(self) -> datetime:
        with self._lock:
            self._cargando = True
            self._error_carga = None
            try:
                return self._cargar()
            finally:
                self._cargando = False

    def _verificar_ruta(self, path: Path) -> None:
        drive = path.drive
        if drive and not Path(drive + "\\").exists():
            raise RedNoDisponibleError("Unidad de red no disponible")
        parent = path.parent
        if not parent.exists():
            if parent.drive and not Path(parent.drive + "\\").exists():
                raise RedNoDisponibleError("Unidad de red no disponible")
            raise FileNotFoundError(f"No se encontró la carpeta de datos: {parent}")

    def _cargar_desde_db(self) -> datetime:
        """Carga desde MariaDB panol.salida_activos (DB unica fuente)."""
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, numero_pedido AS NUMERO_PEDIDO,
                           numero_oc AS NUMERO_OC,
                           numero_remito AS NUMERO_REMITO,
                           sector AS SECTOR,
                           codigo AS CODIGO,
                           equipo AS EQUIPO_REPUESTO,
                           cantidad AS CANTIDAD,
                           nro_serie AS NRO_SERIE,
                           fecha_salida AS FECHA_SALIDA,
                           proveedor AS PROVEEDOR,
                           fecha_regreso AS FECHA_REGRESO,
                           estado_al_ingreso AS ESTADO_AL_INGRESO,
                           observaciones AS OBSERVACIONES,
                           dias_fuera AS DIAS_FUERA,
                           estado AS ESTADO
                    FROM salida_activos
                    ORDER BY fecha_salida DESC, id DESC
                    """
                )
                rows = cur.fetchall()
        finally:
            try:
                conn.close()
            except Exception:
                pass

        if not rows:
            self.df = pd.DataFrame()
            self.archivo_ok = True
            self.ultima_actualizacion = datetime.now(timezone.utc)
            return self.ultima_actualizacion

        df = pd.DataFrame(rows)
        # Mapear a formato esperado por service.py
        # Renombrar y normalizar
        df["_fuera"] = df["ESTADO"].astype(str).str.strip().str.lower() == "fuera_de_planta"
        # _sheet_row ahora es el id de DB para que write_ops use id real
        df["_sheet_row"] = pd.to_numeric(df["id"], errors="coerce").fillna(-1).astype(int)
        # Asegurar DIAS_FUERA numerico
        df["DIAS_FUERA"] = pd.to_numeric(df["DIAS_FUERA"], errors="coerce").fillna(0).astype(int)
        # SECTOR ya viene normalizado pero asegurar upper
        df["SECTOR"] = df["SECTOR"].astype(str).str.strip().str.upper().replace({"NAN": "", "NONE": ""})
        # FECHA_SALIDA / FECHA_REGRESO se mantienen como date/string, service usa fmt_fecha que maneja ambos
        self.df = df.reset_index(drop=True)
        self.archivo_ok = True
        self.ultima_actualizacion = datetime.now(timezone.utc)
        return self.ultima_actualizacion

    def _cargar(self) -> datetime:
        # DB es la unica fuente desde 2026-09-23; Excel queda como backup no usado
        if ACTIVOS_DB_ENABLED:
            try:
                return self._cargar_desde_db()
            except Exception as e:
                # Si DB falla, no caer a Excel — reportar error para no ocultar regresion
                raise RedNoDisponibleError(f"No se pudo cargar activos desde DB: {e}")

        # Fallback Excel solo si DB deshabilitada explicitamente
        path = excel_path()
        self._verificar_ruta(path)
        self.archivo_ok = path.is_file()
        if not path.is_file():
            raise FileNotFoundError(f"No se encontró {path}")

        xls = pd.ExcelFile(path, engine="openpyxl")
        hoja_fuera = _resolver_hoja(xls, SHEET_FUERA) or xls.sheet_names[0]
        df_fuera = _normalizar_df(pd.read_excel(xls, sheet_name=hoja_fuera), fuera=True)
        if not df_fuera.empty:
            df_fuera = df_fuera.reset_index(drop=True)
            df_fuera["_sheet_row"] = df_fuera.index.astype(int)
        else:
            df_fuera["_sheet_row"] = pd.Series(dtype=int)

        hoja_ing = _resolver_hoja(xls, SHEET_INGRESADOS)
        if hoja_ing:
            df_ing = _normalizar_df(pd.read_excel(xls, sheet_name=hoja_ing), fuera=False)
        else:
            df_ing = _normalizar_df(pd.DataFrame(), fuera=False)
        if not df_ing.empty:
            df_ing = df_ing.reset_index(drop=True)
            df_ing["_sheet_row"] = df_ing.index.astype(int)
        else:
            df_ing["_sheet_row"] = pd.Series(dtype=int)
        xls.close()

        if df_fuera.empty and df_ing.empty:
            self.df = pd.DataFrame()
        elif df_fuera.empty:
            self.df = df_ing.reset_index(drop=True)
        elif df_ing.empty:
            self.df = df_fuera.reset_index(drop=True)
        else:
            self.df = pd.concat([df_fuera, df_ing], ignore_index=True, sort=False)

        self.ultima_actualizacion = datetime.now(timezone.utc)
        return self.ultima_actualizacion


def fmt_fecha(val: Any) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    if isinstance(val, datetime):
        return val.strftime("%d/%m/%Y")
    try:
        ts = pd.to_datetime(val, errors="coerce", dayfirst=True)
        if pd.isna(ts):
            s = str(val).strip()
            return "" if s.lower() in ("nan", "none", "nat", "") else s
        return ts.strftime("%d/%m/%Y")
    except Exception:
        s = str(val).strip()
        return "" if s.lower() in ("nan", "none", "nat", "") else s
