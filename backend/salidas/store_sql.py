# -*- coding: utf-8 -*-
"""Store SQL para modulo Salidas - v4 simplificado (2026-09-16).

Fuentes:
 - salida_historial: fuente unica de movimientos (DB cuando SALIDAS_DB_ENABLED=1, sino Excel)
 - salida_atenciones: simplificada a fecha, con_retiro, observaciones(500) + atendido_en/atendido_por opcionales
 - salida_movimientos_diario / salida_otif / salida_atencion_motivos: DROP en v4 (se mantienen funciones stub por compat, retornan vacio si tabla no existe)

Todas las funciones son idempotentes y usan transacciones cortas.
Si MariaDB no responde o tabla no existe, devuelven [] / None en lugar de 500 para no romper 404 handling.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from db import get_connection

import re as _re

import logging as _logging
_store_sql_log = _logging.getLogger("salidas.store_sql")

# ---------- maestro_stock helpers (stock source exclusive for salidas) ----------

def _maestro_has_alias_column() -> bool:
    """Check if maestro_stock.alias exists; cached? Keep simple query."""
    try:
        conn2 = get_connection()
        try:
            with conn2.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) AS c FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='maestro_stock' AND COLUMN_NAME='alias'"
                )
                r = cur.fetchone()
                return bool(r and int(r.get("c", 0)) > 0)
        finally:
            try:
                conn2.close()
            except Exception:
                pass
    except Exception:
        return False


def maestro_get_by_codigo(codigo: str) -> dict[str, Any] | None:
    """Lee artículo desde maestro_stock DB. Retorna ArticuloSalida dict o None si no existe/error."""
    cod = str(codigo or "").strip().upper()
    if not cod:
        return None
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            # Try with alias first; fallback without alias if column missing (backward compat)
            try:
                cur.execute(
                    "SELECT codigo, descripcion, alias, stock, ubicacion, precio_unitario, categoria, activo FROM maestro_stock WHERE codigo=%s AND activo=1 LIMIT 1",
                    (cod,),
                )
            except Exception as e:
                msg = str(e).lower()
                if "unknown column" in msg and "alias" in msg:
                    cur.execute(
                        "SELECT codigo, descripcion, stock, ubicacion, precio_unitario, categoria, activo FROM maestro_stock WHERE codigo=%s AND activo=1 LIMIT 1",
                        (cod,),
                    )
                else:
                    raise
            row = cur.fetchone()
            if not row:
                return None
            alias_val = row.get("alias") if "alias" in row else None
            return {
                "codigo": str(row.get("codigo") or cod).strip().upper(),
                "descripcion": str(row.get("descripcion") or "").strip().upper(),
                "alias": str(alias_val).strip() if alias_val is not None and str(alias_val).strip() != "" else None,
                "ubicacion": str(row.get("ubicacion") or "").strip().upper(),
                "stock_actual": float(row.get("stock") or 0),
                "precio_unitario": float(row.get("precio_unitario") or 0),
                "categoria": str(row.get("categoria") or "GENERAL").strip().upper() or "GENERAL",
                "hoja": "DB",
            }
    except Exception as e:
        msg = str(e).lower()
        if "1146" in msg or "doesn't exist" in msg or "no such table" in msg:
            _store_sql_log.warning("maestro_stock tabla no existe (maestro_get_by_codigo %s): %s", cod, e)
            return None
        _store_sql_log.warning("maestro_get_by_codigo DB error %s: %s", cod, e)
        return None
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def maestro_search(q: str, limite: int = 20) -> list[dict[str, Any]] | None:
    """Busca en maestro_stock por codigo/descripcion/alias/ubicacion (tokenized AND).

    Replica Externas/AppPanolWeb filterArticulos: split query en palabras, cada palabra debe
    estar en codigo+desc+alias+ubicacion (OR por campo, AND entre palabras). Case-insensitive via UPPER.
    """
    try:
        lim = max(1, min(100, int(limite or 20)))
    except Exception:
        lim = 20
    raw_q = str(q or "").strip()
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            # Helper to execute with alias and fallback without alias on migration lag
            def _exec_with_alias(sql_with: str, params_with: tuple, sql_without: str, params_without: tuple):
                try:
                    cur.execute(sql_with, params_with)
                except Exception as e:
                    msg = str(e).lower()
                    if "unknown column" in msg and "alias" in msg:
                        cur.execute(sql_without, params_without)
                    else:
                        raise

            if not raw_q:
                try:
                    cur.execute(
                        "SELECT codigo, descripcion, alias, stock, ubicacion, precio_unitario, categoria FROM maestro_stock WHERE activo=1 ORDER BY codigo ASC LIMIT %s",
                        (lim,),
                    )
                except Exception as e:
                    if "unknown column" in str(e).lower() and "alias" in str(e).lower():
                        cur.execute(
                            "SELECT codigo, descripcion, stock, ubicacion, precio_unitario, categoria FROM maestro_stock WHERE activo=1 ORDER BY codigo ASC LIMIT %s",
                            (lim,),
                        )
                    else:
                        raise
            else:
                words = [w for w in _re.split(r"\s+", raw_q.strip()) if w]
                if not words:
                    try:
                        cur.execute(
                            "SELECT codigo, descripcion, alias, stock, ubicacion, precio_unitario, categoria FROM maestro_stock WHERE activo=1 ORDER BY codigo ASC LIMIT %s",
                            (lim,),
                        )
                    except Exception as e:
                        if "unknown column" in str(e).lower() and "alias" in str(e).lower():
                            cur.execute(
                                "SELECT codigo, descripcion, stock, ubicacion, precio_unitario, categoria FROM maestro_stock WHERE activo=1 ORDER BY codigo ASC LIMIT %s",
                                (lim,),
                            )
                        else:
                            raise
                else:
                    # Build tokenized WHERE: activo=1 AND (word1 OR) AND (word2 OR) ...
                    clauses_with: list[str] = []
                    params_with: list[Any] = []
                    clauses_without: list[str] = []
                    params_without: list[Any] = []
                    for w in words:
                        like = f"%{w.upper()}%"
                        clauses_with.append("(UPPER(codigo) LIKE %s OR UPPER(COALESCE(descripcion,'')) LIKE %s OR UPPER(COALESCE(alias,'')) LIKE %s OR UPPER(COALESCE(ubicacion,'')) LIKE %s)")
                        params_with.extend([like, like, like, like])
                        clauses_without.append("(UPPER(codigo) LIKE %s OR UPPER(COALESCE(descripcion,'')) LIKE %s OR UPPER(COALESCE(ubicacion,'')) LIKE %s)")
                        params_without.extend([like, like, like])
                    where_with = " AND ".join(clauses_with)
                    where_without = " AND ".join(clauses_without)
                    sql_with = f"""SELECT codigo, descripcion, alias, stock, ubicacion, precio_unitario, categoria
                       FROM maestro_stock
                       WHERE activo=1 AND {where_with}
                       ORDER BY codigo ASC LIMIT %s"""
                    sql_without = f"""SELECT codigo, descripcion, stock, ubicacion, precio_unitario, categoria
                       FROM maestro_stock
                       WHERE activo=1 AND {where_without}
                       ORDER BY codigo ASC LIMIT %s"""
                    params_with.append(lim)
                    params_without.append(lim)
                    _exec_with_alias(sql_with, tuple(params_with), sql_without, tuple(params_without))
            rows = cur.fetchall()
            out: list[dict[str, Any]] = []
            for r in rows or []:
                try:
                    alias_val = r.get("alias") if "alias" in r else None
                    out.append(
                        {
                            "codigo": str(r.get("codigo") or "").strip().upper(),
                            "descripcion": str(r.get("descripcion") or "").strip().upper(),
                            "alias": str(alias_val).strip() if alias_val is not None and str(alias_val).strip() != "" else None,
                            "ubicacion": str(r.get("ubicacion") or "").strip().upper(),
                            "stock_actual": float(r.get("stock") or 0),
                            "precio_unitario": float(r.get("precio_unitario") or 0),
                            "categoria": str(r.get("categoria") or "GENERAL").strip().upper() or "GENERAL",
                            "hoja": "DB",
                        }
                    )
                except Exception:
                    continue
            return out
    except Exception as e:
        msg = str(e).lower()
        if "1146" in msg or "doesn't exist" in msg or "no such table" in msg:
            _store_sql_log.warning("maestro_stock tabla no existe (maestro_search q=%s): %s", raw_q, e)
            return None
        _store_sql_log.warning("maestro_search DB error q=%s: %s", raw_q, e)
        return None
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def maestro_decrement_stock(codigo: str, cantidad: float) -> bool:
    """Decrementa stock en maestro_stock en cantidad (positiva salida resta, negativa devolucion suma). Retorna True si row afectada."""
    cod = str(codigo or "").strip().upper()
    if not cod:
        return False
    try:
        cant = float(cantidad)
    except Exception:
        return False
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("UPDATE maestro_stock SET stock = stock - %s WHERE codigo=%s AND activo=1", (cant, cod))
            affected = int(cur.rowcount or 0)
        conn.commit()
        return affected > 0
    except Exception as e:
        _store_sql_log.warning("maestro_decrement_stock fallo %s (%s): %s", cod, cantidad, e)
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return False
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def maestro_update_alias(codigo: str, alias: str | None, realizado_por: str | None = None) -> dict[str, Any]:
    """Actualiza alias de búsqueda para un código. Validate, update, audit.

    - alias: None or '' -> clear (SET NULL); else trimmed string max 300.
    - realizado_por: user for audit if needed (logged via _store_sql_log).
    - Returns updated row dict (codigo, descripcion, alias, stock, ubicacion, precio_unitario, categoria, activo, actualizado_en).
    - Raises ValueError if codigo not found or alias too long / invalid.
    """
    cod = str(codigo or "").strip().upper()
    if not cod:
        raise ValueError("codigo requerido.")
    # Normalize alias
    alias_norm: str | None = None
    if alias is not None:
        s = str(alias).strip()
        if s == "":
            alias_norm = None
        else:
            # Keep original case? Search uses UPPER, so case-insensitive; preserve user input trimmed
            # but enforce max 300
            if len(s) > 300:
                raise ValueError("alias max 300 caracteres.")
            alias_norm = s
    # else alias None -> clear

    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            # Ensure alias column exists - if not, raise helpful error (migration pending)
            try:
                # Try update; if column missing, MySQL will error with unknown column
                cur.execute(
                    "UPDATE maestro_stock SET alias=%s, actualizado_en=NOW() WHERE codigo=%s AND activo=1",
                    (alias_norm, cod),
                )
            except Exception as e:
                msg = str(e).lower()
                if "unknown column" in msg and "alias" in msg:
                    raise ValueError("Columna alias no existe en maestro_stock. Ejecuta migración/docs/maestro_stock_migracion_v1.sql o reinicia el servicio para migrar.") from e
                if "1146" in msg or "doesn't exist" in msg:
                    raise ValueError("Tabla maestro_stock no existe.") from e
                raise
            if cur.rowcount == 0:
                # Check if codigo exists but activo=0 or not found
                try:
                    cur.execute("SELECT codigo, activo FROM maestro_stock WHERE codigo=%s LIMIT 1", (cod,))
                    row_chk = cur.fetchone()
                except Exception:
                    row_chk = None
                if not row_chk:
                    raise ValueError(f"Código {cod} no encontrado en maestro_stock.")
                if int(row_chk.get("activo") or 0) != 1:
                    raise ValueError(f"Código {cod} está inactivo.")
                # If row exists but alias unchanged (same value), rowcount may be 0 but not error; treat as ok
                pass
            # Fetch updated row
            try:
                cur.execute(
                    "SELECT codigo, descripcion, alias, stock, ubicacion, precio_unitario, categoria, activo, actualizado_en FROM maestro_stock WHERE codigo=%s LIMIT 1",
                    (cod,),
                )
            except Exception as e:
                if "unknown column" in str(e).lower() and "alias" in str(e).lower():
                    cur.execute(
                        "SELECT codigo, descripcion, stock, ubicacion, precio_unitario, categoria, activo, actualizado_en FROM maestro_stock WHERE codigo=%s LIMIT 1",
                        (cod,),
                    )
                else:
                    raise
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Código {cod} no encontrado tras actualizar.")
            # Audit via salida_historial_auditoria? For alias, simple log; try to write to auditoria if table exists
            try:
                quien = str(realizado_por or "").strip()[:120] or None
                # Use same auditoria table with accion='editar' but leave datos_before null for alias change
                # Only if table exists
                cur.execute(
                    "SELECT COUNT(*) AS c FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='salida_historial_auditoria'"
                )
                _r = cur.fetchone()
                if _r and int(_r.get("c", 0)) > 0:
                    # We don't have historial_id for maestro; skip inserting. Just log via app logger.
                    pass
            except Exception:
                pass
        conn.commit()
        # Map to ArticuloSalida-like dict plus alias
        alias_val = row.get("alias") if "alias" in row else None
        upd = row.get("actualizado_en")
        try:
            upd_iso = upd.isoformat() if isinstance(upd, (date, datetime)) else str(upd) if upd else None
        except Exception:
            upd_iso = str(upd) if upd else None
        result = {
            "codigo": str(row.get("codigo") or cod).strip().upper(),
            "descripcion": str(row.get("descripcion") or "").strip().upper(),
            "alias": str(alias_val).strip() if alias_val is not None and str(alias_val).strip() != "" else None,
            "ubicacion": str(row.get("ubicacion") or "").strip().upper(),
            "stock_actual": float(row.get("stock") or 0),
            "precio_unitario": float(row.get("precio_unitario") or 0),
            "categoria": str(row.get("categoria") or "GENERAL").strip().upper() or "GENERAL",
            "activo": int(row.get("activo") or 1),
            "actualizado_en": upd_iso,
            "hoja": "DB",
        }
        if realizado_por:
            _store_sql_log.info("maestro_update_alias %s -> %r por %s", cod, alias_norm, realizado_por)
        return result
    except ValueError:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        raise
    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        _store_sql_log.warning("maestro_update_alias fallo %s -> %r: %s", cod, alias, e)
        raise ValueError(str(e)) from e
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def _audit_json_safe(obj: Any) -> Any:
    """Convierte Decimal/date/datetime a JSON-serializable para columnas JSON."""
    if isinstance(obj, Decimal):
        try:
            return float(obj)
        except Exception:
            return str(obj)
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, bytes):
        try:
            return obj.decode("utf-8", errors="replace")
        except Exception:
            return str(obj)
    return obj


def _row_to_jsonable(row: dict[str, Any] | None) -> str | None:
    if row is None:
        return None
    safe = {k: _audit_json_safe(v) for k, v in dict(row).items()}
    try:
        return json.dumps(safe, ensure_ascii=False, default=str)
    except Exception:
        # fallback: stringify
        return json.dumps({k: str(v) for k, v in dict(row).items()}, ensure_ascii=False)


# ---------- helpers OTIF (v4: tabla DROP - stub) ----------
def _calc_otif_flags(fecha_comprometida: date | str | None, fecha_entrega_real: date | str | None, cantidad_solicitada: float, cantidad_entregada: float) -> tuple[int, int, int]:
    from excel_io import parse_fecha

    fc = parse_fecha(fecha_comprometida) if isinstance(fecha_comprometida, str) else fecha_comprometida
    fr = parse_fecha(fecha_entrega_real) if isinstance(fecha_entrega_real, str) else fecha_entrega_real
    try:
        cs = float(cantidad_solicitada or 0)
        ce = float(cantidad_entregada or 0)
    except (TypeError, ValueError):
        cs, ce = 0.0, 0.0
    en_tiempo = 1 if (fr is not None and fc is not None and fr <= fc) else 0
    completo = 1 if ce >= cs and cs != 0 else 0
    otif = 1 if (en_tiempo == 1 and completo == 1) else 0
    return en_tiempo, completo, otif


def _periodo_desde_fecha(fecha_comprometida: date | str | None) -> date | None:
    from excel_io import parse_fecha

    d = parse_fecha(fecha_comprometida) if isinstance(fecha_comprometida, str) else fecha_comprometida
    if d is None:
        return None
    return date(d.year, d.month, 1)


# ---------- salida_historial ----------

def historial_listar(
    desde: date | str | None = None,
    hasta: date | str | None = None,
    limite: int = 100,
    codigo: str | None = None,
    q: str | None = None,
    sector: str | None = None,
    numero_orden: str | None = None,
    incluir_anulados: bool = False,
) -> list[dict[str, Any]]:
    """Lista movimientos con filtros opcionales. Devuelve [] si tabla no existe / DB caida."""
    from excel_io import parse_fecha

    d0 = parse_fecha(desde) if isinstance(desde, str) else desde
    d1 = parse_fecha(hasta) if isinstance(hasta, str) else hasta
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            try:
                sql = "SELECT * FROM salida_historial WHERE 1=1"
                params: list[Any] = []
                if not incluir_anulados:
                    # Filtrar anulados: si columna no existe, el query fallará y se maneja abajo (fallback sin filtro)
                    sql += " AND COALESCE(anulado,0)=0"
                if d0:
                    sql += " AND fecha >= %s"
                    params.append(d0)
                if d1:
                    sql += " AND fecha <= %s"
                    params.append(d1)
                if codigo:
                    sql += " AND codigo = %s"
                    params.append(str(codigo).strip().upper())
                if numero_orden:
                    sql += " AND numero_orden = %s"
                    params.append(str(numero_orden).strip())
                if sector:
                    sql += " AND UPPER(COALESCE(sector_nombre,'')) = %s"
                    params.append(str(sector).strip().upper())
                if q:
                    qq = f"%{str(q).strip().upper()}%"
                    sql += " AND (UPPER(codigo) LIKE %s OR UPPER(COALESCE(descripcion,'')) LIKE %s OR UPPER(COALESCE(numero_orden,'')) LIKE %s OR UPPER(COALESCE(sector_nombre,'')) LIKE %s OR UPPER(COALESCE(operario_nombre,'')) LIKE %s)"
                    params.extend([qq, qq, qq, qq, qq])
                sql += " ORDER BY fecha DESC, id DESC LIMIT %s"
                params.append(int(limite))
                cur.execute(sql, params)
                rows = cur.fetchall()
                return list(rows) if rows else []
            except Exception as e:
                msg = str(e).lower()
                if "1146" in msg or "doesn't exist" in msg or "no such table" in msg:
                    return []
                # Columna anulado no existe aún (unknown column) -> retry sin filtro anulado
                if "unknown column" in msg and "anulado" in msg and not incluir_anulados:
                    try:
                        sql2 = "SELECT * FROM salida_historial WHERE 1=1"
                        params2: list[Any] = []
                        if d0:
                            sql2 += " AND fecha >= %s"
                            params2.append(d0)
                        if d1:
                            sql2 += " AND fecha <= %s"
                            params2.append(d1)
                        if codigo:
                            sql2 += " AND codigo = %s"
                            params2.append(str(codigo).strip().upper())
                        if numero_orden:
                            sql2 += " AND numero_orden = %s"
                            params2.append(str(numero_orden).strip())
                        if sector:
                            sql2 += " AND UPPER(COALESCE(sector_nombre,'')) = %s"
                            params2.append(str(sector).strip().upper())
                        if q:
                            qq = f"%{str(q).strip().upper()}%"
                            sql2 += " AND (UPPER(codigo) LIKE %s OR UPPER(COALESCE(descripcion,'')) LIKE %s OR UPPER(COALESCE(numero_orden,'')) LIKE %s OR UPPER(COALESCE(sector_nombre,'')) LIKE %s OR UPPER(COALESCE(operario_nombre,'')) LIKE %s)"
                            params2.extend([qq, qq, qq, qq, qq])
                        sql2 += " ORDER BY fecha DESC, id DESC LIMIT %s"
                        params2.append(int(limite))
                        cur.execute(sql2, params2)
                        rows = cur.fetchall()
                        return list(rows) if rows else []
                    except Exception:
                        raise
                raise
    finally:
        try:
            conn.close()
        except Exception:
            pass


def historial_crear(fila: dict[str, Any]) -> int:
    """Inserta un movimiento en salida_historial. Retorna id insertado."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Auto-derivar mes/anio si no vienen
            fecha_val = fila.get("fecha")
            mes_val = fila.get("mes")
            anio_val = fila.get("anio")
            if not mes_val or not anio_val:
                try:
                    from excel_io import parse_fecha, nombre_mes
                    fd = parse_fecha(fecha_val) if isinstance(fecha_val, str) else fecha_val
                    if isinstance(fd, datetime):
                        fd = fd.date()
                    if isinstance(fd, date):
                        if not mes_val:
                            mes_val = nombre_mes(fd.month)
                        if not anio_val:
                            anio_val = fd.year
                except Exception:
                    pass
            cur.execute(
                """
                INSERT INTO salida_historial
                  (fecha, mes, anio, codigo, descripcion, ubicacion, cantidad,
                   tipo_comprobante, numero_orden, maquina_sitio,
                   precio_unitario, monto_total,
                   operario_id, operario_nombre, area_id, sector_nombre,
                   es_devolucion, creado_por)
                VALUES
                  (%(fecha)s, %(mes)s, %(anio)s, %(codigo)s, %(descripcion)s, %(ubicacion)s, %(cantidad)s,
                   %(tipo_comprobante)s, %(numero_orden)s, %(maquina_sitio)s,
                   %(precio_unitario)s, %(monto_total)s,
                   %(operario_id)s, %(operario_nombre)s, %(area_id)s, %(sector_nombre)s,
                   %(es_devolucion)s, %(creado_por)s)
                """,
                {
                    "fecha": fecha_val,
                    "mes": mes_val,
                    "anio": anio_val,
                    "codigo": str(fila.get("codigo") or "").strip().upper(),
                    "descripcion": str(fila.get("descripcion") or "").strip().upper() if fila.get("descripcion") else None,
                    "ubicacion": str(fila.get("ubicacion") or "").strip().upper() if fila.get("ubicacion") else None,
                    "cantidad": fila.get("cantidad"),
                    "tipo_comprobante": str(fila.get("tipo_comprobante") or "").strip().upper() if fila.get("tipo_comprobante") else None,
                    "numero_orden": fila.get("numero_orden"),
                    "maquina_sitio": str(fila.get("maquina_sitio") or "").strip().upper() if fila.get("maquina_sitio") else None,
                    "precio_unitario": fila.get("precio_unitario"),
                    "monto_total": fila.get("monto_total"),
                    "operario_id": fila.get("operario_id"),
                    "operario_nombre": str(fila.get("operario_nombre") or "").strip().upper() if fila.get("operario_nombre") else None,
                    "area_id": fila.get("area_id"),
                    "sector_nombre": str(fila.get("sector_nombre") or "").strip().upper() if fila.get("sector_nombre") else None,
                    "es_devolucion": 1 if fila.get("es_devolucion") else 0,
                    "creado_por": fila.get("creado_por"),
                },
            )
            new_id = int(cur.lastrowid or 0)
        conn.commit()
        return new_id
    finally:
        try:
            conn.close()
        except Exception:
            pass


