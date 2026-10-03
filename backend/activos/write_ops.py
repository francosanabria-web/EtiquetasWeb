# -*- coding: utf-8 -*-
"""Operaciones de escritura — crear/editar salida, marcar regreso / restablecer a fuera.

DB es la unica fuente desde 2026-09-23 (panol.salida_activos).
Cuando ACTIVOS_DB_ENABLED=1, las escrituras van a MariaDB.
Fallback Excel solo si DB deshabilitada explicitamente.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import pandas as pd

from config import excel_path
from db import ACTIVOS_DB_ENABLED, get_connection
from excel_io import (
    FileLock,
    calcular_dias_fuera,
    calcular_fingerprint,
    escribir_ambas_hojas,
    fecha_str,
    fila_pendiente,
    leer_ambas_hojas,
    parse_fecha,
)
from store import ActivosStore

log = logging.getLogger("activos")

# Validación de longitudes máximas
_MAX_LEN = {
    "equipo": 200,
    "proveedor": 150,
    "observaciones": 500,
    "sector": 100,
    "codigo": 40,
    "nro_serie": 40,
    "numero_remito": 40,
    "numero_pedido": 40,
    "numero_oc": 40,
}


def _truncar(val: object, max_len: int) -> str:
    s = str(val).strip()
    return s[:max_len] if len(s) > max_len else s


def _validar_campo_requerido(val: object, nombre: str) -> str:
    s = str(val).strip() if val is not None else ""
    if not s:
        raise ValueError(f"El campo '{nombre}' es obligatorio.")
    return s


def _cantidad(val: object) -> int:
    try:
        if val is None:
            return 1
        s = str(val).strip().replace(",", ".")
        if not s or s.lower() in ("nan", "-"):
            return 1
        return max(1, int(float(s)))
    except (TypeError, ValueError):
        return 1


def _hoy_iso() -> str:
    return date.today().isoformat()


def _parsear_fecha_input(val: object) -> date:
    """Parsea fecha desde input (DD/MM/YYYY o YYYY-MM-DD)."""
    d = parse_fecha(val)
    if d is None:
        raise ValueError("Fecha inválida. Usá formato DD/MM/AAAA o AAAA-MM-DD.")
    return d


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


# ──────────────────────────────────────────────────────────
# Crear nueva salida
# ──────────────────────────────────────────────────────────

def _crear_salida_db(data: dict[str, Any]) -> dict[str, Any]:
    """DB path: inserta nueva fila en salida_activos."""
    equipo = _validar_campo_requerido(data.get("equipo"), "equipo")[:200]
    sector = _validar_campo_requerido(data.get("sector"), "sector")[:100]
    proveedor = _validar_campo_requerido(data.get("proveedor"), "proveedor")[:150]
    numero_remito = _validar_campo_requerido(data.get("numero_remito"), "numero_remito")[:40]

    codigo = _truncar(data.get("codigo"), 40) if data.get("codigo") else ""
    nro_serie = _truncar(data.get("nro_serie"), 40) if data.get("nro_serie") else ""
    numero_pedido = _truncar(data.get("numero_pedido"), 40) if data.get("numero_pedido") else ""
    numero_oc = _truncar(data.get("numero_oc"), 40) if data.get("numero_oc") else ""
    observaciones = _truncar(data.get("observaciones"), 500) if data.get("observaciones") else ""
    cantidad = _cantidad(data.get("cantidad"))

    fecha_salida = _parsear_fecha_input(data.get("fecha_salida") or _hoy_iso())
    fecha_salida_str = fecha_salida.isoformat()
    dias_fuera = calcular_dias_fuera(fecha_salida, None)
    fecha = fecha_salida

    fingerprint = calcular_fingerprint(
        codigo=codigo,
        numero_remito=numero_remito,
        numero_pedido=numero_pedido,
        numero_oc=numero_oc,
        nro_serie=nro_serie,
        fecha_salida=fecha_salida_str,
        equipo=equipo,
    )

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Verificar duplicado por fingerprint
            cur.execute(
                "SELECT id FROM salida_activos WHERE fingerprint = %s",
                (fingerprint,),
            )
            dup = cur.fetchone()
            if dup:
                raise ValueError("Ya existe un activo con esos datos (duplicado).")

            cur.execute(
                """
                INSERT INTO salida_activos
                  (fecha, equipo, codigo, descripcion, sector, cantidad,
                   nro_serie, numero_pedido, numero_oc, numero_remito,
                   proveedor, fecha_salida, fecha_regreso,
                   estado_al_ingreso, observaciones, dias_fuera,
                   estado, fingerprint, creado_en, actualizado_en)
                VALUES
                  (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                   %s, %s, NULL, %s, %s, %s, %s, %s, NOW(), NOW())
                """,
                (
                    fecha, equipo, codigo, equipo, sector, cantidad,
                    nro_serie, numero_pedido, numero_oc, numero_remito,
                    proveedor, fecha_salida, "",
                    observaciones, dias_fuera,
                    "fuera_de_planta", fingerprint,
                ),
            )
            new_id = cur.lastrowid
            conn.commit()
            ActivosStore.get().refresh()
            return {"mensaje": "Salida creada correctamente.", "id": new_id, "fingerprint": fingerprint}
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


def crear_salida(data: dict[str, Any]) -> dict[str, Any]:
    """Crea una nueva salida de activo.

    Campos requeridos: equipo, sector, proveedor, numero_remito.
    Opcionales: codigo, nro_serie, numero_pedido, numero_oc, cantidad, fecha_salida, observaciones.
    """
    fecha_input = data.get("fecha_salida") or _hoy_iso()
    fecha_salida = _parsear_fecha_input(fecha_input)
    data["fecha_salida"] = fecha_salida.isoformat()
    return _crear_salida_db(data)


# ──────────────────────────────────────────────────────────
# Editar activo existente
# ──────────────────────────────────────────────────────────

def _editar_activo_db(db_id: int, data: dict[str, Any]) -> dict[str, Any]:
    """DB path: actualiza fila existente en salida_activos.

    No permite cambiar estado ni fecha_regreso (para eso ya existen marcar-regreso/restablecer).
    Recalcula dias_fuera si cambia fecha_salida, recalcula fingerprint, valida duplicado.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, equipo, sector, proveedor, codigo, nro_serie, "
                "numero_pedido, numero_oc, numero_remito, cantidad, fecha_salida, "
                "observaciones, dias_fuera, estado, fingerprint "
                "FROM salida_activos WHERE id = %s",
                (db_id,),
            )
            row = cur.fetchone()
            if not row:
                raise ValueError(f"No existe el activo con id {db_id}.")

            old_values = {
                "equipo": row.get("equipo", ""),
                "sector": row.get("sector", ""),
                "proveedor": row.get("proveedor", ""),
                "codigo": row.get("codigo", ""),
                "nro_serie": row.get("nro_serie", ""),
                "numero_pedido": row.get("numero_pedido", ""),
                "numero_oc": row.get("numero_oc", ""),
                "numero_remito": row.get("numero_remito", ""),
                "cantidad": row.get("cantidad", 1),
                "fecha_salida": row.get("fecha_salida"),
                "observaciones": row.get("observaciones", ""),
                "dias_fuera": row.get("dias_fuera", 0),
                "fingerprint": row.get("fingerprint", ""),
            }

            # Leer valores nuevos (o mantener los actuales)
            nuevo_equipo = _truncar(data.get("equipo", old_values["equipo"]), 200) if data.get("equipo") is not None else old_values["equipo"]
            nuevo_sector = _truncar(data.get("sector", old_values["sector"]), 100) if data.get("sector") is not None else old_values["sector"]
            nuevo_proveedor = _truncar(data.get("proveedor", old_values["proveedor"]), 150) if data.get("proveedor") is not None else old_values["proveedor"]
            nuevo_codigo = _truncar(data.get("codigo", old_values["codigo"]), 40) if data.get("codigo") is not None else old_values["codigo"]
            nuevo_nro_serie = _truncar(data.get("nro_serie", old_values["nro_serie"]), 40) if data.get("nro_serie") is not None else old_values["nro_serie"]
            nuevo_numero_pedido = _truncar(data.get("numero_pedido", old_values["numero_pedido"]), 40) if data.get("numero_pedido") is not None else old_values["numero_pedido"]
            nuevo_numero_oc = _truncar(data.get("numero_oc", old_values["numero_oc"]), 40) if data.get("numero_oc") is not None else old_values["numero_oc"]
            nuevo_numero_remito = _truncar(data.get("numero_remito", old_values["numero_remito"]), 40) if data.get("numero_remito") is not None else old_values["numero_remito"]
            nueva_observaciones = _truncar(data.get("observaciones", old_values["observaciones"]), 500) if data.get("observaciones") is not None else old_values["observaciones"]

            # Validar campos obligatorios si se proveen
            _validar_campo_requerido(nuevo_equipo, "equipo")
            _validar_campo_requerido(nuevo_sector, "sector")
            _validar_campo_requerido(nuevo_proveedor, "proveedor")
            _validar_campo_requerido(nuevo_numero_remito, "numero_remito")

            cantidad = _cantidad(data.get("cantidad", old_values["cantidad"])) if data.get("cantidad") is not None else old_values["cantidad"]

            fecha_salida_old = old_values["fecha_salida"]
            if isinstance(fecha_salida_old, date):
                fecha_salida_str_old = fecha_salida_old.isoformat()
            else:
                fecha_salida_str_old = str(fecha_salida_old)

            if data.get("fecha_salida") is not None:
                nueva_fecha_salida = _parsear_fecha_input(data["fecha_salida"])
            else:
                nueva_fecha_salida = fecha_salida_old

            nueva_fecha_salida_str = nueva_fecha_salida.isoformat()
            nuevo_dias_fuera = calcular_dias_fuera(nueva_fecha_salida, None)

            # Calcular nuevo fingerprint
            nuevo_fingerprint = calcular_fingerprint(
                codigo=nuevo_codigo,
                numero_remito=nuevo_numero_remito,
                numero_pedido=nuevo_numero_pedido,
                numero_oc=nuevo_numero_oc,
                nro_serie=nuevo_nro_serie,
                fecha_salida=nueva_fecha_salida_str,
                equipo=nuevo_equipo,
            )

            # Verificar duplicado (excluyendo este id)
            if nuevo_fingerprint != old_values["fingerprint"]:
                cur.execute(
                    "SELECT id FROM salida_activos WHERE fingerprint = %s AND id != %s",
                    (nuevo_fingerprint, db_id),
                )
                dup = cur.fetchone()
                if dup:
                    raise ValueError("Ya existe un activo con esos datos (duplicado).")

            # Log old vs new
            new_values = {
                "equipo": nuevo_equipo,
                "sector": nuevo_sector,
                "proveedor": nuevo_proveedor,
                "codigo": nuevo_codigo,
                "nro_serie": nuevo_nro_serie,
                "numero_pedido": nuevo_numero_pedido,
                "numero_oc": nuevo_numero_oc,
                "numero_remito": nuevo_numero_remito,
                "cantidad": cantidad,
                "fecha_salida": nueva_fecha_salida_str,
                "observaciones": nueva_observaciones,
                "dias_fuera": nuevo_dias_fuera,
                "fingerprint": nuevo_fingerprint,
            }
            changed = {k: (old_values[k], new_values[k]) for k in old_values if old_values[k] != new_values[k]}
            if changed:
                log.info("Editando activo id=%d cambios: %s", db_id, changed)

            cur.execute(
                """
                UPDATE salida_activos
                SET equipo = %s, sector = %s, proveedor = %s, codigo = %s,
                    nro_serie = %s, numero_pedido = %s, numero_oc = %s,
                    numero_remito = %s, cantidad = %s, fecha_salida = %s,
                    fecha = %s, observaciones = %s, dias_fuera = %s,
                    fingerprint = %s, actualizado_en = NOW()
                WHERE id = %s
                """,
                (
                    nuevo_equipo, nuevo_sector, nuevo_proveedor, nuevo_codigo,
                    nuevo_nro_serie, nuevo_numero_pedido, nuevo_numero_oc,
                    nuevo_numero_remito, cantidad, nueva_fecha_salida,
                    nueva_fecha_salida, nueva_observaciones, nuevo_dias_fuera,
                    nuevo_fingerprint, db_id,
                ),
            )
            conn.commit()
            ActivosStore.get().refresh()
            return {"mensaje": "Activo actualizado correctamente."}
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


def editar_activo(db_id: int, data: dict[str, Any]) -> dict[str, Any]:
    """Edita un activo existente.

    Todos los campos son opcionales en el body. Si se proveen, los campos
    obligatorios (equipo, sector, proveedor, numero_remito) no pueden quedar vacíos.
    No permite cambiar estado ni fecha_regreso.
    """
    return _editar_activo_db(db_id, data)
