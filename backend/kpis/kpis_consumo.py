# -*- coding: utf-8 -*-
"""KPIs de consumo y movimientos."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd

from clasificacion import orden_lineas_gasto
from data_loader import DataStore


def _parse_mes(mes: str | None) -> tuple[int, int]:
    if mes:
        parts = mes.strip().split("-")
        if len(parts) == 2:
            return int(parts[0]), int(parts[1])
    hoy = date.today()
    return hoy.year, hoy.month


def _filtrar_mes(df: pd.DataFrame, year: int, month: int) -> pd.DataFrame:
    if df.empty or "FECHA" not in df.columns:
        return df.iloc[0:0]
    mask = (df["FECHA"].dt.year == year) & (df["FECHA"].dt.month == month)
    return df.loc[mask]


def _ts(store: DataStore) -> str:
    return store.timestamp_iso()


def consumo_mensual(store: DataStore, meses: int = 12) -> dict[str, Any]:
    df = store.movimientos
    if df.empty:
        return {"datos": [], "ultima_actualizacion": _ts(store)}

    tmp = df.dropna(subset=["FECHA"]).copy()
    tmp["periodo"] = tmp["FECHA"].dt.to_period("M").astype(str)
    agg = tmp.groupby("periodo", as_index=False)["MONTO_TOTAL_SALIDA"].sum()
    agg = agg.sort_values("periodo", ascending=False).head(meses)
    agg = agg.sort_values("periodo")
    datos = [
        {"periodo": row["periodo"], "total": round(float(row["MONTO_TOTAL_SALIDA"]), 2)}
        for _, row in agg.iterrows()
    ]
    return {"datos": datos, "ultima_actualizacion": _ts(store)}


def consumo_por_sector(store: DataStore, mes: str | None = None) -> dict[str, Any]:
    year, month = _parse_mes(mes)
    df = _filtrar_mes(store.movimientos, year, month)
    sectores = store.sectores_oficiales

    totales: dict[str, float] = {s: 0.0 for s in sectores}
    if not df.empty:
        grp = df.groupby("SECTOR_CALC")["MONTO_TOTAL_SALIDA"].sum()
        for sec, val in grp.items():
            key = str(sec).upper()
            if key in totales:
                totales[key] = float(val)
            else:
                totales[key] = float(val)

    datos = [{"sector": s, "total": round(totales.get(s, 0.0), 2)} for s in sectores]
    periodo = f"{year}-{month:02d}"
    return {"periodo": periodo, "datos": datos, "ultima_actualizacion": _ts(store)}


def consumo_por_linea(store: DataStore, mes: str | None = None) -> dict[str, Any]:
    year, month = _parse_mes(mes)
    df = _filtrar_mes(store.movimientos, year, month)
    df_m = df[df["SECTOR_CALC"] == "MANTENIMIENTO"] if not df.empty else df

    orden = orden_lineas_gasto()
    totales = {ln: 0.0 for ln in orden}
    if not df_m.empty:
        grp = df_m.groupby("LINEA")["MONTO_TOTAL_SALIDA"].sum()
        for ln, val in grp.items():
            key = str(ln)
            totales[key] = totales.get(key, 0.0) + float(val)

    datos = [{"linea": ln, "total": round(totales.get(ln, 0.0), 2)} for ln in orden if totales.get(ln, 0) > 0]
    # incluir líneas con 0 si están en orden preferido
    if not datos:
        datos = [{"linea": ln, "total": 0.0} for ln in orden if ln != "OTROS"]

    periodo = f"{year}-{month:02d}"
    return {"periodo": periodo, "sector_filtro": "MANTENIMIENTO", "datos": datos, "ultima_actualizacion": _ts(store)}


def consumo_top_articulos(
    store: DataStore, mes: str | None = None, top: int = 10
) -> dict[str, Any]:
    if mes:
        year, month = _parse_mes(mes)
        df = _filtrar_mes(store.movimientos, year, month)
        periodo = f"{year}-{month:02d}"
    else:
        df = store.movimientos
        periodo = "acumulado"

    if df.empty:
        return {
            "periodo": periodo,
            "por_monto": [],
            "por_cantidad": [],
            "ultima_actualizacion": _ts(store),
        }

    if "CODIGO" not in df.columns:
        return {
            "periodo": periodo,
            "por_monto": [],
            "por_cantidad": [],
            "ultima_actualizacion": _ts(store),
        }

    por_monto = (
        df.groupby("CODIGO", as_index=False)
        .agg(monto=("MONTO_TOTAL_SALIDA", "sum"), descripcion=("DESCRIPCION", "first"))
        .sort_values("monto", ascending=False)
        .head(top)
    )
    por_cant = (
        df.groupby("CODIGO", as_index=False)
        .agg(cantidad=("CANTIDAD", "sum"), descripcion=("DESCRIPCION", "first"))
        .sort_values("cantidad", ascending=False)
        .head(top)
    )

    return {
        "periodo": periodo,
        "por_monto": [
            {
                "codigo": r["CODIGO"],
                "descripcion": r.get("descripcion", ""),
                "monto": round(float(r["monto"]), 2),
            }
            for _, r in por_monto.iterrows()
        ],
        "por_cantidad": [
            {
                "codigo": r["CODIGO"],
                "descripcion": r.get("descripcion", ""),
                "cantidad": round(float(r["cantidad"]), 2),
            }
            for _, r in por_cant.iterrows()
        ],
        "ultima_actualizacion": _ts(store),
    }


def consumo_tendencia_anual(store: DataStore) -> dict[str, Any]:
    df = store.movimientos
    if df.empty:
        return {"datos": [], "sectores": store.sectores_oficiales, "ultima_actualizacion": _ts(store)}

    tmp = df.dropna(subset=["FECHA"]).copy()
    hoy = datetime.now()
    limite = hoy - pd.DateOffset(months=12)
    tmp = tmp[tmp["FECHA"] >= limite]
    tmp["periodo"] = tmp["FECHA"].dt.to_period("M").astype(str)

    sectores = store.sectores_oficiales
    pivot: dict[str, dict[str, float]] = {}
    for _, row in tmp.iterrows():
        per = row["periodo"]
        sec = str(row["SECTOR_CALC"]).upper()
        if per not in pivot:
            pivot[per] = {s: 0.0 for s in sectores}
        if sec not in pivot[per]:
            pivot[per][sec] = 0.0
        pivot[per][sec] += float(row["MONTO_TOTAL_SALIDA"])

    periodos = sorted(pivot.keys())
    datos = []
    for per in periodos:
        fila: dict[str, Any] = {"periodo": per}
        for s in sectores:
            fila[s] = round(pivot[per].get(s, 0.0), 2)
        datos.append(fila)

    return {"datos": datos, "sectores": sectores, "ultima_actualizacion": _ts(store)}