def historial_crear_batch(filas: list[dict[str, Any]]) -> list[int]:
    """Inserta batch de movimientos en una transaccion. Retorna ids."""
    if not filas:
        return []
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            ids: list[int] = []
            for fila in filas:
                fecha_val = fila.get("fecha")
                mes_val = fila.get("mes")
                anio_val = fila.get("anio")
                if not mes_val or not anio_val:
                    try:
                        from excel_io import parse_fecha, nombre_mes
                        fd = parse_fecha(fecha_val) if isinstance(fecha_val, str) else fecha_val
                        if isinstance(fd, datetime):
                            fd = fd.date()
                        if isinstance(fd, date):
                            if not mes_val:
                                mes_val = nombre_mes(fd.month)
                            if not anio_val:
                                anio_val = fd.year
                    except Exception:
                        pass
                cur.execute(
                    """
                    INSERT INTO salida_historial
                      (fecha, mes, anio, codigo, descripcion, ubicacion, cantidad,
                       tipo_comprobante, numero_orden, maquina_sitio,
                       precio_unitario, monto_total,
                       operario_id, operario_nombre, area_id, sector_nombre,
                       es_devolucion, creado_por)
                    VALUES
                      (%(fecha)s, %(mes)s, %(anio)s, %(codigo)s, %(descripcion)s, %(ubicacion)s, %(cantidad)s,
                       %(tipo_comprobante)s, %(numero_orden)s, %(maquina_sitio)s,
                       %(precio_unitario)s, %(monto_total)s,
                       %(operario_id)s, %(operario_nombre)s, %(area_id)s, %(sector_nombre)s,
                       %(es_devolucion)s, %(creado_por)s)
                    """,
                    {
                        "fecha": fecha_val,
                        "mes": mes_val,
                        "anio": anio_val,
                        "codigo": str(fila.get("codigo") or "").strip().upper(),
                        "descripcion": str(fila.get("descripcion") or "").strip().upper() if fila.get("descripcion") else None,
                        "ubicacion": str(fila.get("ubicacion") or "").strip().upper() if fila.get("ubicacion") else None,
                        "cantidad": fila.get("cantidad"),
                        "tipo_comprobante": str(fila.get("tipo_comprobante") or "").strip().upper() if fila.get("tipo_comprobante") else None,
                        "numero_orden": fila.get("numero_orden"),
                        "maquina_sitio": str(fila.get("maquina_sitio") or "").strip().upper() if fila.get("maquina_sitio") else None,
                        "precio_unitario": fila.get("precio_unitario"),
                        "monto_total": fila.get("monto_total"),
                        "operario_id": fila.get("operario_id"),
                        "operario_nombre": str(fila.get("operario_nombre") or "").strip().upper() if fila.get("operario_nombre") else None,
                        "area_id": fila.get("area_id"),
                        "sector_nombre": str(fila.get("sector_nombre") or "").strip().upper() if fila.get("sector_nombre") else None,
                        "es_devolucion": 1 if fila.get("es_devolucion") else 0,
                        "creado_por": fila.get("creado_por"),
                    },
                )
                ids.append(int(cur.lastrowid or 0))
        conn.commit()
        return ids
    finally:
        try:
            conn.close()
        except Exception:
            pass


