# -*- coding: utf-8 -*-
"""Lógica de negocio Salidas (paralela al tab Registro de salidas del escritorio)."""

from __future__ import annotations

import logging
import threading
from datetime import date, datetime, timezone
from typing import Any

from config import data_path, historial_path, maestro_path, maestro_writable, PERSONAL_DB_ENABLED
from excel_io import (
    append_movimientos,
    fecha_sin_hora_str,
    guardar_maestro,
    nombre_mes,
    normalizar_orden,
    parse_fecha,
)
from firebase_sync import escribir_stock_item, estado_sync, pull_firestore_si_corresponde
from movimientos import a_registros, cargar_historial, filtrar_por_fecha
from store import SalidasStore

_save_lock = threading.Lock()
log = logging.getLogger("salidas.service")


def _store() -> SalidasStore:
    s = SalidasStore.get()
    s.ensure_loaded()
    s.require_loaded()
    return s


def health_payload() -> dict[str, Any]:
    s = SalidasStore.get()
    fb = estado_sync()
    common = {
        "archivo": s.archivo_ok,
        "path": s.path_maestro or str(maestro_path()),
        "path_escritura": str(data_path()),
        "path_historial": str(historial_path()),
        "maestro_writable": maestro_writable(),
        "firebase": fb,
    }
    if s._error_carga:
        return {
            "estado": "error",
            "detail": s._error_carga,
            **common,
        }
    if s.ultima_actualizacion is None:
        return {
            "estado": "cargando",
            **common,
        }
    return {
        "estado": "ok",
        "service": "salidas",
        "ultima_actualizacion": s.timestamp_iso(),
        **common,
    }


def get_catalogos() -> dict[str, Any]:
    s = _store()
    base_catalog = {
        **s.catalogos,
        "ultima_actualizacion": s.timestamp_iso(),
    }
    # Feature flag: when PERSONAL_DB_ENABLED=1, source sectores/operarios from MariaDB
    if PERSONAL_DB_ENABLED:
        return _catalogos_desde_db(base_catalog)
    return base_catalog


def _catalogos_desde_db(excel_catalog: dict[str, Any]) -> dict[str, Any]:
    """Query MariaDB areas (activo=1) and personal (activo=1) for catalog data."""
    if not PERSONAL_DB_ENABLED:
        return excel_catalog

    conn = None
    try:
        import sys
        from pathlib import Path as _Path
        _personal_dir = str(_Path(__file__).resolve().parent.parent / "personal")
        if _personal_dir not in sys.path:
            sys.path.insert(0, _personal_dir)
        from db import get_connection

        conn = get_connection()
        with conn.cursor() as cur:
            # Sectores = active areas sorted alphabetically
            cur.execute(
                "SELECT nombre FROM areas WHERE activo = 1 ORDER BY nombre ASC"
            )
            rows_areas = cur.fetchall()
            sectores = [r["nombre"] for r in rows_areas] if rows_areas else excel_catalog.get("sectores", [])

            # Operarios = active personal names (UPPER TRIM), sorted
            cur.execute(
                "SELECT nombre FROM personal WHERE activo = 1 ORDER BY nombre ASC"
            )
            rows_personal = cur.fetchall()
            operarios = [r["nombre"].strip().upper() for r in rows_personal] if rows_personal else excel_catalog.get("operarios", [])

        result = {
            **excel_catalog,
            "sectores": sectores,
            "operarios": operarios,
            "ultima_actualizacion": None,
        }
        # Preserve snapshot columns from Excel if DB query succeeds
        for key in ("tipos_comprobante", "operarios_proyectos", "sector_operarios"):
            if key in excel_catalog:
                result[key] = excel_catalog[key]
        result["ultima_actualizacion"] = datetime.now(timezone.utc).isoformat()
        return result
    except Exception:
        # Fallback to Excel catalog if DB query fails
        return excel_catalog
    finally:
        if conn:
            conn.close()


def buscar_articulo(codigo: str) -> dict[str, Any]:
    s = _store()
    art = s.articulo_dict(codigo)
    if not art:
        raise ValueError(f"No se encontró el código {codigo.strip().upper()} en el maestro.")
    return art


def proyectar_stock(
    codigo: str,
    cantidad: float,
    *,
    pendientes: list[dict[str, Any]] | None = None,
    es_devolucion: bool = False,
) -> dict[str, Any]:
    """Proyecta stock tras esta línea + pendientes de la carga actual (cliente)."""
    s = _store()
    art = s.articulo_dict(codigo)
    if not art:
        raise ValueError(f"No se encontró el código {codigo.strip().upper()} en el maestro.")
    try:
        cant_in = float(cantidad)
    except (TypeError, ValueError) as e:
        raise ValueError("Cantidad inválida.") from e
    cant = -abs(cant_in) if es_devolucion else abs(cant_in)

    base = float(art["stock_actual"])
    for p in pendientes or []:
        if str(p.get("codigo") or p.get("CODIGO") or "").strip().upper() == art["codigo"]:
            try:
                base -= float(p.get("cantidad") if "cantidad" in p else p.get("CANTIDAD") or 0)
            except (TypeError, ValueError):
                pass
    proyectado = base - cant
    return {
        "codigo": art["codigo"],
        "descripcion": art["descripcion"],
        "ubicacion": art["ubicacion"],
        "precio_unitario": art["precio_unitario"],
        "stock_actual": art["stock_actual"],
        "stock_base_con_pendientes": base,
        "cantidad": cant,
        "stock_proyectado": proyectado,
        "alerta_negativo": proyectado < 0 and not es_devolucion,
        "es_devolucion": es_devolucion,
    }


