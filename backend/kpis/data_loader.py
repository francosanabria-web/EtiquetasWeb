# -*- coding: utf-8 -*-
"""
Lectura SOLO LECTURA desde MariaDB (panol.salida_historial, panol.maestro_stock, panol.salida_activos).
Nunca escribe. No lee Excel ni G: — DB es la unica fuente de datos.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import pymysql

from clasificacion import normalizar_criticidad, normalizar_linea_gasto
from config import (
    DB_HOST,
    DB_NAME,
    DB_PASSWORD,
    DB_PORT,
    DB_USER,
    KPIS_DB_ENABLED,
)


class RedNoDisponibleError(Exception):
    pass


class CargandoDatosError(Exception):
    """DB aún cargando (arranque o refresh en curso)."""
    pass


def _get_connection():
    """Retorna una conexión activa a MariaDB panol."""
    return pymysql.connect(
        host=DB_HOST,
        port=int(DB_PORT),
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def _load_articulos_from_db() -> pd.DataFrame:
    """Carga artículos desde maestro_stock."""
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT codigo, descripcion, stock AS stock_actual,
                       stock_minimo AS stk_min, precio_unitario,
                       importancia AS criticidad, categoria
                FROM maestro_stock
                WHERE activo = 1
                """
            )
            rows = cur.fetchall()
            if not rows:
                return pd.DataFrame(
                    columns=["codigo", "desc", "stock", "stk_min", "precio_unitario", "criticidad", "valor_stock"]
                )
            df = pd.DataFrame(rows)
            df["codigo"] = df["codigo"].astype(str).str.strip().str.upper()
            df["stock"] = pd.to_numeric(df["stock_actual"], errors="coerce").fillna(0.0)
            df["stk_min"] = pd.to_numeric(df["stk_min"], errors="coerce").fillna(0.0)
            df["precio_unitario"] = pd.to_numeric(df["precio_unitario"], errors="coerce").fillna(0.0)
            df["desc"] = df["descripcion"].astype(str).replace("nan", "")
            df["criticidad"] = df["criticidad"].apply(normalizar_criticidad)
            df["valor_stock"] = df["stock"] * df["precio_unitario"]
            return df[["codigo", "desc", "stock", "stk_min", "precio_unitario", "criticidad", "valor_stock"]]
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _load_movimientos_from_db() -> pd.DataFrame:
    """Carga movimientos desde salida_historial (DB única fuente).
    Sin fallback a Excel — si DB no tiene datos, devuelve DataFrame vacío.
    """
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT fecha, mes, anio, codigo, descripcion, ubicacion, cantidad,
                       tipo_comprobante, numero_orden, maquina_sitio,
                       precio_unitario, monto_total,
                       operario_nombre AS operario, sector_nombre AS sector,
                       COALESCE(sector_nombre, '') AS sector_calc
                FROM salida_historial
                WHERE COALESCE(anulado, 0) = 0
                ORDER BY fecha DESC, id DESC
                LIMIT 200000
                """
            )
            rows = cur.fetchall()
            if not rows:
                return pd.DataFrame(
                    columns=["FECHA", "MES", "AÑO", "CODIGO", "DESCRIPCION", "UBICACION",
                             "CANTIDAD", "TIPO_COMPROBANTE", "NUMERO_ORDEN", "MAQUINA_SITIO",
                             "PRECIO_UNITARIO", "MONTO_TOTAL_SALIDA", "OPERARIO",
                             "SECTOR", "SECTOR_CALC", "LINEA"]
                )
            df = pd.DataFrame(rows)
            # FECHA como datetime
            df["FECHA"] = pd.to_datetime(df["fecha"], errors="coerce")
            # MES/AÑO from DB fields
            df["MES"] = df["mes"].astype(str).str.strip()
            df["AÑO"] = df["anio"].astype(str).str.strip()
            # Campo string fields
            for col in ("codigo", "descripcion", "ubicacion", "tipo_comprobante",
                        "numero_orden", "maquina_sitio", "operario", "sector"):
                df[col] = df[col].astype(str).str.strip().str.upper().replace({"NAN": "", "NONE": "", "NAT": ""})
            # Numeric fields
            df["CANTIDAD"] = pd.to_numeric(df["cantidad"], errors="coerce").fillna(0.0)
            df["PRECIO_UNITARIO"] = pd.to_numeric(df["precio_unitario"], errors="coerce").fillna(0.0)
            df["MONTO_TOTAL_SALIDA"] = pd.to_numeric(df["monto_total"], errors="coerce").fillna(0.0)
            # SECTOR_CALC from DB sector_nombre directly
            df["SECTOR_CALC"] = df["sector"].str.upper()
            # LINEA from tipo_comprobante
            df["LINEA"] = df["tipo_comprobante"].apply(normalizar_linea_gasto)
            # Ensure FECHA is datetime64
            df["FECHA"] = pd.to_datetime(df["FECHA"], errors="coerce")
            return df
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _load_activos_from_db() -> pd.DataFrame:
    """Carga activos desde MariaDB panol.salida_activos (DB única fuente).
    Sin fallback a Excel — si DB no tiene datos, devuelve DataFrame vacío.
    """
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT numero_pedido AS NUMERO_PEDIDO,
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
            if not rows:
                return pd.DataFrame(
                    columns=["NUMERO_PEDIDO", "NUMERO_OC", "NUMERO_REMITO", "SECTOR", "CODIGO",
                             "EQUIPO_REPUESTO", "CANTIDAD", "NRO_SERIE", "FECHA_SALIDA",
                             "PROVEEDOR", "FECHA_REGRESO", "ESTADO_AL_INGRESO", "OBSERVACIONES",
                             "DIAS_FUERA", "ESTADO", "_pendiente"]
                )
            df = pd.DataFrame(rows)
            # Normalizar tipos
            if "DIAS_FUERA" in df.columns:
                df["DIAS_FUERA"] = pd.to_numeric(df["DIAS_FUERA"], errors="coerce").fillna(0).astype(int)
            else:
                df["DIAS_FUERA"] = 0
            if "sector" in df.columns:
                df["sector"] = df["sector"].astype(str).strip().str.upper().replace({"NAN": "", "NONE": ""})
            # ESTADO ya viene como fuera_de_planta / ingresado_a_planta en DB
            df["ESTADO"] = df["ESTADO"].astype(str).str.strip().str.upper()
            # _pendiente: fuera_de_planta == FUERA_DE_PLANTA
            df["_pendiente"] = df["ESTADO"] == "FUERA_DE_PLANTA"
            # Asegurar columnas esperadas existan
            for col in ["NUMERO_PEDIDO", "NUMERO_OC", "NUMERO_REMITO", "CODIGO", "EQUIPO_REPUESTO",
                        "NRO_SERIE", "PROVEEDOR", "ESTADO_AL_INGRESO", "OBSERVACIONES"]:
                if col not in df.columns:
                    df[col] = ""
                df[col] = df[col].astype(str).strip().replace({"nan": "", "None": "", "NaT": ""})
            # FECHA_SALIDA / FECHA_REGRESO como datetime para compatibilidad
            df["FECHA_SALIDA"] = pd.to_datetime(df["FECHA_SALIDA"], errors="coerce")
            df["FECHA_REGRESO"] = pd.to_datetime(df["FECHA_REGRESO"], errors="coerce")
            return df
    finally:
        try:
            conn.close()
        except Exception:
            pass


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
        if not KPIS_DB_ENABLED:
            raise RedNoDisponibleError("KPIS_DB_ENABLED no está activo. DB es la única fuente.")

        # ── Artículos desde maestro_stock (DB) ──
        try:
            self.articulos = _load_articulos_from_db()
            self.archivos_ok["maestro_stock"] = True
        except Exception as e:
            self.archivos_ok["maestro_stock"] = False
            raise RedNoDisponibleError(f"No se pudieron cargar artículos desde DB: {e}")

        # Obtener sectores de maestro_stock categorías + sectores de salida_historial
        try:
            self.sectores_oficiales, self.sector_operarios_map = self._cargar_sectores()
        except Exception:
            self.sectores_oficiales = []
            self.sector_operarios_map = {}

        # ── Movimientos desde salida_historial (DB) ──
        # Sin fallback a Excel — si DB no tiene datos, devuelve vacío (no 6629 de Excel)
        try:
            self.movimientos = _load_movimientos_from_db()
            self.archivos_ok["salida_historial"] = True
        except Exception as e:
            self.archivos_ok["salida_historial"] = False
            raise RedNoDisponibleError(f"No se pudieron cargar movimientos desde DB: {e}")

        # ── Activos desde salida_activos (DB) ──
        # Sin fallback a Excel — DB es única fuente (migrado 2026-09-23, 153 filas)
        try:
            self.activos = _load_activos_from_db()
            self.archivos_ok["salida_activos"] = True
        except Exception as e:
            self.activos = pd.DataFrame()
            self.archivos_ok["salida_activos"] = False
            raise RedNoDisponibleError(f"No se pudieron cargar activos desde DB: {e}")

        self.ultima_actualizacion = datetime.now(timezone.utc)
        return self.ultima_actualizacion

    def _cargar_sectores(self) -> tuple[list[str], dict[str, list[str]]]:
        """Carga sectores y mapa de operarios desde DB."""
        sectores_set: set[str] = set()
        operarios_map: dict[str, list[str]] = {}
        try:
            conn = _get_connection()
            with conn.cursor() as cur:
                # Sectores únicos de salida_historial
                cur.execute("SELECT DISTINCT sector_nombre FROM salida_historial WHERE COALESCE(anulado,0)=0 AND sector_nombre IS NOT NULL ORDER BY sector_nombre")
                for row in cur.fetchall():
                    s = str(row["sector_nombre"]).strip().upper()
                    if s and s not in ("NAN", "NONE", ""):
                        sectores_set.add(s)
                # Operarios por sector
                cur.execute("SELECT DISTINCT operario_nombre, sector_nombre FROM salida_historial WHERE COALESCE(anulado,0)=0 AND operario_nombre IS NOT NULL")
                for row in cur.fetchall():
                    op = str(row["operario_nombre"]).strip().upper()
                    sec = str(row["sector_nombre"]).strip().upper()
                    if op and sec:
                        operarios_map.setdefault(sec, []).append(op)
            try:
                conn.close()
            except Exception:
                pass
        except Exception:
            pass
        # Agregar sectores de maestro_stock categorias
        for cat in ("CRITICO", "ALTA FRECUENCIA", "BASE"):
            sectores_set.add(cat)
        return sorted(sectores_set), operarios_map

    def _normalizar_articulos(self) -> None:
        """Ya no necesita — articulos se cargan normalizados desde _load_articulos_from_db."""
        pass

    def _normalizar_movimientos(self) -> None:
        """Ya no necesita — movimientos se cargan normalizados desde _load_movimientos_from_db."""
        pass

    def _normalizar_activos(self) -> None:
        """Ya no necesita — activos se cargan normalizados desde _load_activos_from_db."""
        pass