def historial_por_orden_fecha(numero_orden: str, fecha: date | str | None = None) -> list[dict[str, Any]]:
    """Busca movimientos por numero_orden y fecha opcional (para remito)."""
    from excel_io import parse_fecha

    d = parse_fecha(fecha) if isinstance(fecha, str) else fecha
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            try:
                if d:
                    cur.execute("SELECT * FROM salida_historial WHERE numero_orden = %s AND fecha = %s ORDER BY id ASC", (str(numero_orden).strip(), d))
                else:
                    cur.execute("SELECT * FROM salida_historial WHERE numero_orden = %s ORDER BY fecha DESC, id DESC LIMIT 100", (str(numero_orden).strip(),))
                rows = cur.fetchall()
                return list(rows) if rows else []
            except Exception as e:
                msg = str(e).lower()
                if "1146" in msg or "doesn't exist" in msg:
                    return []
                raise
    finally:
        try:
            conn.close()
        except Exception:
            pass


# ---------- v5: soft-delete / edit auditable ----------

_ALLOWED_EDIT_FIELDS = frozenset({"tipo_comprobante", "numero_orden", "maquina_sitio", "sector_nombre", "operario_nombre", "cantidad", "precio_unitario"})


def historial_get_by_id(mov_id: int) -> dict[str, Any] | None:
    """Fetch single movimiento por id. Retorna None si no existe."""
    try:
        mid = int(mov_id)
    except (TypeError, ValueError):
        return None
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute("SELECT * FROM salida_historial WHERE id=%s LIMIT 1", (mid,))
                row = cur.fetchone()
                return dict(row) if row else None
            except Exception as e:
                msg = str(e).lower()
                if "1146" in msg or "doesn't exist" in msg:
                    return None
                raise
    finally:
        try:
            conn.close()
        except Exception:
            pass