def _construir_fila(
    *,
    fecha_d: date,
    codigo: str,
    descripcion: str,
    ubicacion: str,
    cantidad: float,
    tipo_comprobante: str,
    numero_orden: Any,
    maquina: str,
    precio: float,
    operario: str,
    sector: str,
    es_devolucion: bool,
) -> dict[str, Any]:
    monto = round(abs(cantidad) * abs(precio), 2)
    desc = str(descripcion or "").strip().upper()
    if es_devolucion and not desc.startswith("(DEVOLUCIÓN)"):
        desc = f"(DEVOLUCIÓN) {desc}".strip()
    fila = {
        "FECHA": fecha_sin_hora_str(fecha_d),
        "MES": nombre_mes(fecha_d.month),
        "AÑO": int(fecha_d.year),
        "CODIGO": str(codigo).strip().upper(),
        "DESCRIPCION": desc,
        "UBICACION": str(ubicacion or "").strip().upper(),
        "CANTIDAD": float(cantidad),
        "TIPO_COMPROBANTE": str(tipo_comprobante or "").strip().upper(),
        "NUMERO_ORDEN": normalizar_orden(numero_orden),
        "MAQUINA_SITIO": str(maquina or "").strip().upper(),
        "PRECIO_UNITARIO": float(precio),
        "MONTO_TOTAL_SALIDA": -monto if es_devolucion else monto,
        "OPERARIO": str(operario or "").strip().upper(),
        "SECTOR": str(sector or "").strip().upper(),
    }
    for k, v in list(fila.items()):
        if k in ("MES", "AÑO", "NUMERO_ORDEN", "PRECIO_UNITARIO", "MONTO_TOTAL_SALIDA", "CANTIDAD"):
            continue
        if isinstance(v, str):
            fila[k] = v.upper()
    return fila


def _validar_item(item: dict[str, Any], *, es_devolucion: bool) -> dict[str, Any]:
    codigo = str(item.get("codigo") or "").strip().upper()
    if not codigo:
        raise ValueError("Cada ítem requiere código.")
    try:
        cant_in = float(str(item.get("cantidad", "")).replace(",", "."))
    except (TypeError, ValueError) as e:
        raise ValueError(f"Cantidad inválida para {codigo}.") from e
    if cant_in == 0:
        raise ValueError(f"Cantidad no puede ser 0 ({codigo}).")
    cant = -abs(cant_in) if es_devolucion or cant_in < 0 else abs(cant_in)
    tipo = str(item.get("tipo_comprobante") or "").strip()
    orden = item.get("numero_orden")
    sector = str(item.get("sector") or "").strip()
    operario = str(item.get("operario") or "").strip()
    if not tipo or orden is None or str(orden).strip() == "" or not sector or not operario:
        raise ValueError(
            f"Faltan datos obligatorios (comprobante, orden, sector, operario) en {codigo}."
        )
    fecha_d = parse_fecha(item.get("fecha"))
    if fecha_d is None:
        raise ValueError(f"Fecha inválida en {codigo}. Usá AAAA-MM-DD o DD/MM/AAAA.")
    permitir_neg = bool(item.get("permitir_stock_negativo"))
    proy = proyectar_stock(
        codigo,
        cant,
        pendientes=[],  # la proyección batch se hace abajo
        es_devolucion=cant < 0,
    )
    return {
        "codigo": codigo,
        "cantidad": cant,
        "tipo_comprobante": tipo,
        "numero_orden": orden,
        "sector": sector,
        "operario": operario,
        "maquina": str(item.get("maquina") or item.get("maquina_sitio") or "").strip(),
        "fecha_d": fecha_d,
        "permitir_stock_negativo": permitir_neg,
        "precio_override": item.get("precio_unitario"),
        "proy": proy,
    }


