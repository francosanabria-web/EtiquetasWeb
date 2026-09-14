# -*- coding: utf-8 -*-
"""Helpers de lectura de movimientos — reutilizables por el módulo Reportes.

Sin acoplamiento a Starlette/UI. Solo contratos de datos + pandas.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from config import COLUMNAS_MOVIMIENTO, historial_path
from excel_io import fecha_sin_hora_str, leer_movimientos, parse_fecha


def columnas_canonicas() -> list[str]:
    return list(COLUMNAS_MOVIMIENTO)


def cargar_historial(path: Path | None = None) -> pd.DataFrame:
    """Lee master_salidas (o path explícito)."""
    return leer_movimientos(path or historial_path())


def filtrar_por_fecha(
    df: pd.DataFrame,
    desde: date | str | None = None,
    hasta: date | str | None = None,
) -> pd.DataFrame:
    if df is None or df.empty or "FECHA" not in df.columns:
        return df.copy() if df is not None else pd.DataFrame(columns=COLUMNAS_MOVIMIENTO)
    d0 = parse_fecha(desde) if desde else None
    d1 = parse_fecha(hasta) if hasta else None
    out = df.copy()
    fechas = out["FECHA"].apply(parse_fecha)
    mask = fechas.notna()
    if d0:
        mask &= fechas.apply(lambda x: x is not None and x >= d0)
    if d1:
        mask &= fechas.apply(lambda x: x is not None and x <= d1)
    return out.loc[mask].reset_index(drop=True)


def a_registros(df: pd.DataFrame, limite: int = 500) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    rows = df.head(max(0, limite)).fillna("")
    result: list[dict[str, Any]] = []
    for _, r in rows.iterrows():
        item = {c: r[c] if c in r.index else "" for c in COLUMNAS_MOVIMIENTO}
        if "FECHA" in item:
            item["FECHA"] = fecha_sin_hora_str(item["FECHA"])
        for k in ("CANTIDAD", "PRECIO_UNITARIO", "MONTO_TOTAL_SALIDA", "AÑO", "NUMERO_ORDEN"):
            if k in item:
                try:
                    item[k] = float(item[k]) if item[k] != "" else 0
                except (TypeError, ValueError):
                    pass
        result.append(item)
    return result