def historial_anular(mov_id: int, anulado_por: str, motivo: str) -> dict[str, Any]:
    """Soft-anula un movimiento. Valida, actualiza anulado=1 y crea fila auditoria.

    Raises ValueError si id no existe, ya anulado, o motivo/anulado_por invalidos.
    Stock NO revertido (decision usuario: se corrige en proxima actualizacion maestro valorizado).
    """
    motivo_s = str(motivo or "").strip()
    if len(motivo_s) < 3:
        raise ValueError("motivo_anulacion requerido (3..500 caracteres).")
    if len(motivo_s) > 500:
        raise ValueError("motivo_anulacion max 500 caracteres.")
    anulado_por_s = str(anulado_por or "").strip()
    if not anulado_por_s:
        raise ValueError("anulado_por requerido (usuario).")
    anulado_por_s = anulado_por_s[:120]
    try:
        mid = int(mov_id)
    except (TypeError, ValueError):
        raise ValueError("id de movimiento invalido.")

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM salida_historial WHERE id=%s LIMIT 1", (mid,))
            before = cur.fetchone()
            if not before:
                raise ValueError(f"Movimiento {mid} no encontrado.")
            before_dict = dict(before)
            if int(before_dict.get("anulado") or 0) == 1:
                raise ValueError(f"Movimiento {mid} ya está anulado.")
            # Update
            cur.execute(
                """
                UPDATE salida_historial
                SET anulado=1, anulado_por=%s, anulado_en=NOW(), motivo_anulacion=%s, editado_en=NOW(), editado_por=%s
                WHERE id=%s AND COALESCE(anulado,0)=0
                """,
                (anulado_por_s, motivo_s, anulado_por_s, mid),
            )
            if cur.rowcount == 0:
                raise ValueError(f"Movimiento {mid} ya está anulado o no existe.")
            # Fetch after
            cur.execute("SELECT * FROM salida_historial WHERE id=%s LIMIT 1", (mid,))
            after = cur.fetchone()
            after_dict = dict(after) if after else dict(before_dict, anulado=1, anulado_por=anulado_por_s, motivo_anulacion=motivo_s)
            # Audit
            try:
                cur.execute(
                    """
                    INSERT INTO salida_historial_auditoria
                      (historial_id, accion, datos_before, datos_after, realizado_por, motivo)
                    VALUES (%s, 'anular', CAST(%s AS JSON), CAST(%s AS JSON), %s, %s)
                    """,
                    (mid, _row_to_jsonable(before_dict), _row_to_jsonable(after_dict), anulado_por_s, motivo_s),
                )
            except Exception:
                # Fallback para MariaDB que no permite CAST(... AS JSON) si columna es LONGTEXT
                try:
                    cur.execute(
                        """
                        INSERT INTO salida_historial_auditoria
                          (historial_id, accion, datos_before, datos_after, realizado_por, motivo)
                        VALUES (%s, 'anular', %s, %s, %s, %s)
                        """,
                        (mid, _row_to_jsonable(before_dict), _row_to_jsonable(after_dict), anulado_por_s, motivo_s),
                    )
                except Exception:
                    pass
        conn.commit()
        return dict(after_dict)
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


