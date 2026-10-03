# -*- coding: utf-8 -*-
"""Lógica de negocio Salidas - v4 volantazo (2026-09-16).

Cambios v4:
 - DB directo con dual-write (SALIDAS_DB_ENABLED + SALIDAS_EXCEL_BACKUP)
 - Atenciones simplificada: fecha, con_retiro, observaciones(500)
 - Diario extraible de historial y enviable por mail
 - Remito / Maestro search helpers
"""

from __future__ import annotations

import logging
import threading
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

def _dec_float(v: Any) -> Any:
    """Convierte Decimal a float para JSON serializable; deja otros tipos."""
    if isinstance(v, Decimal):
        try:
            return float(v)
        except Exception:
            return str(v)
    return v

from config import (
    ATENCIONES_EXPORT_MAX_ROWS,
    FIREBASE_WRITE_ENABLED,
    SALIDAS_DB_ENABLED,
    SALIDAS_EXCEL_BACKUP,
    data_path,
    historial_path,
    maestro_path,
    maestro_writable,
    PERSONAL_DB_ENABLED,
)
from excel_io import (
    append_movimientos,
    atenciones_to_csv_bytes,
    fecha_sin_hora_str,
    guardar_maestro,
    nombre_mes,
    normalizar_orden,
    parse_fecha,
    workbook_atenciones,
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
        "db_enabled": SALIDAS_DB_ENABLED,
        "excel_backup": SALIDAS_EXCEL_BACKUP,
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
    if PERSONAL_DB_ENABLED:
        return _catalogos_desde_db(base_catalog)
    return base_catalog


def _catalogos_desde_db(excel_catalog: dict[str, Any]) -> dict[str, Any]:
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
            cur.execute("SELECT nombre FROM areas WHERE activo = 1 ORDER BY nombre ASC")
            rows_areas = cur.fetchall()
            sectores = [r["nombre"] for r in rows_areas] if rows_areas else excel_catalog.get("sectores", [])
            cur.execute("SELECT nombre FROM personal WHERE activo = 1 ORDER BY nombre ASC")
            rows_personal = cur.fetchall()
            operarios = [r["nombre"].strip().upper() for r in rows_personal] if rows_personal else excel_catalog.get("operarios", [])
        result = {
            **excel_catalog,
            "sectores": sectores,
            "operarios": operarios,
            "ultima_actualizacion": None,
        }
        for key in ("tipos_comprobante", "operarios_proyectos", "sector_operarios"):
            if key in excel_catalog:
                result[key] = excel_catalog[key]
        result["ultima_actualizacion"] = datetime.now(timezone.utc).isoformat()
        return result
    except Exception:
        return excel_catalog
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def buscar_articulo(codigo: str) -> dict[str, Any]:
    cod = str(codigo or "").strip().upper()
    if not cod:
        raise ValueError("Código vacío.")
    # 1) Fuente primaria: maestro_stock (MariaDB panol) — libera Firestore/Excel para salidas
    try:
        from store_sql import maestro_get_by_codigo

        art_db = maestro_get_by_codigo(cod)
        if art_db:
            # Ensure alias key exists for frontend
            if "alias" not in art_db:
                art_db["alias"] = None
            return art_db
    except Exception as e:
        log.warning("buscar_articulo DB fallback para %s: %s", cod, e)
    # 2) Fallback Excel solo si DB no disponible o registro no migrado (transición)
    s = _store()
    art = s.articulo_dict(cod)
    if not art:
        raise ValueError(f"No se encontró el código {cod} en el maestro.")
    return art


def buscar_articulos(q: str, limite: int = 20) -> list[dict[str, Any]]:
    """Búsqueda maestro para modal 'Maestro de stock' (filtra código/descripción, case-insensitive). Fuente primaria: maestro_stock DB."""
    # 1) Intentar maestro_stock DB (exclusivo, libera Firestore/Excel)
    try:
        from store_sql import maestro_search

        res_db = maestro_search(q, limite)
        # None = DB error / tabla faltante -> fallback; [] = sin resultados pero query válida -> retornar vacío (DB es autoridad)
        if res_db is not None:
            return res_db
    except Exception as e:
        log.warning("buscar_articulos DB fallback q=%s: %s", q, e)
    # 2) Fallback Excel solo si DB no disponible (transición)
    s = _store()
    df = s.df_articulos()
    if df is None or df.empty:
        return []
    qq = str(q or "").strip().upper()
    if not qq:
        head = df.head(max(1, min(50, int(limite or 20))))
        out: list[dict[str, Any]] = []
        for _, row in head.iterrows():
            try:
                codigo = str(row.get("codigo") or row.get("CODIGO") or "").strip().upper()
                if not codigo:
                    continue
                art = s.articulo_dict(codigo)
                if art:
                    out.append(art)
            except Exception:
                continue
        return out
    try:
        mask = df["codigo"].astype(str).str.upper().str.contains(qq, na=False)
        from excel_io import col_descripcion

        c_desc = col_descripcion(df)
        if c_desc and c_desc in df.columns:
            mask = mask | df[c_desc].astype(str).str.upper().str.contains(qq, na=False)
        filtered = df[mask].head(max(1, min(100, int(limite or 20))))
        out = []
        for _, row in filtered.iterrows():
            try:
                codigo = str(row.get("codigo") or "").strip().upper()
                if not codigo:
                    continue
                art = s.articulo_dict(codigo)
                if art:
                    out.append(art)
            except Exception:
                continue
        return out
    except Exception:
        out = []
        for _, row in df.iterrows():
            if len(out) >= int(limite or 20):
                break
            try:
                codigo = str(row.get("codigo") or "").strip().upper()
                desc = str(row.get("descripcion") or row.get("DESCRIPCION") or "").upper()
                if qq in codigo or qq in desc:
                    art = s.articulo_dict(codigo)
                    if art:
                        out.append(art)
            except Exception:
                continue
        return out


def actualizar_alias(codigo: str, alias: str | None, realizado_por: str | None = None) -> dict[str, Any]:
    """Actualiza alias en maestro_stock y sincroniza a Firestore (bidirectional).

    - Valida alias max 300 via store_sql.
    - Luego push a Firestore via firebase_sync.escribir_alias (best-effort).
    Returns updated articulo dict.
    """
    cod = str(codigo or "").strip().upper()
    if not cod:
        raise ValueError("codigo requerido.")
    # alias normalization done in store_sql, but pre-validate here
    alias_norm: str | None = None
    if alias is not None:
        s = str(alias).strip()
        if s == "":
            alias_norm = None
        else:
            if len(s) > 300:
                raise ValueError("alias max 300 caracteres.")
            alias_norm = s
    try:
        from store_sql import maestro_update_alias
    except Exception as e:
        raise RuntimeError(f"No se pudo cargar maestro_update_alias: {e}") from e
    row = maestro_update_alias(cod, alias_norm, realizado_por=realizado_por)
    # Firestore push (bidirectional): DB -> Firestore
    try:
        from firebase_sync import escribir_alias

        # Best-effort; don't fail alias update if Firestore down
        escribir_alias(cod, alias_norm)
    except Exception as e:
        log.warning("actualizar_alias Firestore push failed %s -> %r: %s", cod, alias_norm, e)
    return row


def proyectar_stock(
    codigo: str,
    cantidad: float,
    *,
    pendientes: list[dict[str, Any]] | None = None,
    es_devolucion: bool = False,
) -> dict[str, Any]:
    art = buscar_articulo(codigo)
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
        raise ValueError(f"Faltan datos obligatorios (comprobante, orden, sector, operario) en {codigo}.")
    fecha_d = parse_fecha(item.get("fecha"))
    if fecha_d is None:
        raise ValueError(f"Fecha inválida en {codigo}. Usá AAAA-MM-DD o DD/MM/AAAA.")
    permitir_neg = bool(item.get("permitir_stock_negativo"))
    proy = proyectar_stock(codigo, cant, pendientes=[], es_devolucion=cant < 0)
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


def _fila_para_db(fila: dict[str, Any], fecha_d: date, precio: float, operario: str, sector: str, creado_por: str | None) -> dict[str, Any]:
    """Convierte fila Excel-like a dict para store_sql.historial_crear."""
    return {
        "fecha": fecha_d,
        "mes": fila.get("MES"),
        "anio": fila.get("AÑO"),
        "codigo": fila.get("CODIGO"),
        "descripcion": fila.get("DESCRIPCION"),
        "ubicacion": fila.get("UBICACION"),
        "cantidad": fila.get("CANTIDAD"),
        "tipo_comprobante": fila.get("TIPO_COMPROBANTE"),
        "numero_orden": fila.get("NUMERO_ORDEN"),
        "maquina_sitio": fila.get("MAQUINA_SITIO"),
        "precio_unitario": fila.get("PRECIO_UNITARIO"),
        "monto_total": fila.get("MONTO_TOTAL_SALIDA"),
        "operario_nombre": fila.get("OPERARIO"),
        "sector_nombre": fila.get("SECTOR"),
        "es_devolucion": float(fila.get("CANTIDAD") or 0) < 0,
        "creado_por": creado_por,
        "operario_id": None,
        "area_id": None,
    }


def confirmar_batch(
    items: list[dict[str, Any]],
    *,
    es_devolucion: bool = False,
    forzar_negativos: bool = False,
) -> dict[str, Any]:
    if not items:
        raise ValueError("No hay ítems para confirmar.")
    validados = [_validar_item(it, es_devolucion=es_devolucion) for it in items]
    # Validación stock usando fuente primaria maestro_stock DB (libera Excel/Firestore)
    acum: dict[str, float] = {}
    alertas: list[str] = []
    for v in validados:
        cod = v["codigo"]
        art = buscar_articulo(cod)
        if not art:
            raise ValueError(f"No se encontró el código {cod} en el maestro.")
        base = acum.get(cod, float(art["stock_actual"]))
        nuevo = base - float(v["cantidad"])
        if nuevo < 0 and v["cantidad"] > 0 and not (forzar_negativos or v["permitir_stock_negativo"]):
            alertas.append(cod)
        acum[cod] = nuevo
    if alertas:
        raise ValueError("Stock proyectado negativo para: " + ", ".join(alertas) + ". Confirmá con forzar_negativos=true o permitir_stock_negativo por ítem (misma advertencia que el escritorio).")
    filas: list[dict[str, Any]] = []
    fechas: list[date] = []
    sync_payload: list[dict[str, Any]] = []
    filas_db: list[dict[str, Any]] = []
    with _save_lock:
        for v in validados:
            art = buscar_articulo(v["codigo"])
            assert art is not None
            precio = art["precio_unitario"]
            if v["precio_override"] is not None:
                try:
                    precio = float(v["precio_override"])
                except (TypeError, ValueError):
                    pass
            # Actualización de stock: DB maestro_stock es autoridad; Excel solo si SALIDAS_DB_ENABLED=0
            if SALIDAS_DB_ENABLED:
                actual = float(art["stock_actual"])
                nuevo_stock = actual - float(v["cantidad"])
                # No mutar Excel; mock actualizado para sync_payload y fila
                actualizado = {
                    "codigo": art["codigo"],
                    "stock_actual": nuevo_stock,
                    "descripcion": art["descripcion"],
                    "ubicacion": art["ubicacion"],
                    "categoria": art.get("categoria", "GENERAL"),
                }
            else:
                s_local = _store()
                actual = float(art["stock_actual"])
                nuevo_stock = actual - float(v["cantidad"])
                actualizado = s_local.set_stock(v["codigo"], nuevo_stock)
                # Releer art actualizado para descripcion consistente si Excel tenía otro precio
                art = s_local.articulo_dict(v["codigo"]) or art
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
            filas_db.append(_fila_para_db(fila, v["fecha_d"], precio, v["operario"], v["sector"], creado_por=v["operario"]))
            sync_payload.append({"codigo": actualizado["codigo"], "stock": actualizado["stock_actual"], "desc": actualizado["descripcion"], "ubicacion": actualizado["ubicacion"], "categoria": actualizado["categoria"]})
        # Persistencia: DB directo si flag, sino Excel, con backup opcional
        s_store = _store()
        paths: list[str] = []
        if SALIDAS_DB_ENABLED:
            try:
                from store_sql import historial_crear_batch
                ids = historial_crear_batch(filas_db)
                log.info("Salidas DB: %s movimientos insertados ids=%s", len(ids), ids[:5])
                paths.append(f"mariadb:salida_historial ({len(ids)} filas)")
            except Exception as e:
                log.exception("Error escribiendo a MariaDB, fallback a Excel si backup activo: %s", e)
                if not SALIDAS_EXCEL_BACKUP:
                    raise RuntimeError(f"No se pudo guardar en base de datos: {e}") from e
            # Decrementar stock en maestro_stock (autoridad exclusiva, libera Firestore/Excel)
            try:
                from store_sql import maestro_decrement_stock

                for v in validados:
                    try:
                        ok = maestro_decrement_stock(v["codigo"], float(v["cantidad"]))
                        if not ok:
                            log.warning("maestro_decrement_stock no afectó fila para %s (¿código inexistente en maestro_stock?)", v["codigo"])
                    except Exception as e:
                        log.warning("Error decrementando stock %s: %s", v["codigo"], e)
            except Exception as e:
                log.warning("Error batch decrement stock maestro_stock: %s", e)
            if SALIDAS_EXCEL_BACKUP:
                try:
                    guardar_maestro(s_store.hojas, s_store.config_df)
                    paths_excel = append_movimientos(filas, fechas)
                    paths.extend(paths_excel)
                except Exception as e:
                    log.warning("Backup Excel fallo (no critico): %s", e)
            else:
                # DB es autoridad stock; no tocar Excel maestro (Excel queda solo lectura)
                pass
        else:
            guardar_maestro(s_store.hojas, s_store.config_df)
            paths = append_movimientos(filas, fechas)
            if not maestro_writable():
                log.info("Maestro solo lectura (%s). Movimientos escritos en: %s", s_store.path_maestro, paths)
        s_store.ultima_actualizacion = datetime.now(timezone.utc)
        ultima_iso = s_store.timestamp_iso()
    fb_ok = 0
    # Salidas ya no escribe en Firestore — stock solo en maestro_stock DB. Solo buscador/etiquetas usan Firestore.
    if FIREBASE_WRITE_ENABLED:
        for p in sync_payload:
            if escribir_stock_item(p["codigo"], p["stock"], p["desc"], p["ubicacion"], p["categoria"]):
                fb_ok += 1
    else:
        log.info("Firebase write deshabilitado (FIREBASE_WRITE_ENABLED=0) — stock salidas solo en maestro_stock DB")
    return {"mensaje": f"Carga confirmada: {len(filas)} movimiento(s).", "movimientos": len(filas), "archivos": paths if 'paths' in locals() else [], "firebase_escritos": fb_ok, "filas": filas, "ultima_actualizacion": ultima_iso}


def confirmar_salida(body: dict[str, Any]) -> dict[str, Any]:
    items = body.get("items") or []
    if not isinstance(items, list):
        raise ValueError("items debe ser una lista.")
    return confirmar_batch(items, es_devolucion=False, forzar_negativos=bool(body.get("forzar_negativos")))


def confirmar_devolucion(body: dict[str, Any]) -> dict[str, Any]:
    # Mantener por compat backend pero no exponer en UI v4
    items = body.get("items") or []
    if not isinstance(items, list):
        raise ValueError("items debe ser una lista.")
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
    return confirmar_batch(norm, es_devolucion=True, forzar_negativos=True)


def listar_movimientos(
    *,
    desde: str | None = None,
    hasta: str | None = None,
    limite: int = 100,
    codigo: str | None = None,
    q: str | None = None,
    sector: str | None = None,
    numero_orden: str | None = None,
    incluir_anulados: bool = False,
) -> dict[str, Any]:
    """Lista movimientos: DB si enabled sino Excel. Soporta filtros extendidos para historial."""
    lim = max(1, min(1000, int(limite or 100)))
    if SALIDAS_DB_ENABLED:
        try:
            from store_sql import historial_listar
            rows = historial_listar(desde=desde, hasta=hasta, limite=lim, codigo=codigo, q=q, sector=sector, numero_orden=numero_orden, incluir_anulados=incluir_anulados)
            # Mapear DB rows a formato Excel-like para frontend (COLUMNAS_MOVIMIENTO)
            mapped = []
            for r in rows:
                # r es dict con snake_case
                fecha_val = r.get("fecha")
                fecha_s = fecha_val.isoformat() if isinstance(fecha_val, (date, datetime)) else fecha_sin_hora_str(fecha_val) if fecha_val else ""
                # Normalizar anulado fields (pueden venir como int, Decimal)
                anulado_v = r.get("anulado")
                anulado_norm = 1 if int(anulado_v or 0) == 1 else 0
                # Fechas audit
                def _iso(v: Any) -> Any:
                    return v.isoformat() if isinstance(v, (date, datetime)) else v
                mapped.append({
                    "FECHA": fecha_s,
                    "MES": r.get("mes") or "",
                    "AÑO": r.get("anio") or "",
                    "CODIGO": r.get("codigo") or "",
                    "DESCRIPCION": r.get("descripcion") or "",
                    "UBICACION": r.get("ubicacion") or "",
                    "CANTIDAD": _dec_float(r.get("cantidad") or 0),
                    "TIPO_COMPROBANTE": r.get("tipo_comprobante") or "",
                    "NUMERO_ORDEN": r.get("numero_orden") or "",
                    "MAQUINA_SITIO": r.get("maquina_sitio") or "",
                    "PRECIO_UNITARIO": _dec_float(r.get("precio_unitario") or 0),
                    "MONTO_TOTAL_SALIDA": _dec_float(r.get("monto_total") or 0),
                    "OPERARIO": r.get("operario_nombre") or "",
                    "SECTOR": r.get("sector_nombre") or "",
                    "es_devolucion": bool(r.get("es_devolucion")),
                    "id": int(r.get("id")) if r.get("id") is not None else None,
                    "creado_en": _iso(r.get("creado_en")),
                    # v5 audit fields
                    "anulado": anulado_norm,
                    "anulado_por": r.get("anulado_por"),
                    "anulado_en": _iso(r.get("anulado_en")),
                    "motivo_anulacion": r.get("motivo_anulacion"),
                    "editado_en": _iso(r.get("editado_en")),
                    "editado_por": r.get("editado_por"),
                })
            # columnas = keys de mapped[0] si hay, sino COLUMNAS_MOVIMIENTO
            from config import COLUMNAS_MOVIMIENTO
            columnas = list(COLUMNAS_MOVIMIENTO)
            return {"total": len(mapped), "items": mapped, "columnas": columnas}
        except Exception as e:
            log.warning("listar_movimientos DB fallo, fallback Excel: %s", e)
            pass
    df = cargar_historial()
    # filtros extendidos sobre df si vienen q/sector/orden
    if q or codigo or sector or numero_orden:
        # filtrar por q
        if q:
            qq = str(q).strip().upper()
            if qq:
                mask = pd.Series([False]*len(df), index=df.index)
                for col in ("CODIGO", "DESCRIPCION", "NUMERO_ORDEN", "SECTOR", "OPERARIO"):
                    if col in df.columns:
                        mask = mask | df[col].astype(str).str.upper().str.contains(qq, na=False)
                df = df[mask]
        if codigo and "CODIGO" in df.columns:
            df = df[df["CODIGO"].astype(str).str.upper() == str(codigo).strip().upper()]
        if sector and "SECTOR" in df.columns:
            df = df[df["SECTOR"].astype(str).str.upper() == str(sector).strip().upper()]
        if numero_orden and "NUMERO_ORDEN" in df.columns:
            df = df[df["NUMERO_ORDEN"].astype(str).str.strip() == str(numero_orden).strip()]
    df = filtrar_por_fecha(df, desde, hasta)
    # Limitar ya en a_registros
    return {"total": int(len(df)), "items": a_registros(df, limite=lim), "columnas": list(df.columns) if not df.empty else []}


def _normalizar_linea_gasto(val) -> str:
    """Agrupa comprobante como linea (L1…L7, PAÑOL, OTROS) para resumen diario."""
    if val is None:
        return "OTROS"
    s = str(val).strip().upper()
    if not s:
        return "OTROS"
    if s in ("PAÑ", "PAN", "PAÑOL", "PANOL"):
        return "PAÑOL"
    for ln in ("L1", "L2", "L3", "L4", "L5", "L6", "L7"):
        if s == ln or s.startswith(ln + " ") or s.startswith(ln + "-") or s.startswith(ln + "/"):
            return ln
    if s == "PROYECTOS":
        return "PROYECTOS"
    return s


def _orden_lineas_gasto():
    return ["PAÑOL"] + [f"L{i}" for i in range(1, 8)] + ["PROYECTOS"]


def resumen_diario(fecha: str, incluir_anulados: bool = False) -> dict[str, Any]:
    """Retorna resumen diario agrupado por tipo_comprobante normalizado (PAÑOL, L1-L7, OTROS).

    Consulta salida_historial via store_sql. Retorna grupos con totales y detalle.
    """
    from store_sql import historial_listar

    d0 = fecha
    d1 = fecha
    rows = historial_listar(desde=d0, hasta=d1, limite=10000, incluir_anulados=incluir_anulados)
    if not rows:
        return {"fecha": fecha, "grupos": [], "total_general": 0.0, "mensaje": "Sin movimientos para la fecha seleccionada."}

    # Agrupar por linea normalizada
    grupos_data: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        tipo_raw = r.get("tipo_comprobante") or r.get("TIPO_COMPROBANTE") or ""
        linea = _normalizar_linea_gasto(tipo_raw)
        if linea not in grupos_data:
            grupos_data[linea] = []
        monto = float(r.get("monto_total") or r.get("MONTO_TOTAL_SALIDA") or 0)
        cant = float(r.get("cantidad") or r.get("CANTIDAD") or 0)
        grupos_data[linea].append({
            "codigo": str(r.get("codigo") or r.get("CODIGO") or ""),
            "descripcion": str(r.get("descripcion") or r.get("DESCRIPCION") or ""),
            "cantidad": cant,
            "monto": monto,
            "tipo_comprobante": str(tipo_raw),
            "numero_orden": str(r.get("numero_orden") or r.get("NUMERO_ORDEN") or ""),
            "operario": str(r.get("operario_nombre") or r.get("OPERARIO") or ""),
            "sector": str(r.get("sector_nombre") or r.get("SECTOR") or ""),
            "maquina": str(r.get("maquina_sitio") or r.get("MAQUINA_SITIO") or ""),
            "fecha": str(r.get("fecha") or ""),
        })

    # Ordenar grupos: PAÑOL, L1..L7, PROYECTOS, OTROS
    orden = _orden_lineas_gasto()
    grupos: list[dict[str, Any]] = []
    total_general = 0.0
    for linea in orden:
        if linea in grupos_data and grupos_data[linea]:
            items = grupos_data[linea]
            total_grupo = sum(it["monto"] for it in items)
            total_general += total_grupo
            grupos.append({
                "linea": linea,
                "total": round(total_grupo, 2),
                "cantidad": len(items),
                "items": items,
            })
    # Agregar OTROS si existe y no esta ya en orden
    if "OTROS" in grupos_data and grupos_data["OTROS"]:
        otros_items = grupos_data["OTROS"]
        otros_total = sum(it["monto"] for it in otros_items)
        total_general += otros_total
        # Insertar OTROS al final si no existe
        if not any(g["linea"] == "OTROS" for g in grupos):
            grupos.append({"linea": "OTROS", "total": round(otros_total, 2), "cantidad": len(otros_items), "items": otros_items})

    return {"fecha": fecha, "grupos": grupos, "total_general": round(total_general, 2), "mensaje": ""}


def refresh_maestro() -> dict[str, Any]:
    s = SalidasStore.get()
    ts = s.refresh()
    return {"mensaje": "Maestro recargado.", "timestamp": ts.astimezone().isoformat(), "path": s.path_maestro}


def sync_firebase_ahora() -> dict[str, Any]:
    return pull_firestore_si_corresponde(forzar=True)


def generar_diario_para_mail(fecha: str | date) -> tuple[bytes, str]:
    """Genera bytes del diario para mail diario. Fuente DB si enabled sino Excel."""
    from excel_io import generar_diario_bytes

    d = parse_fecha(fecha) if isinstance(fecha, str) else fecha
    if d is None:
        raise ValueError("fecha invalida (use AAAA-MM-DD)")
    return generar_diario_bytes(d)


def generar_remito_para_orden(orden: str, fecha: str | None = None, items: list[dict[str, Any]] | None = None, cabecera: dict[str, Any] | None = None) -> tuple[bytes, str]:
    from excel_io import generar_remito_bytes

    return generar_remito_bytes(orden, fecha, items=items, cabecera=cabecera)


# ---------- Atenciones ventanilla v4 simplificada ----------

def registrar_atencion(body: dict[str, Any], atendido_por_token: str | None = None) -> dict[str, Any]:
    """Registra atencion ventanilla simplificada v4.

    Solo: fecha, con_retiro (true=fuera sistema, false=sin stock), observaciones(500 opcional).
    """
    if not isinstance(body, dict):
        raise ValueError("Body debe ser un objeto JSON.")
    # con_retiro requerido
    cr_raw = body.get("con_retiro")
    if cr_raw is None:
        cr_raw = body.get("conRetiro", body.get("retiro", body.get("retiro_material")))
    if cr_raw is None or str(cr_raw).strip() == "":
        raise ValueError("con_retiro es obligatorio (true = retiro fuera de sistema, false = sin stock).")
    if isinstance(cr_raw, str):
        v = cr_raw.strip().lower()
        if v in ("1", "true", "si", "sí", "con", "yes"):
            con_retiro = True
        elif v in ("0", "false", "no", "sin"):
            con_retiro = False
        else:
            raise ValueError("con_retiro debe ser true/false.")
    else:
        con_retiro = bool(cr_raw)
    # Fecha
    fecha_raw = body.get("fecha") or body.get("atendido_en")
    if fecha_raw:
        fecha_d = parse_fecha(fecha_raw)
        if fecha_d is None:
            raise ValueError("fecha invalida (use AAAA-MM-DD).")
    else:
        fecha_d = date.today()
    # atendido_por
    atendido = None
    if atendido_por_token:
        atendido = str(atendido_por_token).strip()
    if not atendido:
        atendido = str(body.get("atendido_por") or body.get("creado_por") or body.get("usuario") or "").strip()
    if atendido:
        atendido = atendido.strip().upper()[:120]
        if not atendido:
            atendido = None
    # observaciones 500
    obs = body.get("observaciones")
    if obs is not None:
        obs = str(obs).strip()
        if len(obs) > 500:
            raise ValueError("observaciones max 500 caracteres.")
        if not obs:
            obs = None
    payload = {
        "fecha": fecha_d,
        "con_retiro": con_retiro,
        "observaciones": obs,
        "atendido_por": atendido,
        "creado_por": atendido,
    }
    # Resolver atendido_en combinando fecha si viene hora? v4 ignora hora, usa atendido_en = ahora o fecha mediodia
    if body.get("atendido_en"):
        try:
            ae = parse_fecha(body.get("atendido_en"))
            if ae:
                payload["atendido_en"] = datetime(ae.year, ae.month, ae.day, 12, 0, 0)
        except Exception:
            pass
    elif body.get("hora"):
        try:
            hora_raw = str(body.get("hora")).strip()[:8]
            h, m, *rest = hora_raw.split(":")
            s = int(rest[0]) if rest else 0
            payload["atendido_en"] = datetime(fecha_d.year, fecha_d.month, fecha_d.day, int(h), int(m), int(s))
        except Exception:
            pass
    try:
        from store_sql import atenciones_crear
    except Exception as e:
        raise RuntimeError(f"No se pudo cargar store_sql.atenciones_crear: {e}") from e
    new_id = atenciones_crear(payload)
    return {"mensaje": "Atención registrada.", "id": new_id, "con_retiro": con_retiro, "fecha": fecha_d.isoformat()}


def listar_atenciones(
    *,
    desde: str | None = None,
    hasta: str | None = None,
    con_retiro: str | int | bool | None = None,
    q: str | None = None,
    limite: int = 100,
) -> dict[str, Any]:
    try:
        from store_sql import atenciones_listar
    except Exception as e:
        raise RuntimeError(f"No se pudo cargar store_sql: {e}") from e
    lim = max(1, min(ATENCIONES_EXPORT_MAX_ROWS, int(limite or 100)))
    rows = atenciones_listar(desde=desde, hasta=hasta, con_retiro=con_retiro, q=q, limite=lim)
    out = []
    for r in rows:
        d = dict(r)
        for k in ("fecha", "creado_en", "actualizado_en", "atendido_en"):
            v = d.get(k)
            if isinstance(v, (date, datetime)):
                d[k] = v.isoformat()
            elif v is None:
                d[k] = None
        out.append(d)
    return {"total": len(out), "items": out, "limite": lim}


def atenciones_export_data(
    *,
    desde: str | None = None,
    hasta: str | None = None,
    formato: str = "xlsx",
) -> tuple[bytes, str, str]:
    try:
        from store_sql import atenciones_exportar_rows
    except Exception as e:
        raise RuntimeError(f"No se pudo cargar store_sql: {e}") from e
    rows = atenciones_exportar_rows(desde=desde, hasta=hasta)
    if len(rows) > ATENCIONES_EXPORT_MAX_ROWS:
        raise ValueError(f"Export excede max {ATENCIONES_EXPORT_MAX_ROWS} filas. Filtre por fecha.")
    fmt = (formato or "xlsx").strip().lower()
    if fmt not in ("xlsx", "csv"):
        raise ValueError("formato debe ser xlsx o csv")
    desde_s = parse_fecha(desde).isoformat() if desde and parse_fecha(desde) else "inicio"
    hasta_s = parse_fecha(hasta).isoformat() if hasta and parse_fecha(hasta) else date.today().isoformat()
    base = f"atenciones_{desde_s}_a_{hasta_s}"
    if fmt == "csv":
        data = atenciones_to_csv_bytes(rows)
        return data, "text/csv; charset=utf-8", f"{base}.csv"
    wb = workbook_atenciones(rows, sheet_name="Atenciones")
    import io
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", f"{base}.xlsx"


def kpi_atenciones(periodo: str | None = None, desde: str | None = None, hasta: str | None = None) -> dict[str, Any]:
    try:
        from store_sql import atenciones_kpi_mensual, atenciones_por_dia
    except Exception as e:
        raise RuntimeError(f"No se pudo cargar store_sql: {e}") from e
    mensual = atenciones_kpi_mensual(periodo=periodo) if periodo else atenciones_kpi_mensual()
    for r in mensual:
        v = r.get("periodo")
        if isinstance(v, (date, datetime)):
            r["periodo"] = v.isoformat() if isinstance(v, datetime) else v.isoformat()
        elif v is not None:
            r["periodo"] = str(v)
        for k in ("total", "con_retiro", "sin_retiro"):
            try:
                r[k] = int(r[k]) if r.get(k) is not None else 0
            except (TypeError, ValueError):
                r[k] = 0
        try:
            r["pct_con_retiro"] = float(r["pct_con_retiro"]) if r.get("pct_con_retiro") is not None else None
        except (TypeError, ValueError):
            r["pct_con_retiro"] = None
    result: dict[str, Any] = {"kpi_mensual": mensual}
    if periodo:
        return result
    if desde or hasta:
        por_dia = atenciones_por_dia(desde=desde, hasta=hasta)
        for r in por_dia:
            fv = r.get("fecha")
            if isinstance(fv, (date, datetime)):
                r["fecha"] = fv.isoformat()
            for k in ("total", "con_retiro", "sin_retiro"):
                try:
                    r[k] = int(r[k]) if r.get(k) is not None else 0
                except (TypeError, ValueError):
                    r[k] = 0
            try:
                r["pct_con_retiro"] = float(r["pct_con_retiro"]) if r.get("pct_con_retiro") is not None else None
            except (TypeError, ValueError):
                r["pct_con_retiro"] = None
        result["por_dia"] = por_dia
    else:
        por_dia = atenciones_por_dia()
        for r in por_dia:
            fv = r.get("fecha")
            if isinstance(fv, (date, datetime)):
                r["fecha"] = fv.isoformat()
            for k in ("total", "con_retiro", "sin_retiro"):
                try:
                    r[k] = int(r[k]) if r.get(k) is not None else 0
                except (TypeError, ValueError):
                    r[k] = 0
            try:
                r["pct_con_retiro"] = float(r["pct_con_retiro"]) if r.get("pct_con_retiro") is not None else None
            except (TypeError, ValueError):
                r["pct_con_retiro"] = None
        result["por_dia"] = por_dia[:31]
    if mensual:
        result["resumen"] = mensual[0]
    else:
        result["resumen"] = {"total": 0, "con_retiro": 0, "sin_retiro": 0, "pct_con_retiro": None}
    return result


# ---------- v5: anulacion/edicion auditable ----------

def anular_movimiento(movimiento_id: int | str, motivo: str, realizado_por: str | None) -> dict[str, Any]:
    """Anula (soft-delete) un movimiento. Validacion y auditoria en store_sql. Stock NO revertido."""
    mot = str(motivo or "").strip()
    if len(mot) < 3:
        raise ValueError("motivo requerido (3..500 caracteres).")
    if len(mot) > 500:
        raise ValueError("motivo max 500 caracteres.")
    quien = str(realizado_por or "").strip() or "SISTEMA"
    quien = quien[:120].upper() if len(quien) <= 120 else quien[:120].upper()
    try:
        from store_sql import historial_anular
    except Exception as e:
        raise RuntimeError(f"No se pudo cargar store_sql.historial_anular: {e}") from e
    if not SALIDAS_DB_ENABLED:
        raise ValueError("Anulación requiere SALIDAS_DB_ENABLED=1 (DB activa).")
    row = historial_anular(movimiento_id, anulado_por=quien, motivo=mot)
    # Mapear a formato frontend simple
    def _iso(v: Any) -> Any:
        return v.isoformat() if isinstance(v, (date, datetime)) else v
    mapped = {
        "FECHA": _iso(row.get("fecha")),
        "CODIGO": row.get("codigo"),
        "CANTIDAD": _dec_float(row.get("cantidad")),
        "NUMERO_ORDEN": row.get("numero_orden"),
        "SECTOR": row.get("sector_nombre"),
        "OPERARIO": row.get("operario_nombre"),
        "anulado": int(row.get("anulado") or 0),
        "motivo_anulacion": row.get("motivo_anulacion"),
        "anulado_por": row.get("anulado_por"),
        "anulado_en": _iso(row.get("anulado_en")),
        "id": int(row.get("id")) if row.get("id") is not None else None,
    }
    return {"mensaje": "Movimiento anulado", "id": int(row.get("id") or 0), "movimiento": mapped}


def editar_movimiento(movimiento_id: int | str, cambios: dict[str, Any], realizado_por: str | None, motivo: str | None = None) -> dict[str, Any]:
    """Edita un movimiento activo. Solo campos permitidos. Stock NO tocado (correccion historica)."""
    if not isinstance(cambios, dict) or not cambios:
        raise ValueError("cambios requerido.")
    # Filtrar solo permitidos a nivel service también (defense in depth)
    permitidos = {"tipo_comprobante", "numero_orden", "maquina_sitio", "sector_nombre", "operario_nombre", "cantidad", "precio_unitario", "fecha"}
    clean: dict[str, Any] = {}
    for k, v in cambios.items():
        kk = str(k).strip().lower()
        if kk in permitidos:
            clean[kk] = v
        elif str(k).strip() in permitidos:
            clean[str(k).strip()] = v
    if not clean:
        raise ValueError(f"No hay campos editables (permitidos: {', '.join(sorted(permitidos))}).")
    quien = str(realizado_por or "").strip() or "SISTEMA"
    quien = quien[:120].upper()
    mot = str(motivo).strip()[:500] if motivo is not None and str(motivo).strip() else None
    # Sanitizar strings base: upper/strip (fecha se mantiene ISO, no upper)
    for fk in ("tipo_comprobante", "numero_orden", "maquina_sitio", "sector_nombre", "operario_nombre"):
        if fk in clean and isinstance(clean[fk], str):
            clean[fk] = clean[fk].strip()
            if fk in ("tipo_comprobante", "maquina_sitio", "sector_nombre", "operario_nombre"):
                clean[fk] = clean[fk].upper()
            elif fk == "numero_orden":
                clean[fk] = clean[fk].strip()
    if "fecha" in clean and isinstance(clean["fecha"], str):
        clean["fecha"] = clean["fecha"].strip()
        # Validacion basica de fecha (usa parse_fecha del excel_io)
        from excel_io import parse_fecha

        if parse_fecha(clean["fecha"]) is None:
            raise ValueError("fecha invalida. Use AAAA-MM-DD o DD/MM/AAAA.")
    try:
        from store_sql import historial_editar
    except Exception as e:
        raise RuntimeError(f"No se pudo cargar store_sql.historial_editar: {e}") from e
    if not SALIDAS_DB_ENABLED:
        raise ValueError("Edicion requiere SALIDAS_DB_ENABLED=1 (DB activa).")
    row = historial_editar(movimiento_id, cambios=clean, editado_por=quien, motivo=mot)
    def _iso2(v: Any) -> Any:
        return v.isoformat() if isinstance(v, (date, datetime)) else v
    mapped = {
        "FECHA": _iso2(row.get("fecha")),
        "CODIGO": row.get("codigo"),
        "CANTIDAD": _dec_float(row.get("cantidad")),
        "TIPO_COMPROBANTE": row.get("tipo_comprobante"),
        "NUMERO_ORDEN": row.get("numero_orden"),
        "MAQUINA_SITIO": row.get("maquina_sitio"),
        "PRECIO_UNITARIO": _dec_float(row.get("precio_unitario")),
        "MONTO_TOTAL_SALIDA": _dec_float(row.get("monto_total")),
        "OPERARIO": row.get("operario_nombre"),
        "SECTOR": row.get("sector_nombre"),
        "editado_en": _iso2(row.get("editado_en")),
        "editado_por": row.get("editado_por"),
        "id": int(row.get("id")) if row.get("id") is not None else None,
    }
    return {"mensaje": "Movimiento editado", "id": int(row.get("id") or 0), "movimiento": mapped}


def listar_auditoria(historial_id: int | str) -> dict[str, Any]:
    """Lista auditoria para un movimiento."""
    try:
        from store_sql import historial_auditoria_listar
    except Exception as e:
        raise RuntimeError(f"No se pudo cargar store_sql.historial_auditoria_listar: {e}") from e
    try:
        hid = int(str(historial_id).strip())
    except (TypeError, ValueError):
        raise ValueError("historial_id invalido.")
    rows = historial_auditoria_listar(hid)
    out = []
    for r in rows:
        d = dict(r)
        for k in ("realizado_en",):
            v = d.get(k)
            if isinstance(v, (date, datetime)):
                d[k] = v.isoformat()
        # datos_before/after are JSON strings or dicts; ensure parsed preview
        # Leave as stored (MariaDB JSON returns string); frontend can parse.
        # Ensure keys are serializable
        for kk in ("datos_before", "datos_after"):
            vv = d.get(kk)
            if isinstance(vv, (bytes, bytearray)):
                try:
                    d[kk] = vv.decode("utf-8")
                except Exception:
                    d[kk] = str(vv)
        out.append(d)
    return {"total": len(out), "items": out, "historial_id": hid}


# ---------- Motivos catalogo editable (v4: DROP - stub compat) ----------

def listar_motivos(activos_only: bool = True) -> dict[str, Any]:
    """v4 stub: tabla DROP, retornar vacio para compat."""
    try:
        from store_sql import motivos_listar
        rows = motivos_listar(activos_only=activos_only)
        out = []
        for r in rows:
            d = dict(r)
            v = d.get("creado_en")
            if isinstance(v, (date, datetime)):
                d["creado_en"] = v.isoformat()
            out.append(d)
        return {"total": len(out), "items": out}
    except Exception:
        return {"total": 0, "items": []}


def crear_motivo(body: dict[str, Any]) -> dict[str, Any]:
    raise ValueError("Catálogo de motivos obsoleto en v4 (DROP tabla salida_atencion_motivos). No se usa - atenciones ahora solo con_retiro + observaciones.")


def actualizar_motivo(motivo_id: int | str, body: dict[str, Any]) -> dict[str, Any]:
    raise ValueError("Catálogo de motivos obsoleto en v4.")


def eliminar_motivo(motivo_id: int | str) -> dict[str, Any]:
    raise ValueError("Catálogo de motivos obsoleto en v4.")
