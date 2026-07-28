# -*- coding: utf-8 -*-
"""KPIs de stock e inventario."""

from __future__ import annotations

from typing import Any

import pandas as pd

from clasificacion import CRITICIDAD_OPCIONES
from data_loader import DataStore


def _ts(store: DataStore) -> str:
    return store.timestamp_iso()


def stock_resumen(store: DataStore) -> dict[str, Any]:
    df = store.articulos
    if df.empty:
        return {
            "total_articulos": 0,
            "bajo_minimo": {"cantidad": 0, "porcentaje": 0.0, "valor_pesos": 0.0},
            "sobre_minimo": {"cantidad": 0, "porcentaje": 0.0, "valor_pesos": 0.0},
            "en_cero": {"cantidad": 0, "valor_reposicion_estimado": 0.0},
            "stock_valorizado_total": 0.0,
            "por_criticidad": [],
            "ultima_actualizacion": _ts(store),
        }

    total = len(df)
    bajo = df[df["stock"] < df["stk_min"]]
    sobre = df[df["stock"] >= df["stk_min"]]
    cero = df[df["stock"] <= 0]

    valor_bajo = float(bajo["valor_stock"].sum())
    valor_sobre = float(sobre["valor_stock"].sum())
    valor_total = float(df["valor_stock"].sum())

    rep_cero = cero.copy()
    rep_cero["faltante"] = (rep_cero["stk_min"] - rep_cero["stock"]).clip(lower=0)
    valor_rep_cero = float((rep_cero["faltante"] * rep_cero["precio_unitario"]).sum())

    por_crit = []
    for crit in CRITICIDAD_OPCIONES:
        sub = df[df["criticidad"] == crit]
        por_crit.append(
            {
                "criticidad": crit,
                "cantidad": int(len(sub)),
                "valor": round(float(sub["valor_stock"].sum()), 2),
            }
        )

    pct = lambda n: round(100.0 * n / total, 2) if total else 0.0

    return {
        "total_articulos": total,
        "bajo_minimo": {
            "cantidad": int(len(bajo)),
            "porcentaje": pct(len(bajo)),
            "valor_pesos": round(valor_bajo, 2),
        },
        "sobre_minimo": {
            "cantidad": int(len(sobre)),
            "porcentaje": pct(len(sobre)),
            "valor_pesos": round(valor_sobre, 2),
        },
        "en_cero": {
            "cantidad": int(len(cero)),
            "valor_reposicion_estimado": round(valor_rep_cero, 2),
        },
        "stock_valorizado_total": round(valor_total, 2),
        "por_criticidad": por_crit,
        "ultima_actualizacion": _ts(store),
    }


def stock_bajo_minimo(store: DataStore, criticidad: str | None = None) -> dict[str, Any]:
    df = store.articulos
    bajo = df[df["stock"] < df["stk_min"]].copy()
    if criticidad:
        crit_norm = criticidad.strip().upper()
        bajo = bajo[bajo["criticidad"].str.upper() == crit_norm]

    bajo["faltante"] = (bajo["stk_min"] - bajo["stock"]).clip(lower=0)
    bajo["valor_faltante"] = bajo["faltante"] * bajo["precio_unitario"]

    items = []
    for _, row in bajo.sort_values(["criticidad", "faltante"], ascending=[True, False]).iterrows():
        items.append(
            {
                "codigo": row.get("codigo", ""),
                "desc": row.get("desc", ""),
                "stock": round(float(row["stock"]), 2),
                "stk_min": round(float(row["stk_min"]), 2),
                "precio_unitario": round(float(row["precio_unitario"]), 2),
                "faltante": round(float(row["faltante"]), 2),
                "valor_faltante": round(float(row["valor_faltante"]), 2),
                "criticidad": row.get("criticidad", "BASE"),
            }
        )

    return {"articulos": items, "total": len(items), "ultima_actualizacion": _ts(store)}


def stock_en_cero(store: DataStore, top: int = 20) -> dict[str, Any]:
    df = store.articulos[store.articulos["stock"] <= 0].copy()
    df["valor_reposicion"] = df["stk_min"] * df["precio_unitario"]
    df = df.sort_values("valor_reposicion", ascending=False).head(top)
    items = []
    for _, row in df.iterrows():
        items.append(
            {
                "codigo": row.get("codigo", ""),
                "desc": row.get("desc", ""),
                "stock": round(float(row["stock"]), 2),
                "stk_min": round(float(row["stk_min"]), 2),
                "precio_unitario": round(float(row["precio_unitario"]), 2),
                "valor_reposicion": round(float(row["valor_reposicion"]), 2),
                "criticidad": row.get("criticidad", "BASE"),
            }
        )
    return {"articulos": items, "total": int(len(store.articulos[store.articulos["stock"] <= 0])), "ultima_actualizacion": _ts(store)}