def historial_editar(mov_id: int, cambios: dict[str, Any], editado_por: str, motivo: str | None = None) -> dict[str, Any]:
    """Edita campos permitidos de un movimiento activo. Crea auditoria.

    cambios: dict con keys subset de _ALLOWED_EDIT_FIELDS. Valores None/'' => ignorar (no update).
    Realiza validaciones y recalculo monto_total si cambia cantidad/precio.
    Raises ValueError si id no existe, anulado, sin cambios, o validacion falla.
    """
    if not isinstance(cambios, dict) or not cambios:
        raise ValueError("cambios requerido (al menos un campo a editar).")
    # Filtrar solo permitidos
    filtrados: dict[str, Any] = {}
    for k, v in cambios.items():
        if k in _ALLOWED_EDIT_FIELDS:
            filtrados[k] = v
        elif k.strip().lower() in _ALLOWED_EDIT_FIELDS:
            filtrados[k.strip().lower()] = v
    # Quitar vacios que no implican edicion? Para string fields, '' podria ser invalido, pero si usuario manda '' queremos considerar?
    # Mantener: si valor es None, ignorar.
    sanitized: dict[str, Any] = {}
    for k, v in filtrados.items():
        if v is None:
            continue
        if isinstance(v, str) and k not in ("cantidad", "precio_unitario"):
            vs = v.strip()
            if vs == "":
                continue
            sanitized[k] = vs
        else:
            sanitized[k] = v
    if not sanitized:
        raise ValueError("No hay cambios validos (campos permitidos: tipo_comprobante, numero_orden, maquina_sitio, sector_nombre, operario_nombre, cantidad, precio_unitario).")
    editado_por_s = str(editado_por or "").strip()
    if not editado_por_s:
        raise ValueError("editado_por requerido.")
    editado_por_s = editado_por_s[:120]
    motivo_s = str(motivo).strip()[:500] if motivo is not None and str(motivo).strip() else None
    try:
        mid = int(mov_id)
    except (TypeError, ValueError):
        raise ValueError("id de movimiento invalido.")

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM salida_historial WHERE id=%s LIMIT 1", (mid,))
            before = cur.fetchone()
            if not before:
                raise ValueError(f"Movimiento {mid} no encontrado.")
            before_dict = dict(before)
            if int(before_dict.get("anulado") or 0) == 1:
                raise ValueError(f"Movimiento {mid} está anulado y no puede editarse.")
            # Validar/sanitizar cada campo
            updates: dict[str, Any] = {}
            for k, raw in sanitized.items():
                if k in ("tipo_comprobante", "numero_orden", "sector_nombre", "operario_nombre", "maquina_sitio"):
                    s = str(raw).strip()
                    if not s:
                        raise ValueError(f"{k} no puede estar vacio.")
                    # upper normalizado (sector, operario, tipo, maquina)
                    s_up = s.upper()
                    if k == "tipo_comprobante" and len(s_up) > 30:
                        s_up = s_up[:30]
                    elif k == "numero_orden" and len(s_up) > 40:
                        s_up = s_up[:40]
                    elif k == "maquina_sitio" and len(s_up) > 100:
                        s_up = s_up[:100]
                    elif k == "sector_nombre" and len(s_up) > 100:
                        s_up = s_up[:100]
                    elif k == "operario_nombre" and len(s_up) > 150:
                        s_up = s_up[:150]
                    # Comparar con valor actual (upper)
                    cur_val = before_dict.get(k)
                    cur_val_s = str(cur_val).strip().upper() if cur_val is not None else ""
                    if s_up == cur_val_s:
                        continue
                    updates[k] = s_up
                elif k == "cantidad":
                    try:
                        cant = float(str(raw).replace(",", "."))
                    except (TypeError, ValueError):
                        raise ValueError("cantidad invalida (debe ser numerica !=0).")
                    if cant == 0:
                        raise ValueError("cantidad no puede ser 0.")
                    # Normalizar signo segun es_devolucion?
                    # Mantener signo coherente con flag: si devolucion -> negativo, sino positivo
                    es_dev = int(before_dict.get("es_devolucion") or 0) == 1
                    # Si usuario pasa negativo en salida normal, lo aceptamos tal cual pero mantenemos es_dev para monto
                    # Para devolucion, asegurar cantidad negativa
                    if es_dev:
                        cant_stored = -abs(cant)
                    else:
                        cant_stored = abs(cant)
                    cur_cant = float(before_dict.get("cantidad") or 0)
                    if abs(cant_stored - cur_cant) < 1e-9:
                        continue
                    updates["cantidad"] = cant_stored
                elif k == "precio_unitario":
                    try:
                        precio = float(str(raw).replace(",", "."))
                    except (TypeError, ValueError):
                        raise ValueError("precio_unitario invalido.")
                    if precio < 0:
                        raise ValueError("precio_unitario no puede ser negativo.")
                    cur_precio = before_dict.get("precio_unitario")
                    cur_precio_f = float(cur_precio) if cur_precio is not None else None
                    if cur_precio_f is not None and abs(precio - cur_precio_f) < 1e-9:
                        continue
                    updates["precio_unitario"] = round(precio, 2)
            if not updates:
                raise ValueError("Sin cambios (valores iguales a los actuales).")
            # Si cambia cantidad o precio, recalcular monto_total
            nuevo_cantidad = updates.get("cantidad", before_dict.get("cantidad"))
            nuevo_precio = updates.get("precio_unitario", before_dict.get("precio_unitario"))
            if "cantidad" in updates or "precio_unitario" in updates:
                try:
                    cant_f = float(nuevo_cantidad or 0)
                    prec_f = float(nuevo_precio or 0)
                except (TypeError, ValueError):
                    cant_f = 0
                    prec_f = 0
                es_dev = int(before_dict.get("es_devolucion") or 0) == 1
                monto = round(abs(cant_f) * abs(prec_f), 2)
                if es_dev:
                    monto = -monto
                updates["monto_total"] = monto
            # Build UPDATE
            set_clauses = []
            params: list[Any] = []
            col_map = {
                "tipo_comprobante": "tipo_comprobante",
                "numero_orden": "numero_orden",
                "maquina_sitio": "maquina_sitio",
                "sector_nombre": "sector_nombre",
                "operario_nombre": "operario_nombre",
                "cantidad": "cantidad",
                "precio_unitario": "precio_unitario",
                "monto_total": "monto_total",
            }
            for uk, val in updates.items():
                col = col_map.get(uk)
                if not col:
                    continue
                set_clauses.append(f"`{col}`=%s")
                params.append(val)
            set_clauses.append("`editado_en`=NOW()")
            set_clauses.append("`editado_por`=%s")
            params.append(editado_por_s)
            params.append(mid)
            sql = f"UPDATE salida_historial SET {', '.join(set_clauses)} WHERE id=%s AND COALESCE(anulado,0)=0"
            cur.execute(sql, params)
            if cur.rowcount == 0:
                raise ValueError(f"Movimiento {mid} no encontrado o anulado.")
            cur.execute("SELECT * FROM salida_historial WHERE id=%s LIMIT 1", (mid,))
            after = cur.fetchone()
            after_dict = dict(after) if after else dict(before_dict, **updates, editado_por=editado_por_s)
            # Audit
            try:
                cur.execute(
                    """
                    INSERT INTO salida_historial_auditoria
                      (historial_id, accion, datos_before, datos_after, realizado_por, motivo)
                    VALUES (%s, 'editar', CAST(%s AS JSON), CAST(%s AS JSON), %s, %s)
                    """,
                    (mid, _row_to_jsonable(before_dict), _row_to_jsonable(after_dict), editado_por_s, motivo_s),
                )
            except Exception:
                try:
                    cur.execute(
                        """
                        INSERT INTO salida_historial_auditoria
                          (historial_id, accion, datos_before, datos_after, realizado_por, motivo)
                        VALUES (%s, 'editar', %s, %s, %s, %s)
                        """,
                        (mid, _row_to_jsonable(before_dict), _row_to_jsonable(after_dict), editado_por_s, motivo_s),
                    )
                except Exception:
                    pass
        conn.commit()
        return dict(after_dict) if 'after_dict' in locals() else dict(before_dict)
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