def confirmar_batch(
    items: list[dict[str, Any]],
    *,
    es_devolucion: bool = False,
    forzar_negativos: bool = False,
) -> dict[str, Any]:
    """Confirma carga pendiente: descuenta stock, escribe Excel prueba, sync Firebase."""
    if not items:
        raise ValueError("No hay ítems para confirmar.")

    s = _store()
    validados = [_validar_item(it, es_devolucion=es_devolucion) for it in items]

    # Proyección acumulada por código (como pendientes del escritorio)
    acum: dict[str, float] = {}
    alertas: list[str] = []
    for v in validados:
        cod = v["codigo"]
        art = s.articulo_dict(cod)
        if not art:
            raise ValueError(f"No se encontró el código {cod} en el maestro.")
        base = acum.get(cod, float(art["stock_actual"]))
        nuevo = base - float(v["cantidad"])
        if nuevo < 0 and v["cantidad"] > 0 and not (forzar_negativos or v["permitir_stock_negativo"]):
            alertas.append(cod)
        acum[cod] = nuevo

    if alertas:
        raise ValueError(
            "Stock proyectado negativo para: "
            + ", ".join(alertas)
            + ". Confirmá con forzar_negativos=true o permitir_stock_negativo por ítem "
            "(misma advertencia que el escritorio)."
        )

    filas: list[dict[str, Any]] = []
    fechas: list[date] = []
    sync_payload: list[dict[str, Any]] = []

    with _save_lock:
        # Aplicar stocks
        for v in validados:
            art = s.articulo_dict(v["codigo"])
            assert art is not None
            precio = art["precio_unitario"]
            if v["precio_override"] is not None:
                try:
                    precio = float(v["precio_override"])
                except (TypeError, ValueError):
                    pass
            actual = float(art["stock_actual"])
            nuevo_stock = actual - float(v["cantidad"])
            actualizado = s.set_stock(v["codigo"], nuevo_stock)
            fila = _construir_fila(
                fecha_d=v["fecha_d"],
                codigo=v["codigo"],
                descripcion=art["descripcion"],
                ubicacion=art["ubicacion"],
                cantidad=float(v["cantidad"]),
                tipo_comprobante=v["tipo_comprobante"],
                numero_orden=v["numero_orden"],
                maquina=v["maquina"],
                precio=precio,
                operario=v["operario"],
                sector=v["sector"],
                es_devolucion=float(v["cantidad"]) < 0,
            )
            filas.append(fila)
            fechas.append(v["fecha_d"])
            sync_payload.append(
                {
                    "codigo": actualizado["codigo"],
                    "stock": actualizado["stock_actual"],
                    "desc": actualizado["descripcion"],
                    "ubicacion": actualizado["ubicacion"],
                    "categoria": actualizado["categoria"],
                }
            )

        guardar_maestro(s.hojas, s.config_df)
        paths = append_movimientos(filas, fechas)
        if not maestro_writable():
            log.info(
                "Maestro solo lectura (%s). Movimientos escritos en: %s",
                s.path_maestro,
                paths,
            )
        s.ultima_actualizacion = datetime.now(timezone.utc)

    fb_ok = 0
    for p in sync_payload:
        if escribir_stock_item(
            p["codigo"], p["stock"], p["desc"], p["ubicacion"], p["categoria"]
        ):
            fb_ok += 1
        else:
            # caché local ya se actualizó dentro de escribir_stock_item parcialmente;
            # si no hay Firebase, igual quedó en SQLite
            pass

    return {
        "mensaje": f"Carga confirmada: {len(filas)} movimiento(s).",
        "movimientos": len(filas),
        "archivos": paths,
        "firebase_escritos": fb_ok,
        "filas": filas,
        "ultima_actualizacion": s.timestamp_iso(),
    }


def confirmar_salida(body: dict[str, Any]) -> dict[str, Any]:
    items = body.get("items") or []
    if not isinstance(items, list):
        raise ValueError("items debe ser una lista.")
    return confirmar_batch(
        items,
        es_devolucion=False,
        forzar_negativos=bool(body.get("forzar_negativos")),
    )


def confirmar_devolucion(body: dict[str, Any]) -> dict[str, Any]:
    items = body.get("items") or []
    if not isinstance(items, list):
        raise ValueError("items debe ser una lista.")
    # Forzar signo negativo
    norm = []
    for it in items:
        if not isinstance(it, dict):
            continue
        d = dict(it)
        try:
            d["cantidad"] = -abs(float(str(d.get("cantidad", 0)).replace(",", ".")))
        except (TypeError, ValueError):
            pass
        norm.append(d)
    return confirmar_batch(
        norm,
        es_devolucion=True,
        forzar_negativos=True,
    )


def listar_movimientos(
    *,
    desde: str | None = None,
    hasta: str | None = None,
    limite: int = 100,
) -> dict[str, Any]:
    df = cargar_historial()
    df = filtrar_por_fecha(df, desde, hasta)
    return {
        "total": int(len(df)),
        "items": a_registros(df, limite=limite),
        "columnas": list(df.columns) if not df.empty else [],
    }


def refresh_maestro() -> dict[str, Any]:
    s = SalidasStore.get()
    ts = s.refresh()
    return {
        "mensaje": "Maestro recargado.",
        "timestamp": ts.astimezone().isoformat(),
        "path": s.path_maestro,
    }


def sync_firebase_ahora() -> dict[str, Any]:
    return pull_firestore_si_corresponde(forzar=True)
