# -*- coding: utf-8 -*-
"""
cola_repo.py — Acceso a la cola de impresión de etiquetas.

Este módulo es la ÚNICA puerta de entrada a la persistencia de la cola. Hoy usa
SQLite (archivo local `cola.db`, sin dependencias externas) pero está aislado a
propósito: el resto del servicio (main.py) sólo llama a las funciones públicas de
acá. El día que se migre a la base central (MariaDB) se reimplementa este archivo
manteniendo la misma firma de funciones, sin tocar el resto del servicio.

Estados de un pedido:
  - "pendiente"  : esperando que el print-agent lo imprima.
  - "impreso"    : el print-agent confirmó impresión exitosa.
  - "descartado" : superó el máximo de intentos fallidos; ya no se reintenta.

Nota sobre los reintentos:
  El print-agent toma los pedidos "pendiente" por polling. Si reporta un error,
  el pedido vuelve a "pendiente" (con el contador de intentos +1) para reintentar,
  salvo que ya haya alcanzado MAX_INTENTOS, en cuyo caso pasa a "descartado" y deja
  de aparecer en la lista de pendientes.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Optional

# --- Estados (constantes para no repetir literales sueltos) -------------------
ESTADO_PENDIENTE = "pendiente"
ESTADO_IMPRESO = "impreso"
ESTADO_DESCARTADO = "descartado"

# Resultados que puede reportar el print-agent al confirmar.
RESULTADO_IMPRESO = "impreso"
RESULTADO_ERROR = "error"

# Cantidad máxima de intentos fallidos antes de descartar el pedido.
MAX_INTENTOS = 3

# Ruta del archivo SQLite. Configurable por entorno para tests / despliegues.
DB_PATH = os.environ.get(
    "ETIQUETAS_DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "cola.db"),
)

# Columnas que se exponen al resto del servicio (orden estable).
_COLUMNAS = (
    "id",
    "tipo",
    "texto_libre",
    "codigo",
    "descripcion",
    "ubicacion",
    "qr_data",
    "cantidad",
    "solicitado_por",
    "estado",
    "intentos",
    "error_msg",
    "creado_en",
    "actualizado_en",
)


def _ahora_iso() -> str:
    """Timestamp UTC en ISO 8601 (ordenable lexicográficamente)."""
    return datetime.now(timezone.utc).isoformat()


def _conectar() -> sqlite3.Connection:
    """Abre una conexión nueva por operación (simple y seguro entre threads)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def init_db() -> None:
    """Crea la tabla si no existe. Idempotente: se puede llamar al arrancar."""
    with _conectar() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS etiquetas (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo           TEXT    NOT NULL,
                texto_libre    TEXT,
                codigo         TEXT,
                descripcion    TEXT,
                ubicacion      TEXT,
                qr_data        TEXT,
                cantidad       INTEGER NOT NULL DEFAULT 1,
                solicitado_por TEXT,
                estado         TEXT    NOT NULL DEFAULT 'pendiente',
                intentos       INTEGER NOT NULL DEFAULT 0,
                error_msg      TEXT,
                creado_en      TEXT    NOT NULL,
                actualizado_en TEXT    NOT NULL
            );
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_etiquetas_estado "
            "ON etiquetas (estado, creado_en, id);"
        )


def _row_a_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {col: row[col] for col in _COLUMNAS}


def crear_pedido(datos: dict[str, Any]) -> dict[str, Any]:
    """
    Inserta un pedido nuevo en estado "pendiente" y devuelve el registro creado.

    `datos` debe traer las claves ya validadas por la capa de modelos:
    tipo, texto_libre, codigo, descripcion, ubicacion, qr_data, cantidad,
    solicitado_por.
    """
    ahora = _ahora_iso()
    with _conectar() as conn:
        cur = conn.execute(
            """
            INSERT INTO etiquetas (
                tipo, texto_libre, codigo, descripcion, ubicacion, qr_data,
                cantidad, solicitado_por, estado, intentos, error_msg,
                creado_en, actualizado_en
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, ?, ?);
            """,
            (
                datos.get("tipo"),
                datos.get("texto_libre"),
                datos.get("codigo"),
                datos.get("descripcion"),
                datos.get("ubicacion"),
                datos.get("qr_data"),
                int(datos.get("cantidad", 1) or 1),
                datos.get("solicitado_por"),
                ESTADO_PENDIENTE,
                ahora,
                ahora,
            ),
        )
        nuevo_id = int(cur.lastrowid)
    pedido = obtener_pedido(nuevo_id)
    assert pedido is not None  # recién insertado
    return pedido


def listar_pendientes() -> list[dict[str, Any]]:
    """Devuelve los pedidos "pendiente" ordenados por antigüedad (FIFO)."""
    with _conectar() as conn:
        filas = conn.execute(
            "SELECT * FROM etiquetas WHERE estado = ? "
            "ORDER BY creado_en ASC, id ASC;",
            (ESTADO_PENDIENTE,),
        ).fetchall()
    return [_row_a_dict(f) for f in filas]


def obtener_pedido(pedido_id: int) -> Optional[dict[str, Any]]:
    """Devuelve un pedido por id, o None si no existe."""
    with _conectar() as conn:
        fila = conn.execute(
            "SELECT * FROM etiquetas WHERE id = ?;", (pedido_id,)
        ).fetchone()
    return _row_a_dict(fila) if fila else None


def confirmar_pedido(
    pedido_id: int,
    resultado: str,
    error_msg: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """
    Aplica el resultado reportado por el print-agent sobre un pedido pendiente.

    - resultado == "impreso": el pedido pasa a "impreso".
    - resultado == "error":   suma 1 al contador de intentos; si alcanzó
      MAX_INTENTOS pasa a "descartado", si no vuelve a "pendiente" para reintentar.

    Devuelve el pedido actualizado, o None si el id no existe.
    Lanza ValueError si el pedido no estaba en estado "pendiente" (ya resuelto).
    """
    pedido = obtener_pedido(pedido_id)
    if pedido is None:
        return None
    if pedido["estado"] != ESTADO_PENDIENTE:
        raise ValueError(
            f"El pedido {pedido_id} no está pendiente (estado actual: "
            f"'{pedido['estado']}'); no se puede confirmar de nuevo."
        )

    ahora = _ahora_iso()

    if resultado == RESULTADO_IMPRESO:
        nuevo_estado = ESTADO_IMPRESO
        nuevos_intentos = pedido["intentos"]
        nuevo_error = None
    elif resultado == RESULTADO_ERROR:
        nuevos_intentos = pedido["intentos"] + 1
        nuevo_estado = (
            ESTADO_DESCARTADO if nuevos_intentos >= MAX_INTENTOS else ESTADO_PENDIENTE
        )
        nuevo_error = error_msg
    else:
        raise ValueError(
            f"Resultado inválido: '{resultado}'. "
            f"Use '{RESULTADO_IMPRESO}' o '{RESULTADO_ERROR}'."
        )

    with _conectar() as conn:
        conn.execute(
            "UPDATE etiquetas SET estado = ?, intentos = ?, error_msg = ?, "
            "actualizado_en = ? WHERE id = ?;",
            (nuevo_estado, nuevos_intentos, nuevo_error, ahora, pedido_id),
        )
    return obtener_pedido(pedido_id)