def historial_auditoria_listar(historial_id: int) -> list[dict[str, Any]]:
    """Lista auditoria para un historial_id ordenada por fecha desc."""
    try:
        hid = int(historial_id)
    except (TypeError, ValueError):
        raise ValueError("historial_id invalido.")
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    "SELECT * FROM salida_historial_auditoria WHERE historial_id=%s ORDER BY realizado_en DESC, id DESC",
                    (hid,),
                )
                rows = cur.fetchall()
                return list(rows) if rows else []
            except Exception as e:
                msg = str(e).lower()
                if "1146" in msg or "doesn't exist" in msg:
                    return []
                raise
    finally:
        try:
            conn.close()
        except Exception:
            pass


# ---------- salida_movimientos_diario (v4: DROP - stub, ahora derivado de historial) ----------

def diario_get(fecha: date | str) -> dict[str, Any] | None:
    """Compat stub: deriva registro diario desde salida_historial via agregacion."""
    from excel_io import parse_fecha

    d = parse_fecha(fecha) if isinstance(fecha, str) else fecha
    if d is None:
        return None
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute("SELECT * FROM salida_movimientos_diario WHERE fecha = %s", (d,))
                row = cur.fetchone()
                if row:
                    return row
            except Exception:
                pass
            # Fallback: agregar desde historial
            try:
                cur.execute(
                    """
                    SELECT
                      %s AS fecha,
                      COUNT(*) AS total_movimientos,
                      COALESCE(SUM(cantidad),0) AS total_cantidad,
                      COALESCE(SUM(monto_total),0) AS total_monto,
                      COALESCE(SUM(es_devolucion),0) AS devoluciones,
                      'abierto' AS estado
                    FROM salida_historial WHERE fecha = %s
                    """,
                    (d, d),
                )
                agg = cur.fetchone()
                if agg and int(agg.get("total_movimientos") or 0) > 0:
                    return dict(agg)
                return None
            except Exception:
                return None
    finally:
        try:
            conn.close()
        except Exception:
            pass


def diario_upsert(fecha: date | str, total_movimientos: int | None = None, total_cantidad: float | None = None, total_monto: float | None = None, devoluciones: int | None = None) -> None:
    """v4 stub: si tabla existe, upsert; sino no-op (diario es vista de historial)."""
    from excel_io import parse_fecha

    d = parse_fecha(fecha) if isinstance(fecha, str) else fecha
    assert d is not None, "fecha invalida"
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Intentar usar tabla si aun existe (compat transicion)
            try:
                cur.execute("SELECT 1 FROM salida_movimientos_diario LIMIT 1")
            except Exception:
                # Tabla DROP -> no-op
                return
            # Si existe, recalcular si no se pasan totales
            if total_movimientos is None:
                cur.execute(
                    """
                    SELECT
                      COUNT(*) AS c,
                      COALESCE(SUM(cantidad),0) AS s_cant,
                      COALESCE(SUM(monto_total),0) AS s_monto,
                      COALESCE(SUM(es_devolucion),0) AS s_dev
                    FROM salida_historial WHERE fecha = %s
                    """,
                    (d,),
                )
                agg = cur.fetchone()
                total_movimientos = int(agg["c"] or 0) if agg else 0
                total_cantidad = float(agg["s_cant"] or 0) if agg else 0.0
                total_monto = float(agg["s_monto"] or 0) if agg else 0.0
                devoluciones = int(agg["s_dev"] or 0) if agg else 0
            try:
                cur.execute(
                    """
                    INSERT INTO salida_movimientos_diario (fecha, total_movimientos, total_cantidad, total_monto, devoluciones, estado)
                    VALUES (%s, %s, %s, %s, %s, 'abierto')
                    ON DUPLICATE KEY UPDATE
                      total_movimientos = VALUES(total_movimientos),
                      total_cantidad = VALUES(total_cantidad),
                      total_monto = VALUES(total_monto),
                      devoluciones = VALUES(devoluciones)
                    """,
                    (d, total_movimientos, total_cantidad, total_monto, devoluciones),
                )
                conn.commit()
            except Exception:
                conn.rollback()
    finally:
        try:
            conn.close()
        except Exception:
            pass


def diario_cerrar(fecha: date | str, cerrado_por: str | None = None) -> None:
    from excel_io import parse_fecha

    d = parse_fecha(fecha) if isinstance(fecha, str) else fecha
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    "UPDATE salida_movimientos_diario SET estado='cerrado', cerrado_por=%s, cerrado_en=NOW() WHERE fecha=%s",
                    (cerrado_por, d),
                )
                conn.commit()
            except Exception:
                # Tabla DROP -> no-op
                pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


# ---------- salida_otif (v4: DROP - stub) ----------

def otif_listar(periodo: date | str | None = None, area_id: int | None = None, limite: int = 100) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            try:
                from excel_io import parse_fecha
                p = None
                if periodo:
                    pd = parse_fecha(periodo) if isinstance(periodo, str) else periodo
                    if pd:
                        p = date(pd.year, pd.month, 1)
                sql = "SELECT * FROM salida_otif WHERE 1=1"
                params: list[Any] = []
                if p:
                    sql += " AND periodo = %s"
                    params.append(p)
                if area_id is not None:
                    sql += " AND area_id = %s"
                    params.append(area_id)
                sql += " ORDER BY fecha_comprometida DESC, id DESC LIMIT %s"
                params.append(int(limite))
                cur.execute(sql, params)
                rows = cur.fetchall()
                return list(rows) if rows else []
            except Exception as e:
                msg = str(e).lower()
                if "1146" in msg or "doesn't exist" in msg:
                    return []
                raise
    finally:
        try:
            conn.close()
        except Exception:
            pass


def otif_crear(data: dict[str, Any]) -> int:
    raise ValueError("salida_otif obsoleta en v4 (volantazo 2026-09-16). DROP TABLE aplicada.")


def otif_actualizar_entrega(otif_id: int, fecha_entrega_real: date | str | None, cantidad_entregada: float | None = None, motivo_retraso: str | None = None, motivo_faltante: str | None = None) -> None:
    raise ValueError("salida_otif obsoleta en v4.")


def otif_kpi_mensual() -> list[dict[str, Any]]:
    return []


def otif_recalcular_todo() -> int:
    return 0


# ---------- salida_atencion_motivos (v4: DROP - stub) ----------

_CLAVE_RE = None


def _validar_clave_motivo(clave: str) -> str:
    import re
    global _CLAVE_RE
    if _CLAVE_RE is None:
        _CLAVE_RE = re.compile(r"^[A-Z0-9_]{2,30}$")
    c = str(clave or "").strip().upper().replace(" ", "_").replace("-", "_")
    while "__" in c:
        c = c.replace("__", "_")
    if not _CLAVE_RE.match(c):
        raise ValueError("Clave invalida: use solo A-Z, 0-9 y _ (2..30 chars), sin espacios. Ej SIN_STOCK.")
    return c


