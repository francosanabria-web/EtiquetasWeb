# -*- coding: utf-8 -*-
"""Operaciones de escritura — marcar regreso / restablecer a fuera."""

from __future__ import annotations

from typing import Any

import pandas as pd

from excel_io import (
    FileLock,
    calcular_dias_fuera,
    excel_path,
    fecha_str,
    fila_pendiente,
    leer_ambas_hojas,
    parse_fecha,
    escribir_ambas_hojas,
)
from store import ActivosStore


def _parse_ids(ids: list[str], prefix: str) -> list[int]:
    if not ids:
        raise ValueError("Seleccioná al menos un ítem.")
    filas: list[int] = []
    for raw in ids:
        s = str(raw).strip()
        if s.startswith(prefix):
            s = s[len(prefix) :]
        try:
            filas.append(int(s))
        except ValueError as e:
            raise ValueError(f"Id de ítem inválido: {raw}") from e
    return filas


def marcar_regreso(
    ids: list[str],
    fecha_regreso: str,
    estado_al_ingreso: str,
) -> dict[str, Any]:
    """Mueve filas de FUERA → INGRESADO (misma lógica que el escritorio)."""
    filas_pedidas = _parse_ids(ids, "f-")
    fr = parse_fecha(fecha_regreso)
    if fr is None:
        raise ValueError("Fecha de ingreso inválida. Usá formato DD/MM/AAAA o AAAA-MM-DD.")
    est = str(estado_al_ingreso or "").strip().upper()
    if not est:
        raise ValueError("Indicá el estado / condición al ingresar a planta.")

    path = excel_path()
    with FileLock(path):
        df_fuera, df_ing = leer_ambas_hojas(path)
        movidos_rows: list[pd.Series] = []
        no_encontrados: list[str] = []
        fr_txt = fecha_str(fr)
        indices_ok: list[int] = []

        for sheet_row in sorted(set(filas_pedidas)):
            if sheet_row < 0 or sheet_row >= len(df_fuera):
                no_encontrados.append(f"f-{sheet_row}")
                continue
            row = df_fuera.loc[sheet_row]
            if not fila_pendiente(row):
                no_encontrados.append(f"f-{sheet_row}")
                continue

            nuevo = row.copy()
            nuevo["FECHA_REGRESO"] = fr_txt
            nuevo["ESTADO"] = "INGRESADO_A_PLANTA"
            nuevo["ESTADO_AL_INGRESO"] = est
            nuevo["DIAS_FUERA"] = calcular_dias_fuera(nuevo.get("FECHA_SALIDA"), fr)
            movidos_rows.append(nuevo)
            indices_ok.append(sheet_row)

        if not movidos_rows:
            raise ValueError(
                "No se pudo marcar ningún ítem (ya ingresados o el listado está desactualizado). "
                "Actualizá y reintentá."
            )

        df_fuera = df_fuera.drop(index=indices_ok).reset_index(drop=True)
        df_ing = pd.concat([df_ing, pd.DataFrame(movidos_rows)], ignore_index=True)

        escribir_ambas_hojas(df_fuera, df_ing, path)
        ActivosStore.get().refresh()

    return {
        "mensaje": f"Se marcó el regreso de {len(movidos_rows)} ítem(s).",
        "movidos": len(movidos_rows),
        "no_encontrados": no_encontrados,
        "fecha_regreso": fr_txt,
        "estado_al_ingreso": est,
    }


def restablecer_fuera(ids: list[str]) -> dict[str, Any]:
    """Devuelve filas de INGRESADO → FUERA (corrige ingreso erróneo / prueba)."""
    filas_pedidas = _parse_ids(ids, "i-")
    path = excel_path()
    with FileLock(path):
        df_fuera, df_ing = leer_ambas_hojas(path)
        movidos_rows: list[pd.Series] = []
        no_encontrados: list[str] = []
        indices_ok: list[int] = []

        for sheet_row in sorted(set(filas_pedidas)):
            if sheet_row < 0 or sheet_row >= len(df_ing):
                no_encontrados.append(f"i-{sheet_row}")
                continue
            row = df_ing.loc[sheet_row]
            if fila_pendiente(row):
                # Ya figura como fuera — no mover
                no_encontrados.append(f"i-{sheet_row}")
                continue

            nuevo = row.copy()
            nuevo["ESTADO"] = "FUERA_DE_PLANTA"
            nuevo["FECHA_REGRESO"] = ""
            nuevo["ESTADO_AL_INGRESO"] = ""
            nuevo["DIAS_FUERA"] = calcular_dias_fuera(nuevo.get("FECHA_SALIDA"), None)
            movidos_rows.append(nuevo)
            indices_ok.append(sheet_row)

        if not movidos_rows:
            raise ValueError(
                "No se pudo restablecer ningún ítem (ya están fuera o el listado está desactualizado). "
                "Actualizá y reintentá."
            )

        df_ing = df_ing.drop(index=indices_ok).reset_index(drop=True)
        df_fuera = pd.concat([df_fuera, pd.DataFrame(movidos_rows)], ignore_index=True)

        escribir_ambas_hojas(df_fuera, df_ing, path)
        ActivosStore.get().refresh()

    return {
        "mensaje": f"Se restableció a fuera de planta {len(movidos_rows)} ítem(s).",
        "movidos": len(movidos_rows),
        "no_encontrados": no_encontrados,
    }
