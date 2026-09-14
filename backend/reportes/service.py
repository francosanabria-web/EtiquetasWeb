# -*- coding: utf-8 -*-
"""Filtros, listados y agregaciones de movimientos (capa service)."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Any

import pandas as pd

from config import COLUMNAS
from exports import build_xlsx_tabla
from store import ReportesStore


@dataclass
class FiltrosMovimientos:
    fecha_desde: str | None = None  # YYYY-MM-DD
    fecha_hasta: str | None = None
    sector: str | None = None
    operario: str | None = None
    codigo: str | None = None
    numero_orden: str | None = None
    tipo_comprobante: str | None = None
    q: str | None = None  # búsqueda libre en código/descripcion/operario/orden
    limite: int = 200
    offset: int = 0


def _parse_filtros(params: dict[str, str]) -> FiltrosMovimientos:
    def g(*keys: str) -> str | None:
        for k in keys:
            v = (params.get(k) or "").strip()
            if v:
                return v
        return None

    try:
        limite = int(params.get("limite") or params.get("limit") or "200")
    except ValueError:
        limite = 200
    try:
        offset = int(params.get("offset") or "0")
    except ValueError:
        offset = 0
    limite = max(1, min(limite, 5000))
    offset = max(0, offset)

    return FiltrosMovimientos(
        fecha_desde=g("fecha_desde", "desde"),
        fecha_hasta=g("fecha_hasta", "hasta"),
        sector=g("sector"),
        operario=g("operario"),
        codigo=g("codigo"),
        numero_orden=g("numero_orden", "orden"),
        tipo_comprobante=g("tipo_comprobante", "comprobante"),
        q=g("q", "buscar"),
        limite=limite,
        offset=offset,
    )


def _aplicar_filtros(df: pd.DataFrame, f: FiltrosMovimientos) -> pd.DataFrame:
    if df.empty:
        return df
    out = df

    if f.fecha_desde:
        d = pd.to_datetime(f.fecha_desde, errors="coerce")
        if not pd.isna(d):
            out = out[out["_fecha"] >= d.normalize()]
    if f.fecha_hasta:
        d = pd.to_datetime(f.fecha_hasta, errors="coerce")
        if not pd.isna(d):
            out = out[out["_fecha"] <= d.normalize()]
    if f.sector:
        s = f.sector.strip().upper()
        out = out[out["SECTOR"].str.upper() == s]
    if f.operario:
        op = f.operario.strip().lower()
        out = out[out["OPERARIO"].str.lower() == op]
    if f.codigo:
        cod = f.codigo.strip().lower()
        out = out[out["CODIGO"].str.lower().str.contains(cod, na=False)]
    if f.numero_orden:
        ord_ = f.numero_orden.strip().lower()
        out = out[out["NUMERO_ORDEN"].str.lower().str.contains(ord_, na=False)]
    if f.tipo_comprobante:
        tc = f.tipo_comprobante.strip().upper()
        out = out[out["TIPO_COMPROBANTE"].str.upper() == tc]
    if f.q:
        q = f.q.strip().lower()
        mask = (
            out["CODIGO"].str.lower().str.contains(q, na=False)
            | out["DESCRIPCION"].str.lower().str.contains(q, na=False)
            | out["OPERARIO"].str.lower().str.contains(q, na=False)
            | out["NUMERO_ORDEN"].str.lower().str.contains(q, na=False)
            | out["MAQUINA_SITIO"].str.lower().str.contains(q, na=False)
        )
        out = out[mask]

    return out


def _row_to_dict(row: pd.Series) -> dict[str, Any]:
    return {
        "fecha": str(row.get("FECHA") or ""),
        "mes": str(row.get("MES") or ""),
        "anio": str(row.get("AÑO") or ""),
        "codigo": str(row.get("CODIGO") or ""),
        "descripcion": str(row.get("DESCRIPCION") or ""),
        "ubicacion": str(row.get("UBICACION") or ""),
        "cantidad": float(row.get("CANTIDAD") or 0),
        "tipo_comprobante": str(row.get("TIPO_COMPROBANTE") or ""),
        "numero_orden": str(row.get("NUMERO_ORDEN") or ""),
        "maquina_sitio": str(row.get("MAQUINA_SITIO") or ""),
        "precio_unitario": float(row.get("PRECIO_UNITARIO") or 0),
        "monto_total_salida": float(row.get("MONTO_TOTAL_SALIDA") or 0),
        "operario": str(row.get("OPERARIO") or ""),
        "sector": str(row.get("SECTOR") or ""),
    }


def listar_movimientos(store: ReportesStore, params: dict[str, str]) -> dict[str, Any]:
    store.require_loaded()
    f = _parse_filtros(params)
    filtrado = _aplicar_filtros(store.df, f)
    total = int(len(filtrado))
    # Más reciente primero
    if "_fecha" in filtrado.columns and not filtrado.empty:
        filtrado = filtrado.sort_values("_fecha", ascending=False, na_position="last")
    pagina = filtrado.iloc[f.offset : f.offset + f.limite]
    items = [_row_to_dict(row) for _, row in pagina.iterrows()]
    return {
        "total": total,
        "limite": f.limite,
        "offset": f.offset,
        "items": items,
        "fuente": store.meta(),
    }


def resumen_movimientos(store: ReportesStore, params: dict[str, str]) -> dict[str, Any]:
    store.require_loaded()
    f = _parse_filtros(params)
    # resumen ignora paginación
    f.limite = 10_000_000
    f.offset = 0
    df = _aplicar_filtros(store.df, f)
    if df.empty:
        return {
            "filas": 0,
            "monto_total": 0.0,
            "cantidad_total": 0.0,
            "por_sector": [],
            "por_operario": [],
            "por_tipo_comprobante": [],
            "por_mes": [],
            "fuente": store.meta(),
        }

    monto = float(pd.to_numeric(df["MONTO_TOTAL_SALIDA"], errors="coerce").fillna(0).sum())
    cant = float(pd.to_numeric(df["CANTIDAD"], errors="coerce").fillna(0).sum())

    def agrupar(col: str, key_name: str, top: int = 30) -> list[dict[str, Any]]:
        if col not in df.columns:
            return []
        g = (
            df.groupby(col, dropna=False)
            .agg(filas=("CODIGO", "size"), monto=("MONTO_TOTAL_SALIDA", "sum"))
            .reset_index()
            .sort_values("monto", ascending=False)
            .head(top)
        )
        out = []
        for _, r in g.iterrows():
            label = str(r[col]).strip()
            if not label or label.lower() in ("nan", "none"):
                label = "(sin dato)"
            out.append(
                {
                    key_name: label,
                    "filas": int(r["filas"]),
                    "monto": round(float(r["monto"]), 2),
                }
            )
        return out

    por_mes: list[dict[str, Any]] = []
    if not df.empty:
        tmp = df.copy()
        tmp["_ym"] = tmp["_fecha"].dt.to_period("M").astype(str)
        g = (
            tmp.groupby("_ym", dropna=False)
            .agg(filas=("CODIGO", "size"), monto=("MONTO_TOTAL_SALIDA", "sum"))
            .reset_index()
            .sort_values("_ym")
        )
        for _, r in g.iterrows():
            ym = str(r["_ym"])
            if ym in ("NaT", "nan", "None"):
                continue
            por_mes.append(
                {"mes": ym, "filas": int(r["filas"]), "monto": round(float(r["monto"]), 2)}
            )

    return {
        "filas": int(len(df)),
        "monto_total": round(monto, 2),
        "cantidad_total": round(cant, 2),
        "por_sector": agrupar("SECTOR", "sector"),
        "por_operario": agrupar("OPERARIO", "operario"),
        "por_tipo_comprobante": agrupar("TIPO_COMPROBANTE", "tipo_comprobante"),
        "por_mes": por_mes,
        "fuente": store.meta(),
    }


def opciones_filtros(store: ReportesStore) -> dict[str, Any]:
    store.require_loaded()
    df = store.df

    def uniques(col: str) -> list[str]:
        if col not in df.columns or df.empty:
            return []
        vals = sorted(
            {
                str(v).strip()
                for v in df[col].dropna().astype(str)
                if str(v).strip() and str(v).strip().lower() not in ("nan", "none")
            }
        )
        return vals

    fechas = df["_fecha"].dropna() if "_fecha" in df.columns else pd.Series(dtype="datetime64[ns]")
    return {
        "sectores": uniques("SECTOR"),
        "operarios": uniques("OPERARIO"),
        "tipos_comprobante": uniques("TIPO_COMPROBANTE"),
        "fecha_min": fechas.min().strftime("%Y-%m-%d") if len(fechas) else "",
        "fecha_max": fechas.max().strftime("%Y-%m-%d") if len(fechas) else "",
        "fuente": store.meta(),
    }


def _df_filtrado_export(store: ReportesStore, params: dict[str, str]) -> pd.DataFrame:
    store.require_loaded()
    f = _parse_filtros(params)
    f.limite = 50_000
    f.offset = 0
    df = _aplicar_filtros(store.df, f)
    if "_fecha" in df.columns and not df.empty:
        df = df.sort_values("_fecha", ascending=False, na_position="last")
    return df


def export_xlsx(store: ReportesStore, params: dict[str, str]) -> bytes:
    """Excel Table con layout del detalle del mail diario de gastos (+ SECTOR)."""
    df = _df_filtrado_export(store, params)
    return build_xlsx_tabla(df, sheet_name="Movimientos", table_name="TablaGastos")


def export_csv(store: ReportesStore, params: dict[str, str]) -> bytes:
    """DEPRECATED — preferir export_xlsx. Se mantiene por compatibilidad."""
    df = _df_filtrado_export(store, params)
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(COLUMNAS)
    for _, row in df.iterrows():
        writer.writerow([row.get(c, "") for c in COLUMNAS])
    return ("\ufeff" + buf.getvalue()).encode("utf-8")