def motivos_listar(activos_only: bool = True) -> list[dict[str, Any]]:
    """v4 stub: tabla DROP -> retorna [] (compat, no usar)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            try:
                if activos_only:
                    cur.execute("SELECT id, clave, nombre, activo, orden, creado_en FROM salida_atencion_motivos WHERE activo=1 ORDER BY `orden` ASC, clave ASC")
                else:
                    cur.execute("SELECT id, clave, nombre, activo, orden, creado_en FROM salida_atencion_motivos ORDER BY `orden` ASC, clave ASC")
                rows = cur.fetchall()
                return list(rows) if rows else []
            except Exception as e:
                msg = str(e).lower()
                if "1146" in msg or "doesn't exist" in msg:
                    return []
                raise
    finally:
        try:
            conn.close()
        except Exception:
            pass


def motivos_resolver_clave(clave: str | None) -> dict[str, Any] | None:
    if not clave:
        return None
    c = str(clave).strip().upper()
    if not c:
        return None
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute("SELECT id, clave, nombre, activo, orden FROM salida_atencion_motivos WHERE clave=%s LIMIT 1", (c,))
                row = cur.fetchone()
                return dict(row) if row else None
            except Exception as e:
                msg = str(e).lower()
                if "1146" in msg or "doesn't exist" in msg:
                    return None
                raise
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _motivos_claves_activas_set() -> set[str]:
    try:
        rows = motivos_listar(activos_only=True)
        if rows:
            return {str(r["clave"]).strip().upper() for r in rows}
    except Exception:
        pass
    return set()


def motivos_crear(clave: str, nombre: str, orden: int | None = None, activo: int | bool = 1) -> int:
    raise ValueError("salida_atencion_motivos obsoleto en v4 (DROP). Ya no hay motivos catalogo.")


def motivos_actualizar(motivo_id: int, clave: str | None = None, nombre: str | None = None, orden: int | None = None, activo: int | bool | None = None) -> dict[str, Any]:
    raise ValueError("salida_atencion_motivos obsoleto en v4.")


def motivos_eliminar(motivo_id: int) -> dict[str, str]:
    raise ValueError("salida_atencion_motivos obsoleto en v4.")


# ---------- salida_atenciones (ventanilla - v4 simplificada) ----------

_ATENCIONES_MOTIVOS_FALLBACK = frozenset()
_ATENCIONES_MOTIVOS = _ATENCIONES_MOTIVOS_FALLBACK


def _resolve_persona_id(nombre: str | None) -> int | None:
    return None


def _resolve_area_id(sector: str | None) -> tuple[int | None, str | None]:
    if not sector:
        return None, None
    return None, str(sector).strip().upper()


def atenciones_listar(
    desde: date | str | None = None,
    hasta: date | str | None = None,
    con_retiro: int | bool | None = None,
    q: str | None = None,
    limite: int = 100,
) -> list[dict[str, Any]]:
    """Lista atenciones v4 simplificada. Filtros: fecha, con_retiro, q en observaciones/atendido_por."""
    from excel_io import parse_fecha

    d0 = parse_fecha(desde) if isinstance(desde, str) else desde
    d1 = parse_fecha(hasta) if isinstance(hasta, str) else hasta
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            try:
                sql = "SELECT * FROM salida_atenciones WHERE 1=1"
                params: list[Any] = []
                if d0:
                    sql += " AND fecha >= %s"
                    params.append(d0)
                if d1:
                    sql += " AND fecha <= %s"
                    params.append(d1)
                if con_retiro is not None and str(con_retiro) != "":
                    if isinstance(con_retiro, str):
                        v = con_retiro.strip().lower()
                        if v in ("1", "true", "si", "sí", "con"):
                            cr = 1
                        elif v in ("0", "false", "no", "sin"):
                            cr = 0
                        else:
                            try:
                                cr = int(v)
                            except ValueError:
                                cr = None
                        if cr is not None:
                            sql += " AND con_retiro = %s"
                            params.append(cr)
                    else:
                        sql += " AND con_retiro = %s"
                        params.append(1 if bool(con_retiro) else 0)
                if q:
                    qq = f"%{str(q).strip().upper()}%"
                    # v4: solo observaciones y atendido_por + fecha
                    sql += " AND (UPPER(COALESCE(observaciones,'')) LIKE %s OR UPPER(COALESCE(atendido_por,'')) LIKE %s)"
                    params.extend([qq, qq])
                sql += " ORDER BY fecha DESC, id DESC LIMIT %s"
                params.append(int(limite))
                cur.execute(sql, params)
                rows = cur.fetchall()
                return list(rows) if rows else []
            except Exception as e:
                msg = str(e).lower()
                if "1146" in msg or "doesn't exist" in msg or "unknown column" in msg:
                    # Column not found => tabla vieja sin migrar, intentar compat query minimal
                    try:
                        # Fallback legacy: select with old columns if exist
                        cur.execute("SELECT * FROM salida_atenciones ORDER BY fecha DESC, id DESC LIMIT %s", (int(limite),))
                        rows = cur.fetchall()
                        return list(rows) if rows else []
                    except Exception:
                        return []
                raise
    finally:
        try:
            conn.close()
        except Exception:
            pass


def atenciones_crear(data: dict[str, Any]) -> int:
    """Inserta una atencion ventanilla v4 simplificada.

    Espera claves: fecha (DATE), con_retiro (bool/int requerido),
    observaciones (str max 500 opcional), atendido_por (opcional),
    atendido_en (datetime opcional).
    """
    from excel_io import parse_fecha

    # fecha
    fecha_val = data.get("fecha")
    if isinstance(fecha_val, str):
        fecha_d = parse_fecha(fecha_val)
    elif isinstance(fecha_val, datetime):
        fecha_d = fecha_val.date()
    elif isinstance(fecha_val, date):
        fecha_d = fecha_val
    else:
        fecha_d = None
    if fecha_d is None:
        raise ValueError("fecha invalida (use AAAA-MM-DD).")
    # con_retiro
    cr_raw = data.get("con_retiro")
    if cr_raw is None or str(cr_raw).strip() == "":
        raise ValueError("con_retiro es obligatorio (true=retiro fuera de sistema, false=sin stock).")
    if isinstance(cr_raw, str):
        v = cr_raw.strip().lower()
        if v in ("1", "true", "si", "sí", "con", "yes"):
            con_retiro = 1
        elif v in ("0", "false", "no", "sin"):
            con_retiro = 0
        else:
            raise ValueError("con_retiro debe ser true/false.")
    else:
        con_retiro = 1 if bool(cr_raw) else 0
    # observaciones 500
    obs = data.get("observaciones")
    if obs is not None:
        obs = str(obs).strip()
        if len(obs) > 500:
            raise ValueError("observaciones max 500 caracteres.")
        if not obs:
            obs = None
    atendido_por = data.get("atendido_por") or data.get("creado_por")
    if atendido_por:
        atendido_por = str(atendido_por).strip().upper()[:120]
        if not atendido_por:
            atendido_por = None
    atendido_en = data.get("atendido_en")
    if atendido_en is None:
        # Usar ahora con fecha solicitada si es hoy, sino mediodia
        from datetime import date as _date
        if fecha_d == _date.today():
            atendido_en = datetime.now()
        else:
            atendido_en = datetime(fecha_d.year, fecha_d.month, fecha_d.day, 12, 0, 0)
    elif isinstance(atendido_en, date) and not isinstance(atendido_en, datetime):
        atendido_en = datetime(atendido_en.year, atendido_en.month, atendido_en.day, 12, 0, 0)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Detectar columnas disponibles (compat v2/v3 sin migrar)
            cur.execute(
                """
                SELECT COLUMN_NAME FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME='salida_atenciones'
                """
            )
            cols_rows = cur.fetchall()
            cols_set = {str(r.get("COLUMN_NAME") or r.get("column_name") or "").lower() for r in cols_rows} if cols_rows else set()
            has_hora = "hora" in cols_set
            has_persona = "persona_solicitante" in cols_set
            has_persona_id = "persona_id" in cols_set
            has_area_id = "area_id" in cols_set
            has_sector = "sector_nombre" in cols_set
            has_motivo = "motivo_sin_retiro" in cols_set
            has_cant = "cantidad_items_solicitados" in cols_set
            has_orden = "orden_referencia" in cols_set
            has_atendido_por_id = "atendido_por_id" in cols_set
            has_creado_por = "creado_por" in cols_set

            if has_persona or has_motivo or has_hora:
                # Tabla legacy no migrada: insert compat con defaults NULL/empty para columnas legacy requeridas
                # persona_solicitante NOT NULL en v2 -> usar atendido_por o placeholder
                persona_dummy = (atendido_por or "VENTANILLA")[:150] if has_persona else None
                # Construir insert dinamico segun columnas existentes
                cols = ["fecha", "con_retiro", "observaciones", "atendido_en", "atendido_por"]
                vals = [fecha_d, con_retiro, obs, atendido_en, atendido_por]
                col_sql = ", ".join(f"`{c}`" for c in cols)
                ph_sql = ", ".join(["%s"] * len(cols))
                # Añadir columnas legacy si existen con valores por defecto
                extra_cols: list[str] = []
                extra_vals: list[Any] = []
                if has_hora:
                    extra_cols.append("hora")
                    extra_vals.append(None)
                if has_persona:
                    extra_cols.append("persona_solicitante")
                    extra_vals.append(persona_dummy)
                if has_persona_id:
                    extra_cols.append("persona_id")
                    extra_vals.append(None)
                if has_area_id:
                    extra_cols.append("area_id")
                    extra_vals.append(None)
                if has_sector:
                    extra_cols.append("sector_nombre")
                    extra_vals.append(None)
                if has_motivo:
                    extra_cols.append("motivo_sin_retiro")
                    extra_vals.append(None)
                if has_cant:
                    extra_cols.append("cantidad_items_solicitados")
                    extra_vals.append(None)
                if has_orden:
                    extra_cols.append("orden_referencia")
                    extra_vals.append(None)
                if has_atendido_por_id:
                    extra_cols.append("atendido_por_id")
                    extra_vals.append(None)
                if has_creado_por:
                    extra_cols.append("creado_por")
                    extra_vals.append(atendido_por)
                if extra_cols:
                    col_sql += ", " + ", ".join(f"`{c}`" for c in extra_cols)
                    ph_sql += ", " + ", ".join(["%s"] * len(extra_cols))
                    vals.extend(extra_vals)
                cur.execute(f"INSERT INTO salida_atenciones ({col_sql}) VALUES ({ph_sql})", vals)
            else:
                cur.execute(
                    """
                    INSERT INTO salida_atenciones
                      (fecha, con_retiro, observaciones, atendido_en, atendido_por)
                    VALUES
                      (%s, %s, %s, %s, %s)
                    """,
                    (fecha_d, con_retiro, obs, atendido_en, atendido_por),
                )
            new_id = int(cur.lastrowid or 0)
        conn.commit()
        return new_id
    finally:
        try:
            conn.close()
        except Exception:
            pass


def atenciones_exportar_rows(desde: date | str | None = None, hasta: date | str | None = None) -> list[dict[str, Any]]:
    from excel_io import parse_fecha

    d0 = parse_fecha(desde) if isinstance(desde, str) else desde
    d1 = parse_fecha(hasta) if isinstance(hasta, str) else hasta
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            try:
                sql = "SELECT * FROM salida_atenciones WHERE 1=1"
                params: list[Any] = []
                if d0:
                    sql += " AND fecha >= %s"
                    params.append(d0)
                if d1:
                    sql += " AND fecha <= %s"
                    params.append(d1)
                sql += " ORDER BY fecha ASC, id ASC"
                cur.execute(sql, params)
                rows = cur.fetchall()
                return list(rows) if rows else []
            except Exception as e:
                msg = str(e).lower()
                if "1146" in msg or "doesn't exist" in msg:
                    return []
                raise
    finally:
        try:
            conn.close()
        except Exception:
            pass


def atenciones_kpi_mensual(periodo: str | None = None) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            try:
                if periodo:
                    from excel_io import parse_fecha
                    p = str(periodo).strip()
                    if len(p) == 7:
                        p += "-01"
                    pd = parse_fecha(p)
                    if pd:
                        cur.execute(
                            """
                            SELECT
                              DATE_FORMAT(fecha, '%%Y-%%m-01') AS periodo,
                              COUNT(*) AS total,
                              SUM(con_retiro) AS con_retiro,
                              SUM(1 - con_retiro) AS sin_retiro,
                              ROUND(SUM(con_retiro) / NULLIF(COUNT(*),0) * 100, 1) AS pct_con_retiro
                            FROM salida_atenciones
                            WHERE DATE_FORMAT(fecha, '%%Y-%%m-01') = DATE_FORMAT(%s, '%%Y-%%m-01')
                            GROUP BY DATE_FORMAT(fecha, '%%Y-%%m-01')
                            """,
                            (pd,),
                        )
                        rows = cur.fetchall()
                        return list(rows) if rows else []
                    return []
                cur.execute(
                    """
                    SELECT
                      DATE_FORMAT(fecha, '%%Y-%%m-01') AS periodo,
                      COUNT(*) AS total,
                      SUM(con_retiro) AS con_retiro,
                      SUM(1 - con_retiro) AS sin_retiro,
                      ROUND(SUM(con_retiro) / NULLIF(COUNT(*),0) * 100, 1) AS pct_con_retiro
                    FROM salida_atenciones
                    GROUP BY DATE_FORMAT(fecha, '%%Y-%%m-01')
                    ORDER BY periodo DESC
                    """
                )
                rows = cur.fetchall()
                return list(rows) if rows else []
            except Exception as e:
                msg = str(e).lower()
                if "1146" in msg or "doesn't exist" in msg or "unknown column" in msg:
                    return []
                raise
    finally:
        try:
            conn.close()
        except Exception:
            pass


def atenciones_por_dia(desde: date | str | None = None, hasta: date | str | None = None) -> list[dict[str, Any]]:
    from excel_io import parse_fecha

    d0 = parse_fecha(desde) if isinstance(desde, str) else desde
    d1 = parse_fecha(hasta) if isinstance(hasta, str) else hasta
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            try:
                sql = """
                    SELECT
                      fecha,
                      COUNT(*) AS total,
                      SUM(con_retiro) AS con_retiro,
                      SUM(1 - con_retiro) AS sin_retiro,
                      ROUND(SUM(con_retiro) / NULLIF(COUNT(*),0) * 100, 1) AS pct_con_retiro
                    FROM salida_atenciones
                    WHERE 1=1
                """
                params: list[Any] = []
                if d0:
                    sql += " AND fecha >= %s"
                    params.append(d0)
                if d1:
                    sql += " AND fecha <= %s"
                    params.append(d1)
                sql += " GROUP BY fecha ORDER BY fecha DESC"
                cur.execute(sql, params)
                rows = cur.fetchall()
                return list(rows) if rows else []
            except Exception as e:
                msg = str(e).lower()
                if "1146" in msg or "doesn't exist" in msg or "unknown column" in msg:
                    return []
                raise
    finally:
        try:
            conn.close()
        except Exception:
            pass

