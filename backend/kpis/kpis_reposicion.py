# -*- coding: utf-8 -*-
"""KPIs de reposición."""

from __future__ import annotations

from typing import Any

from data_loader import DataStore


def reposicion_resumen(store: DataStore) -> dict[str, Any]:
    df = store.articulos
    rep = df[df["stock"] < df["stk_min"]].copy()
    rep["faltante"] = (rep["stk_min"] - rep["stock"]).clip(lower=0)
    rep["valor_faltante"] = rep["faltante"] * rep["precio_unitario"]

    criticos = rep[rep["criticidad"] == "CRÍTICO"]

    lista = []
    for _, row in rep.sort_values("valor_faltante", ascending=False).iterrows():
        lista.append(
            {
                "codigo": row.get("codigo", ""),
                "desc": row.get("desc", ""),
                "stock": round(float(row["stock"]), 2),
                "stk_min": round(float(row["stk_min"]), 2),
                "faltante": round(float(row["faltante"]), 2),
                "precio_unitario": round(float(row["precio_unitario"]), 2),
                "valor_faltante": round(float(row["valor_faltante"]), 2),
                "criticidad": row.get("criticidad", "BASE"),
            }
        )

    return {
        "articulos_a_reponer": int(len(rep)),
        "criticos_bajo_minimo": int(len(criticos)),
        "valor_total_reposicion": round(float(rep["valor_faltante"].sum()), 2),
        "lista": lista,
        "ultima_actualizacion": store.timestamp_iso(),
    }
