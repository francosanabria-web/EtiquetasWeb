# -*- coding: utf-8 -*-
"""Lógica de resumen Activos (lectura)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from config import DIAS_ALERTA
from store import ActivosStore, fmt_fecha


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


def _row_to_item(row: pd.Series, *, fuera: bool) -> dict[str, Any]:
    sheet_row = row.get("_sheet_row")
    try:
        sr = int(sheet_row) if sheet_row is not None and not (isinstance(sheet_row, float) and pd.isna(sheet_row)) else -1
    except (TypeError, ValueError):
        sr = -1
    if fuera and sr >= 0:
        item_id = f"f-{sr}"
    elif (not fuera) and sr >= 0:
        item_id = f"i-{sr}"
    else:
        item_id = ""
    return {
        "id": item_id,
        "codigo": _norm_doc(row.get("CODIGO", "")),
        "equipo": _norm_text(row.get("EQUIPO_REPUESTO", "")),
        "sector": _norm_text(row.get("SECTOR", "")),
        "dias_fuera": int(float(row.get("DIAS_FUERA", 0) or 0)),
        "cantidad": _norm_cantidad(row.get("CANTIDAD", 1)),
        "estado": _norm_text(row.get("ESTADO", "")),
        "proveedor": _norm_text(row.get("PROVEEDOR", "")),
        "remito": _norm_doc(row.get("NUMERO_REMITO", "")),
        "n_pedido": _norm_doc(row.get("NUMERO_PEDIDO", "")),
        "n_oc": _norm_doc(row.get("NUMERO_OC", "")),
        "nro_serie": _norm_text(row.get("NRO_SERIE", "")),
        "fecha_salida": fmt_fecha(row.get("FECHA_SALIDA")),
        "fecha_regreso": fmt_fecha(row.get("FECHA_REGRESO")),
        "estado_al_ingreso": _norm_text(row.get("ESTADO_AL_INGRESO", "")),
        "observaciones": _norm_text(row.get("OBSERVACIONES", "")),
        "fingerprint": _norm_text(row.get("FINGERPRINT", "")),
    }


def activos_resumen(store: ActivosStore) -> dict[str, Any]:
    store.require_loaded()
    df = store.df
    empty = {
        "fuera_de_planta": 0,
        "ingresados": 0,
        "dias_promedio_fuera": 0.0,
        "criticos": 0,
        "por_sector": [],
        "sectores": [],
        "lista_fuera": [],
        "lista_ingresados": [],
        "ultima_actualizacion": store.timestamp_iso(),
    }
    if df.empty:
        return empty

    fuera = df[df["_fuera"]].copy()
    ingresados = df[~df["_fuera"]].copy()

    dias = pd.to_numeric(fuera["DIAS_FUERA"], errors="coerce").fillna(0)
    dias_prom = round(float(dias.mean()), 1) if len(fuera) else 0.0
    criticos = int((dias > DIAS_ALERTA).sum()) if len(fuera) else 0

    por_sector: list[dict[str, Any]] = []
    if "SECTOR" in fuera.columns and not fuera.empty:
        grp = fuera.groupby("SECTOR", dropna=False).size().reset_index(name="cantidad")
        for _, r in grp.iterrows():
            sector = str(r["SECTOR"]).strip()
            if sector and sector.lower() not in ("nan", "none"):
                por_sector.append({"sector": sector, "cantidad": int(r["cantidad"])})

    sectores = sorted(
        {
            str(s).strip()
            for s in df.get("SECTOR", pd.Series(dtype=str)).dropna().astype(str)
            if str(s).strip() and str(s).strip().lower() not in ("nan", "none")
        }
    )

    lista_fuera = [
        _row_to_item(row, fuera=True)
        for _, row in fuera.sort_values("DIAS_FUERA", ascending=False).iterrows()
    ]
    # Ingresados: más recientes primero si hay fecha_regreso
    if "FECHA_REGRESO" in ingresados.columns and not ingresados.empty:
        tmp = ingresados.copy()
        tmp["_fr"] = pd.to_datetime(tmp["FECHA_REGRESO"], errors="coerce", dayfirst=True)
        ingresados = tmp.sort_values("_fr", ascending=False)
    lista_ing = [_row_to_item(row, fuera=False) for _, row in ingresados.iterrows()]

    return {
        "fuera_de_planta": int(len(fuera)),
        "ingresados": int(len(ingresados)),
        "dias_promedio_fuera": dias_prom,
        "criticos": criticos,
        "por_sector": por_sector,
        "sectores": sectores,
        "lista_fuera": lista_fuera,
        "lista_ingresados": lista_ing,
        "ultima_actualizacion": store.timestamp_iso(),
    }
