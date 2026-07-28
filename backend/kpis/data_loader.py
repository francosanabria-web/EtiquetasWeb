# -*- coding: utf-8 -*-
"""
Lectura SOLO LECTURA de Excel + caché en memoria.
Nunca escribe en master_codes, master_salidas ni salida_activos.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from clasificacion import (
    cargar_mapa_sectores,
    clasificar_sector,
    normalizar_criticidad,
    normalizar_linea_gasto,
)
from config import (
    MASTER_CODES,
    MASTER_SALIDAS,
    SALIDA_ACTIVOS,
    SHEET_ACTIVOS,
    SHEET_ARTICULOS,
    SHEET_CONFIG,
    SHEET_MOVIMIENTOS,
    base_path,
)


class RedNoDisponibleError(Exception):
    pass


class CargandoDatosError(Exception):
    """Excel aún en carga (arranque o refresh en curso)."""
    pass


def _resolver_hoja(xls: pd.ExcelFile, nombre: str) -> str | None:
    for s in xls.sheet_names:
        if s.strip().lower() == nombre.strip().lower():
            return s
    return None


def _col(df: pd.DataFrame, *candidatos: str) -> str | None:
    if df.empty:
        return None
    lower = {str(c).strip().lower(): c for c in df.columns}
    for cand in candidatos:
        if cand.lower() in lower:
            return lower[cand.lower()]
    return None


def _num(val: Any, default: float = 0.0) -> float:
    try:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


def _mapear_columnas_activos(df: pd.DataFrame) -> pd.DataFrame:
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


def _tiene_fecha_regreso_valida(val: object) -> bool:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return False
    s = str(val).strip().lower()
    return s not in ("", "nan", "none", "nat", "-")


def _fila_activo_pendiente(row: pd.Series) -> bool:
    est = str(row.get("ESTADO", "")).strip().upper().replace(" ", "_")
    if est == "INGRESADO_A_PLANTA":
        return False
    if est == "FUERA_DE_PLANTA":
        return True
    return not _tiene_fecha_regreso_valida(row.get("FECHA_REGRESO"))


class DataStore:
    _lock = threading.Lock()
    _instance: DataStore | None = None

    def __init__(self) -> None:
        self.ultima_actualizacion: datetime | None = None
        self._cargando = False
        self._error_carga: str | None = None
        self.articulos: pd.DataFrame = pd.DataFrame()
        self.movimientos: pd.DataFrame = pd.DataFrame()
        self.activos: pd.DataFrame = pd.DataFrame()
        self.config: pd.DataFrame = pd.DataFrame()
        self.sectores_oficiales: list[str] = []
        self.sector_operarios_map: dict[str, list[str]] = {}
        self.archivos_ok: dict[str, bool] = {}

    @classmethod
    def get(cls) -> DataStore:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = DataStore()
        return cls._instance

    def timestamp_iso(self) -> str:
        if self.ultima_actualizacion is None:
            return ""
        return self.ultima_actualizacion.astimezone().isoformat()

    def _verificar_ruta(self, base: Path) -> None:
        drive = base.drive
        if drive and not Path(drive + "\\").exists():
            raise RedNoDisponibleError("Unidad de red no disponible")
        if not base.exists():
            parent = base.parent
            if parent.drive and not Path(parent.drive + "\\").exists():
                raise RedNoDisponibleError("Unidad de red no disponible")
            raise FileNotFoundError(f"No se encontró la carpeta de datos: {base}")

    def registrar_error_carga(self, mensaje: str) -> None:
        self._error_carga = mensaje
        self._cargando = False

    def require_loaded(self) -> None:
        if self._error_carga:
            raise RedNoDisponibleError(self._error_carga)
        if self.ultima_actualizacion is None:
            raise CargandoDatosError(
                "Los datos del pañol se están cargando. Espere 1-2 minutos e intente de nuevo."
            )

    def refresh(self) -> datetime:
        with self._lock:
            self._cargando = True
            self._error_carga = None
            try:
                return self._cargar_todo()
            finally:
                self._cargando = False

    def ensure_loaded(self) -> None:
        if self.ultima_actualizacion is not None:
            return
        if self._cargando:
            raise CargandoDatosError(
                "Los datos del pañol se están cargando. Espere 1-2 minutos e intente de nuevo."
            )
        with self._lock:
            if self.ultima_actualizacion is not None:
                return
            if self._cargando:
                raise CargandoDatosError(
                    "Los datos del pañol se están cargando. Espere 1-2 minutos e intente de nuevo."
                )
            self._cargando = True
            self._error_carga = None
            try:
                self._cargar_todo()
            finally:
                self._cargando = False

    def _cargar_todo(self) -> datetime:
        base = base_path()
        self._verificar_ruta(base)
        self.archivos_ok = {}

        path_codes = base / MASTER_CODES
        path_salidas = base / MASTER_SALIDAS
        path_activos = base / SALIDA_ACTIVOS

        self.archivos_ok["master_codes"] = path_codes.is_file()
        self.archivos_ok["master_salidas"] = path_salidas.is_file()
        self.archivos_ok["salida_activos"] = path_activos.is_file()

        if not path_codes.is_file():
            raise FileNotFoundError(f"No se encontró {path_codes}")

        xls = pd.ExcelFile(path_codes, engine="openpyxl")
        hoja_cfg = _resolver_hoja(xls, SHEET_CONFIG) or xls.sheet_names[0]
        hoja_art = _resolver_hoja(xls, SHEET_ARTICULOS) or xls.sheet_names[0]
        self.config = pd.read_excel(xls, sheet_name=hoja_cfg)
        self.articulos = pd.read_excel(xls, sheet_name=hoja_art)
        xls.close()
        self._normalizar_articulos()

        self.sectores_oficiales, self.sector_operarios_map = cargar_mapa_sectores(self.config)

        if path_salidas.is_file():
            xls_s = pd.ExcelFile(path_salidas, engine="openpyxl")
            hoja = _resolver_hoja(xls_s, SHEET_MOVIMIENTOS) or xls_s.sheet_names[0]
            self.movimientos = pd.read_excel(xls_s, sheet_name=hoja)
            xls_s.close()
            self._normalizar_movimientos()
        else:
            self.movimientos = pd.DataFrame()

        if path_activos.is_file():
            xls_a = pd.ExcelFile(path_activos, engine="openpyxl")
            hoja_a = _resolver_hoja(xls_a, SHEET_ACTIVOS) or xls_a.sheet_names[0]
            self.activos = pd.read_excel(xls_a, sheet_name=hoja_a)
            xls_a.close()
            self._normalizar_activos()
        else:
            self.activos = pd.DataFrame()

        self.ultima_actualizacion = datetime.now(timezone.utc)
        return self.ultima_actualizacion

    def _normalizar_articulos(self) -> None:
        df = self.articulos.copy()
        col_cod = _col(df, "codigo")
        col_stock = _col(df, "stock_actual", "stock")
        col_min = _col(df, "stk.min", "stk_min")
        col_precio = _col(df, "precio_unitario")
        col_desc = _col(df, "descripcion", "desc")
        col_imp = _col(df, "importancia", "criticidad")

        if col_cod:
            df["codigo"] = df[col_cod].astype(str).str.strip().str.upper()
        if col_stock:
            df["stock"] = df[col_stock].apply(_num)
        else:
            df["stock"] = 0.0
        if col_min:
            df["stk_min"] = df[col_min].apply(_num)
        else:
            df["stk_min"] = 0.0
        if col_precio:
            df["precio_unitario"] = df[col_precio].apply(_num)
        else:
            df["precio_unitario"] = 0.0
        if col_desc:
            df["desc"] = df[col_desc].astype(str).replace("nan", "")
        else:
            df["desc"] = ""
        if col_imp:
            df["criticidad"] = df[col_imp].apply(normalizar_criticidad)
        else:
            df["criticidad"] = "BASE"

        df["valor_stock"] = df["stock"] * df["precio_unitario"]
        self.articulos = df

    def _normalizar_movimientos(self) -> None:
        df = self.movimientos.copy()
        col_fecha = _col(df, "FECHA")
        col_monto = _col(df, "MONTO_TOTAL_SALIDA")
        col_operario = _col(df, "OPERARIO")
        col_tipo = _col(df, "TIPO_COMPROBANTE")
        col_cod = _col(df, "CODIGO")
        col_desc = _col(df, "DESCRIPCION")
        col_cant = _col(df, "CANTIDAD")

        if col_fecha:
            df["FECHA"] = pd.to_datetime(df[col_fecha], errors="coerce", dayfirst=True)
        else:
            df["FECHA"] = pd.NaT

        col_mes = _col(df, "MES")
        col_anio = _col(df, "AÑO", "ANIO")
        if col_mes is not None and col_anio is not None:
            mask = df["FECHA"].isna()
            if mask.any():
                df.loc[mask, "FECHA"] = pd.to_datetime(
                    df.loc[mask, col_anio].astype(str)
                    + "-"
                    + df.loc[mask, col_mes].astype(str).str.zfill(2)
                    + "-01",
                    errors="coerce",
                )

        df["MONTO_TOTAL_SALIDA"] = df[col_monto].apply(_num) if col_monto else 0.0

        if col_operario:
            df["OPERARIO"] = df[col_operario].astype(str)
            df["SECTOR_CALC"] = df["OPERARIO"].apply(
                lambda o: clasificar_sector(o, self.sector_operarios_map, self.sectores_oficiales)
            )
        else:
            df["OPERARIO"] = ""
            df["SECTOR_CALC"] = "MANTENIMIENTO"

        if col_tipo:
            df["TIPO_COMPROBANTE"] = df[col_tipo].astype(str)
            df["LINEA"] = df["TIPO_COMPROBANTE"].apply(normalizar_linea_gasto)
        else:
            df["LINEA"] = "OTROS"

        if col_cod:
            df["CODIGO"] = df[col_cod].astype(str)
        if col_desc:
            df["DESCRIPCION"] = df[col_desc].astype(str)
        if col_cant:
            df["CANTIDAD"] = df[col_cant].apply(_num)

        self.movimientos = df

    def _normalizar_activos(self) -> None:
        df = _mapear_columnas_activos(self.activos.copy())
        if "DIAS_FUERA" in df.columns:
            df["DIAS_FUERA"] = pd.to_numeric(df["DIAS_FUERA"], errors="coerce").fillna(0)
        else:
            df["DIAS_FUERA"] = 0
        if "SECTOR" in df.columns:
            df["SECTOR"] = df["SECTOR"].astype(str).str.strip().str.upper()
        df["_pendiente"] = df.apply(_fila_activo_pendiente, axis=1)
        self.activos = df
