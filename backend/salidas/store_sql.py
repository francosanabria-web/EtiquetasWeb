# -*- coding: utf-8 -*-
"""Store SQL para modulo Salidas (opcional, esqueleto).

Funciones minimas para historial / diario / OTIF contra MariaDB.
No usado aun por service.py (sigue en Excel); dejar como referencia
para la reimplementacion de excel_io.py contra MariaDB con feature flag
SALIDAS_DB_ENABLED=1.

Todas las funciones son idempotentes y usan transacciones cortas.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from db import get_connection


# ---------- helpers OTIF ----------

def _calc_otif_flags(fecha_comprometida: date | str | None, fecha_entrega_real: date | str | None, cantidad_solicitada: float, cantidad_entregada: float) -> tuple[int, int, int]:
    """Calcula (en_tiempo, completo, otif) segun reglas de negocio."""
    from excel_io import parse_fecha  # reutiliza parser existente

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
    """Primer dia del mes de fecha_comprometida."""
    from excel_io import parse_fecha

    d = parse_fecha(fecha_comprometida) if isinstance(fecha_comprometida, str) else fecha_comprometida
    if d is None:
        return None
    return date(d.year, d.month, 1)


# ---------- salida_historial ----------

def historial_listar(desde: date | str | None = None, hasta: date | str | None = None, limite: int = 100, codigo: str | None = None) -> list[dict[str, Any]]:
    """Lista movimientos con filtros opcionales."""
    from excel_io import parse_fecha

    d0 = parse_fecha(desde) if isinstance(desde, str) else desde
    d1 = parse_fecha(hasta) if isinstance(hasta, str) else hasta
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            sql = "SELECT * FROM salida_historial WHERE 1=1"
            params: list[Any] = []
            if d0:
                sql += " AND fecha >= %s"
                params.append(d0)
            if d1:
                sql += " AND fecha <= %s"
                params.append(d1)
            if codigo:
                sql += " AND codigo = %s"
                params.append(str(codigo).strip().upper())
            sql += " ORDER BY fecha DESC, id DESC LIMIT %s"
            params.append(int(limite))
            cur.execute(sql, params)
            rows = cur.fetchall()
            return list(rows) if rows else []
    finally:
        try:
            conn.close()
        except Exception:
            pass


def historial_crear(fila: dict[str, Any]) -> int:
    """Inserta un movimiento en salida_historial. Retorna id insertado.

    Espera claves: fecha, codigo, cantidad, descripcion, ubicacion,
    tipo_comprobante, numero_orden, maquina_sitio, precio_unitario,
    monto_total, operario_id, operario_nombre, area_id, sector_nombre,
    es_devolucion, creado_por
    """
    en_tiempo_dummy = 0  # no usado aqui
    conn = get_connection()
    try:
        with conn.cursor() as cur:
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
                    "fecha": fila.get("fecha"),
                    "mes": fila.get("mes"),
                    "anio": fila.get("anio"),
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


# ---------- salida_movimientos_diario ----------

def diario_get(fecha: date | str) -> dict[str, Any] | None:
    from excel_io import parse_fecha

    d = parse_fecha(fecha) if isinstance(fecha, str) else fecha
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM salida_movimientos_diario WHERE fecha = %s", (d,))
            return cur.fetchone()
    finally:
        try:
            conn.close()
        except Exception:
            pass


def diario_upsert(fecha: date | str, total_movimientos: int | None = None, total_cantidad: float | None = None, total_monto: float | None = None, devoluciones: int | None = None) -> None:
    """Upsert header diario. Si no se pasan totales, los recalcula desde historial."""
    from excel_io import parse_fecha

    d = parse_fecha(fecha) if isinstance(fecha, str) else fecha
    assert d is not None, "fecha invalida"
    conn = get_connection()
    try:
        with conn.cursor() as cur:
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
            cur.execute(
                "UPDATE salida_movimientos_diario SET estado='cerrado', cerrado_por=%s, cerrado_en=NOW() WHERE fecha=%s",
                (cerrado_por, d),
            )
        conn.commit()
    finally:
        try:
            conn.close()
        except Exception:
            pass


# ---------- salida_otif ----------

def otif_listar(periodo: date | str | None = None, area_id: int | None = None, limite: int = 100) -> list[dict[str, Any]]:
    from excel_io import parse_fecha

    p = None
    if periodo:
        pd = parse_fecha(periodo) if isinstance(periodo, str) else periodo
        if pd:
            p = date(pd.year, pd.month, 1)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
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
    finally:
        try:
            conn.close()
        except Exception:
            pass


def otif_crear(data: dict[str, Any]) -> int:
    """Crea fila OTIF. Calcula flags y periodo en app."""
    en_tiempo, completo, otif = _calc_otif_flags(
        data.get("fecha_comprometida"), data.get("fecha_entrega_real"),
        float(data.get("cantidad_solicitada") or 0), float(data.get("cantidad_entregada") or 0)
    )
    periodo = _periodo_desde_fecha(data.get("fecha_comprometida"))
    # Si ya trae flags explicitos, respetarlos (permite override)
    if "en_tiempo" in data:
        en_tiempo = int(bool(data["en_tiempo"]))
    if "completo" in data:
        completo = int(bool(data["completo"]))
    if "otif" in data:
        otif = int(bool(data["otif"]))
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO salida_otif
                  (salida_id, solicitud_id, codigo, descripcion,
                   fecha_solicitada, fecha_comprometida, fecha_entrega_real,
                   cantidad_solicitada, cantidad_entregada,
                   en_tiempo, completo, otif,
                   motivo_retraso, motivo_faltante,
                   responsable_id, area_id, periodo, observaciones)
                VALUES
                  (%(salida_id)s, %(solicitud_id)s, %(codigo)s, %(descripcion)s,
                   %(fecha_solicitada)s, %(fecha_comprometida)s, %(fecha_entrega_real)s,
                   %(cantidad_solicitada)s, %(cantidad_entregada)s,
                   %(en_tiempo)s, %(completo)s, %(otif)s,
                   %(motivo_retraso)s, %(motivo_faltante)s,
                   %(responsable_id)s, %(area_id)s, %(periodo)s, %(observaciones)s)
                """,
                {
                    "salida_id": data.get("salida_id"),
                    "solicitud_id": data.get("solicitud_id"),
                    "codigo": str(data.get("codigo") or "").strip().upper() if data.get("codigo") else None,
                    "descripcion": data.get("descripcion"),
                    "fecha_solicitada": data.get("fecha_solicitada"),
                    "fecha_comprometida": data.get("fecha_comprometida"),
                    "fecha_entrega_real": data.get("fecha_entrega_real"),
                    "cantidad_solicitada": data.get("cantidad_solicitada"),
                    "cantidad_entregada": data.get("cantidad_entregada") or 0,
                    "en_tiempo": en_tiempo,
                    "completo": completo,
                    "otif": otif,
                    "motivo_retraso": data.get("motivo_retraso"),
                    "motivo_faltante": data.get("motivo_faltante"),
                    "responsable_id": data.get("responsable_id"),
                    "area_id": data.get("area_id"),
                    "periodo": periodo,
                    "observaciones": data.get("observaciones"),
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


def otif_actualizar_entrega(otif_id: int, fecha_entrega_real: date | str | None, cantidad_entregada: float | None = None, motivo_retraso: str | None = None, motivo_faltante: str | None = None) -> None:
    """Actualiza entrega real y recalcula flags."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT fecha_comprometida, cantidad_solicitada, cantidad_entregada FROM salida_otif WHERE id=%s", (otif_id,))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"OTIF {otif_id} no existe")
            fc = row["fecha_comprometida"]
            cs = float(row["cantidad_solicitada"] or 0)
            ce = float(cantidad_entregada if cantidad_entregada is not None else row["cantidad_entregada"] or 0)
            en_tiempo, completo, otif = _calc_otif_flags(fc, fecha_entrega_real, cs, ce)
            cur.execute(
                """
                UPDATE salida_otif
                SET fecha_entrega_real = %s,
                    cantidad_entregada = %s,
                    en_tiempo = %s,
                    completo = %s,
                    otif = %s,
                    motivo_retraso = COALESCE(%s, motivo_retraso),
                    motivo_faltante = COALESCE(%s, motivo_faltante)
                WHERE id = %s
                """,
                (fecha_entrega_real, ce, en_tiempo, completo, otif, motivo_retraso, motivo_faltante, otif_id),
            )
        conn.commit()
    finally:
        try:
            conn.close()
        except Exception:
            pass


def otif_kpi_mensual() -> list[dict[str, Any]]:
    """OTIF % mensual."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  periodo AS mes,
                  COUNT(*) AS total_entregas,
                  SUM(otif) AS entregas_otif,
                  ROUND(AVG(otif) * 100, 2) AS otif_pct,
                  ROUND(AVG(en_tiempo) * 100, 2) AS on_time_pct,
                  ROUND(AVG(completo) * 100, 2) AS in_full_pct
                FROM salida_otif
                WHERE periodo IS NOT NULL
                GROUP BY periodo
                ORDER BY periodo DESC
                """
            )
            rows = cur.fetchall()
            return list(rows) if rows else []
    finally:
        try:
            conn.close()
        except Exception:
            pass


def otif_recalcular_todo() -> int:
    """Recalcula flags y periodo para filas con periodo NULL o desactualizadas. Retorna filas afectadas."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE salida_otif
                SET en_tiempo = IF(fecha_entrega_real IS NOT NULL AND fecha_entrega_real <= fecha_comprometida, 1, 0),
                    completo  = IF(cantidad_entregada >= cantidad_solicitada, 1, 0),
                    otif      = IF(fecha_entrega_real IS NOT NULL AND fecha_entrega_real <= fecha_comprometida AND cantidad_entregada >= cantidad_solicitada, 1, 0),
                    periodo   = DATE_FORMAT(fecha_comprometida, '%Y-%m-01')
                WHERE periodo IS NULL
                   OR en_tiempo != IF(fecha_entrega_real IS NOT NULL AND fecha_entrega_real <= fecha_comprometida, 1, 0)
                   OR completo  != IF(cantidad_entregada >= cantidad_solicitada, 1, 0)
                """
            )
            n = int(cur.rowcount or 0)
        conn.commit()
        return n
    finally:
        try:
            conn.close()
        except Exception:
            pass
