# -*- coding: utf-8 -*-
"""Store en memoria del maestro de artículos (fuente operativa Fase 1 = Excel prueba)."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from excel_io import (
    catalogos_desde_config,
    col_categoria,
    col_descripcion,
    col_precio,
    col_stock,
    col_ubicacion,
    leer_maestro,
)
from config import HOJA_ARTICULOS, maestro_path


class CargandoDatosError(Exception):
    pass


class RedNoDisponibleError(Exception):
    pass


class SalidasStore:
    _lock = threading.Lock()
    _instance: SalidasStore | None = None

    def __init__(self) -> None:
        self.ultima_actualizacion: datetime | None = None
        self._cargando = False
        self._error_carga: str | None = None
        self.hojas: dict[str, pd.DataFrame] = {}
        self.config_df: pd.DataFrame = pd.DataFrame()
        self.catalogos: dict[str, Any] = {}
        self.archivo_ok = False
        self.path_maestro: str = ""

    @classmethod
    def get(cls) -> SalidasStore:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = SalidasStore()
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
                "Los datos de salidas se están cargando. Espere e intente de nuevo."
            )

    def ensure_loaded(self) -> None:
        if self.ultima_actualizacion is not None:
            return
        if self._cargando:
            raise CargandoDatosError(
                "Los datos de salidas se están cargando. Espere e intente de nuevo."
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

    def _cargar(self) -> datetime:
        path = maestro_path()
        self.path_maestro = str(path)
        self.archivo_ok = path.is_file()
        hojas, config_df = leer_maestro()
        self.hojas = hojas
        self.config_df = config_df
        self.catalogos = catalogos_desde_config(config_df)
        self.ultima_actualizacion = datetime.now(timezone.utc)
        self.archivo_ok = True
        return self.ultima_actualizacion

    def df_articulos(self) -> pd.DataFrame:
        if HOJA_ARTICULOS in self.hojas:
            return self.hojas[HOJA_ARTICULOS]
        for df in self.hojas.values():
            if "codigo" in df.columns:
                return df
        return pd.DataFrame()

    def buscar_articulo_raw(self, codigo: str) -> tuple[str, pd.DataFrame, Any, dict[str, str]] | None:
        """(hoja, df, idx, cols) o None."""
        cod = str(codigo or "").strip().upper()
        if not cod:
            return None
        for nombre, df in self.hojas.items():
            if "codigo" not in df.columns:
                continue
            idxs = df.index[df["codigo"] == cod].tolist()
            if not idxs:
                continue
            cols = {
                "stock": col_stock(df) or "",
                "precio": col_precio(df) or "",
                "ubicacion": col_ubicacion(df) or "",
                "descripcion": col_descripcion(df) or "",
                "categoria": col_categoria(df) or "",
            }
            return nombre, df, idxs[0], cols
        return None

    def articulo_dict(self, codigo: str) -> dict[str, Any] | None:
        found = self.buscar_articulo_raw(codigo)
        if not found:
            return None
        hoja, df, idx, cols = found
        def cell(key: str, default: Any = "") -> Any:
            c = cols.get(key) or ""
            if not c or c not in df.columns:
                return default
            v = df.at[idx, c]
            if pd.isna(v):
                return default
            return v

        stock_raw = cell("stock", 0)
        precio_raw = cell("precio", 0)
        try:
            stock = float(stock_raw)
        except (TypeError, ValueError):
            stock = 0.0
        try:
            precio = float(precio_raw)
        except (TypeError, ValueError):
            precio = 0.0
        return {
            "codigo": str(codigo).strip().upper(),
            "descripcion": str(cell("descripcion", "")).strip().upper(),
            "ubicacion": str(cell("ubicacion", "")).strip().upper(),
            "stock_actual": stock,
            "precio_unitario": precio,
            "categoria": str(cell("categoria", "GENERAL") or "GENERAL").strip().upper(),
            "hoja": hoja,
        }

    def set_stock(self, codigo: str, nuevo: float) -> dict[str, Any]:
        found = self.buscar_articulo_raw(codigo)
        if not found:
            raise ValueError(f"No se encontró el código {codigo} en el maestro.")
        hoja, df, idx, cols = found
        c_stock = cols.get("stock")
        if not c_stock:
            raise ValueError(f"El maestro no tiene columna de stock para {codigo}.")
        df.at[idx, c_stock] = float(nuevo)
        self.hojas[hoja] = df
        art = self.articulo_dict(codigo)
        assert art is not None
        return art
