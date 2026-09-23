# -*- coding: utf-8 -*-
"""Operaciones de escritura — marcar regreso / restablecer a fuera.

DB es la unica fuente desde 2026-09-23 (panol.salida_activos).
Cuando ACTIVOS_DB_ENABLED=1, las escrituras van a MariaDB.
Fallback Excel solo si DB deshabilitada explicitamente.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from db import ACTIVOS_DB_ENABLED, get_connection
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


def _marcar_regreso_db(ids: list[int], fecha_regreso, estado_al_ingreso: str) -> dict[str, Any]:
    """DB path: actualiza salida_activos directamente."""
    fr = fecha_regreso
    est = str(estado_al_ingreso or "").strip().upper()
    fr_txt = fecha_str(fr)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            movidos = 0
            no_encontrados: list[str] = []
            for db_id in sorted(set(ids)):
                # Verificar que existe y esta fuera
                cur.execute(
                    "SELECT id, fecha_salida, estado FROM salida_activos WHERE id = %s",
                    (db_id,),
                )
                row = cur.fetchone()
                if not row:
                    no_encontrados.append(f"f-{db_id}")
                    continue
                if str(row["estado"]).strip().lower() != "fuera_de_planta":
                    no_encontrados.append(f"f-{db_id}")
                    continue
                fecha_salida = row["fecha_salida"]
                dias = calcular_dias_fuera(fecha_salida, fr)
                cur.execute(
                    """
                    UPDATE salida_activos
                    SET estado = 'ingresado_a_planta',
                        fecha_regreso = %s,
                        estado_al_ingreso = %s,
                        dias_fuera = %s,
                        actualizado_en = NOW()
                    WHERE id = %s
                    """,
                    (fr, est, dias, db_id),
                )
                if cur.rowcount:
                    movidos += 1
                else:
                    no_encontrados.append(f"f-{db_id}")
            if not movidos:
                conn.rollback()
                raise ValueError(
                    "No se pudo marcar ningún ítem (ya ingresados o el listado está desactualizado). "
                    "Actualizá y reintentá."
                )
            conn.commit()
            ActivosStore.get().refresh()
            return {
                "mensaje": f"Se marcó el regreso de {movidos} ítem(s).",
                "movidos": movidos,
                "no_encontrados": no_encontrados,
                "fecha_regreso": fr_txt,
                "estado_al_ingreso": est,
            }
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _restablecer_fuera_db(ids: list[int]) -> dict[str, Any]:
    """DB path: vuelve ingresado -> fuera."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            movidos = 0
            no_encontrados: list[str] = []
            for db_id in sorted(set(ids)):
                cur.execute(
                    "SELECT id, fecha_salida, estado FROM salida_activos WHERE id = %s",
                    (db_id,),
                )
                row = cur.fetchone()
                if not row:
                    no_encontrados.append(f"i-{db_id}")
                    continue
                if str(row["estado"]).strip().lower() != "ingresado_a_planta":
                    no_encontrados.append(f"i-{db_id}")
                    continue
                fecha_salida = row["fecha_salida"]
                dias = calcular_dias_fuera(fecha_salida, None)
                cur.execute(
                    """
                    UPDATE salida_activos
                    SET estado = 'fuera_de_planta',
                        fecha_regreso = NULL,
                        estado_al_ingreso = '',
                        dias_fuera = %s,
                        actualizado_en = NOW()
                    WHERE id = %s
                    """,
                    (dias, db_id),
                )
                if cur.rowcount:
                    movidos += 1
                else:
                    no_encontrados.append(f"i-{db_id}")
            if not movidos:
                conn.rollback()
                raise ValueError(
                    "No se pudo restablecer ningún ítem (ya están fuera o el listado está desactualizado). "
                    "Actualizá y reintentá."
                )
            conn.commit()
            ActivosStore.get().refresh()
            return {
                "mensaje": f"Se restableció a fuera de planta {movidos} ítem(s).",
                "movidos": movidos,
                "no_encontrados": no_encontrados,
            }
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass


def marcar_regreso(
    ids: list[str],
    fecha_regreso: str,
    estado_al_ingreso: str,
) -> dict[str, Any]:
    """Mueve filas de FUERA → INGRESADO."""
    filas_pedidas = _parse_ids(ids, "f-")
    fr = parse_fecha(fecha_regreso)
    if fr is None:
        raise ValueError("Fecha de ingreso inválida. Usá formato DD/MM/AAAA o AAAA-MM-DD.")
    est = str(estado_al_ingreso or "").strip().upper()
    if not est:
        raise ValueError("Indicá el estado / condición al ingresar a planta.")

    if ACTIVOS_DB_ENABLED:
        return _marcar_regreso_db(filas_pedidas, fr, est)

    # Fallback Excel solo si DB deshabilitada
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
    """Devuelve filas de INGRESADO → FUERA."""
    filas_pedidas = _parse_ids(ids, "i-")

    if ACTIVOS_DB_ENABLED:
        return _restablecer_fuera_db(filas_pedidas)

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
