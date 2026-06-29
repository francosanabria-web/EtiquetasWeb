# -*- coding: utf-8 -*-
"""Persistencia SQLite para minutas de reunión semanal."""

from __future__ import annotations

import os
import smtplib
import sqlite3
from datetime import date, datetime, timezone
from typing import Any, Optional

from models import (
    Actualizacion,
    ActualizacionCreate,
    EntregaParcial,
    EntregaParcialCreate,
    EstadoEntrega,
    EstadoSesion,
    SesionDetalle,
    SesionResumen,
    Solicitud,
    SolicitudCreate,
    SolicitudUpdate,
    Tema,
    TemaCreate,
    TemaUpdate,
    Urgencia,
)

DB_PATH = os.environ.get(
    "MINUTAS_DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "minutas.db"),
)


def _ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _semana_iso(fecha: date | None = None) -> str:
    d = fecha or date.today()
    iso = d.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _conectar() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def init_db() -> None:
    with _conectar() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sesiones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,
                semana_iso TEXT NOT NULL,
                estado TEXT NOT NULL DEFAULT 'abierta',
                responsable TEXT,
                notas_generales TEXT,
                email_enviado_en TEXT,
                creado_en TEXT NOT NULL,
                actualizado_en TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS solicitudes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sesion_origen_id INTEGER NOT NULL,
                numero_referencia TEXT NOT NULL,
                solicitante TEXT NOT NULL,
                urgencia TEXT NOT NULL,
                cantidad_items INTEGER NOT NULL,
                descripcion TEXT,
                estado_entrega TEXT NOT NULL DEFAULT 'pendiente',
                cerrado INTEGER NOT NULL DEFAULT 0,
                creado_en TEXT NOT NULL,
                actualizado_en TEXT NOT NULL,
                FOREIGN KEY (sesion_origen_id) REFERENCES sesiones(id)
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_solicitud_ref_activa
                ON solicitudes(numero_referencia)
                WHERE cerrado = 0;

            CREATE TABLE IF NOT EXISTS entregas_parciales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                solicitud_id INTEGER NOT NULL,
                fecha TEXT NOT NULL,
                cantidad INTEGER NOT NULL,
                observacion TEXT,
                creado_en TEXT NOT NULL,
                FOREIGN KEY (solicitud_id) REFERENCES solicitudes(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS temas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sesion_origen_id INTEGER NOT NULL,
                titulo TEXT NOT NULL,
                descripcion TEXT,
                resuelto INTEGER NOT NULL DEFAULT 0,
                creado_en TEXT NOT NULL,
                actualizado_en TEXT NOT NULL,
                FOREIGN KEY (sesion_origen_id) REFERENCES sesiones(id)
            );

            CREATE TABLE IF NOT EXISTS actualizaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sesion_id INTEGER NOT NULL,
                solicitud_id INTEGER,
                texto TEXT NOT NULL,
                autor TEXT,
                creado_en TEXT NOT NULL,
                FOREIGN KEY (sesion_id) REFERENCES sesiones(id) ON DELETE CASCADE,
                FOREIGN KEY (solicitud_id) REFERENCES solicitudes(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS sesion_solicitudes (
                sesion_id INTEGER NOT NULL,
                solicitud_id INTEGER NOT NULL,
                PRIMARY KEY (sesion_id, solicitud_id),
                FOREIGN KEY (sesion_id) REFERENCES sesiones(id) ON DELETE CASCADE,
                FOREIGN KEY (solicitud_id) REFERENCES solicitudes(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS sesion_temas (
                sesion_id INTEGER NOT NULL,
                tema_id INTEGER NOT NULL,
                PRIMARY KEY (sesion_id, tema_id),
                FOREIGN KEY (sesion_id) REFERENCES sesiones(id) ON DELETE CASCADE,
                FOREIGN KEY (tema_id) REFERENCES temas(id) ON DELETE CASCADE
            );
            """
        )


def _row_sesion(row: sqlite3.Row) -> SesionResumen:
    return SesionResumen(
        id=row["id"],
        fecha=row["fecha"],
        semana_iso=row["semana_iso"],
        estado=EstadoSesion(row["estado"]),
        responsable=row["responsable"],
        notas_generales=row["notas_generales"],
        email_enviado_en=row["email_enviado_en"],
        creado_en=row["creado_en"],
        actualizado_en=row["actualizado_en"],
    )


def _calcular_estado_entrega(cantidad_total: int, entregas: list[EntregaParcial]) -> EstadoEntrega:
    entregado = sum(e.cantidad for e in entregas)
    if entregado <= 0:
        return EstadoEntrega.PENDIENTE
    if entregado >= cantidad_total:
        return EstadoEntrega.COMPLETO
    return EstadoEntrega.PARCIAL


def _entregas_por_solicitud(conn: sqlite3.Connection, solicitud_id: int) -> list[EntregaParcial]:
    rows = conn.execute(
        "SELECT * FROM entregas_parciales WHERE solicitud_id = ? ORDER BY fecha, id",
        (solicitud_id,),
    ).fetchall()
    return [
        EntregaParcial(
            id=r["id"],
            solicitud_id=r["solicitud_id"],
            fecha=r["fecha"],
            cantidad=r["cantidad"],
            observacion=r["observacion"],
            creado_en=r["creado_en"],
        )
        for r in rows
    ]


def _actualizaciones_solicitud(
    conn: sqlite3.Connection, sesion_id: int, solicitud_id: int
) -> list[Actualizacion]:
    rows = conn.execute(
        """
        SELECT * FROM actualizaciones
        WHERE sesion_id = ? AND solicitud_id = ?
        ORDER BY creado_en, id
        """,
        (sesion_id, solicitud_id),
    ).fetchall()
    return [
        Actualizacion(
            id=r["id"],
            sesion_id=r["sesion_id"],
            solicitud_id=r["solicitud_id"],
            texto=r["texto"],
            autor=r["autor"],
            creado_en=r["creado_en"],
        )
        for r in rows
    ]


def _solicitud_completa(conn: sqlite3.Connection, row: sqlite3.Row, sesion_id: int) -> Solicitud:
    entregas = _entregas_parciales(conn, row["id"])
    actualizaciones = _actualizaciones_solicitud(conn, sesion_id, row["id"])
    return Solicitud(
        id=row["id"],
        sesion_origen_id=row["sesion_origen_id"],
        numero_referencia=row["numero_referencia"],
        solicitante=row["solicitante"],
        urgencia=Urgencia(row["urgencia"]),
        cantidad_items=row["cantidad_items"],
        descripcion=row["descripcion"],
        estado_entrega=EstadoEntrega(row["estado_entrega"]),
        cerrado=bool(row["cerrado"]),
        entregas=entregas,
        actualizaciones=actualizaciones,
        creado_en=row["creado_en"],
        actualizado_en=row["actualizado_en"],
    )


def obtener_sesion_abierta(conn: sqlite3.Connection) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM sesiones WHERE estado = ? ORDER BY id DESC LIMIT 1",
        (EstadoSesion.ABIERTA.value,),
    ).fetchone()


def listar_sesiones(limite: int = 20) -> list[SesionResumen]:
    with _conectar() as conn:
        rows = conn.execute(
            "SELECT * FROM sesiones ORDER BY id DESC LIMIT ?",
            (limite,),
        ).fetchall()
        return [_row_sesion(r) for r in rows]


def obtener_sesion_detalle(sesion_id: int) -> Optional[SesionDetalle]:
    with _conectar() as conn:
        row = conn.execute("SELECT * FROM sesiones WHERE id = ?", (sesion_id,)).fetchone()
        if not row:
            return None

        sol_rows = conn.execute(
            """
            SELECT s.* FROM solicitudes s
            INNER JOIN sesion_solicitudes ss ON ss.solicitud_id = s.id
            WHERE ss.sesion_id = ?
            ORDER BY s.urgencia DESC, s.actualizado_en DESC
            """,
            (sesion_id,),
        ).fetchall()

        tema_rows = conn.execute(
            """
            SELECT t.* FROM temas t
            INNER JOIN sesion_temas st ON st.tema_id = t.id
            WHERE st.sesion_id = ?
            ORDER BY t.resuelto ASC, t.actualizado_en DESC
            """,
            (sesion_id,),
        ).fetchall()

        act_rows = conn.execute(
            """
            SELECT * FROM actualizaciones
            WHERE sesion_id = ? AND solicitud_id IS NULL
            ORDER BY creado_en, id
            """,
            (sesion_id,),
        ).fetchall()

        solicitudes = [_solicitud_completa(conn, r, sesion_id) for r in sol_rows]
        temas = [
            Tema(
                id=r["id"],
                sesion_origen_id=r["sesion_origen_id"],
                titulo=r["titulo"],
                descripcion=r["descripcion"],
                resuelto=bool(r["resuelto"]),
                creado_en=r["creado_en"],
                actualizado_en=r["actualizado_en"],
            )
            for r in tema_rows
        ]
        actualizaciones = [
            Actualizacion(
                id=r["id"],
                sesion_id=r["sesion_id"],
                solicitud_id=r["solicitud_id"],
                texto=r["texto"],
                autor=r["autor"],
                creado_en=r["creado_en"],
            )
            for r in act_rows
        ]

        base = _row_sesion(row)
        return SesionDetalle(
            **base.model_dump(),
            solicitudes=solicitudes,
            temas=temas,
            actualizaciones=actualizaciones,
        )


def _vincular_solicitud_sesion(conn: sqlite3.Connection, sesion_id: int, solicitud_id: int) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO sesion_solicitudes (sesion_id, solicitud_id) VALUES (?, ?)",
        (sesion_id, solicitud_id),
    )


def _vincular_tema_sesion(conn: sqlite3.Connection, sesion_id: int, tema_id: int) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO sesion_temas (sesion_id, tema_id) VALUES (?, ?)",
        (sesion_id, tema_id),
    )


def _solicitudes_pendientes_arrastre(conn: sqlite3.Connection) -> list[int]:
    rows = conn.execute(
        """
        SELECT id FROM solicitudes
        WHERE cerrado = 0 AND estado_entrega != ?
        ORDER BY actualizado_en DESC
        """,
        (EstadoEntrega.COMPLETO.value,),
    ).fetchall()
    return [r["id"] for r in rows]


def _temas_pendientes_arrastre(conn: sqlite3.Connection) -> list[int]:
    rows = conn.execute(
        "SELECT id FROM temas WHERE resuelto = 0 ORDER BY actualizado_en DESC"
    ).fetchall()
    return [r["id"] for r in rows]


def iniciar_sesion_semana(
    notas_generales: Optional[str] = None,
    responsable: Optional[str] = None,
) -> SesionDetalle:
    with _conectar() as conn:
        abierta = obtener_sesion_abierta(conn)
        if abierta:
            raise ValueError("Ya existe una reunión abierta. Cerrala antes de iniciar otra.")

        ahora = _ahora_iso()
        hoy = date.today().isoformat()
        semana = _semana_iso()
        cur = conn.execute(
            """
            INSERT INTO sesiones (fecha, semana_iso, estado, responsable, notas_generales, creado_en, actualizado_en)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (hoy, semana, EstadoSesion.ABIERTA.value, responsable, notas_generales, ahora, ahora),
        )
        sesion_id = cur.lastrowid
        assert sesion_id is not None

        for sol_id in _solicitudes_pendientes_arrastre(conn):
            _vincular_solicitud_sesion(conn, sesion_id, sol_id)
        for tema_id in _temas_pendientes_arrastre(conn):
            _vincular_tema_sesion(conn, sesion_id, tema_id)

        conn.commit()

    detalle = obtener_sesion_detalle(sesion_id)
    assert detalle is not None
    return detalle


def actualizar_sesion(
    sesion_id: int,
    notas_generales: Optional[str] = None,
    responsable: Optional[str] = None,
) -> SesionResumen:
    with _conectar() as conn:
        row = conn.execute("SELECT * FROM sesiones WHERE id = ?", (sesion_id,)).fetchone()
        if not row:
            raise LookupError("Sesión no encontrada.")
        if row["estado"] != EstadoSesion.ABIERTA.value:
            raise ValueError("Solo se puede editar una sesión abierta.")

        ahora = _ahora_iso()
        conn.execute(
            """
            UPDATE sesiones
            SET notas_generales = COALESCE(?, notas_generales),
                responsable = COALESCE(?, responsable),
                actualizado_en = ?
            WHERE id = ?
            """,
            (notas_generales, responsable, ahora, sesion_id),
        )
        conn.commit()
        updated = conn.execute("SELECT * FROM sesiones WHERE id = ?", (sesion_id,)).fetchone()
        assert updated is not None
        return _row_sesion(updated)


def crear_solicitud(sesion_id: int, data: SolicitudCreate) -> Solicitud:
    with _conectar() as conn:
        ses = conn.execute("SELECT * FROM sesiones WHERE id = ?", (sesion_id,)).fetchone()
        if not ses:
            raise LookupError("Sesión no encontrada.")
        if ses["estado"] != EstadoSesion.ABIERTA.value:
            raise ValueError("La sesión no está abierta.")

        dup = conn.execute(
            "SELECT id FROM solicitudes WHERE numero_referencia = ? AND cerrado = 0",
            (data.numero_referencia,),
        ).fetchone()
        if dup:
            raise ValueError(
                f"Ya existe una solicitud activa con referencia '{data.numero_referencia}'."
            )

        ahora = _ahora_iso()
        cur = conn.execute(
            """
            INSERT INTO solicitudes (
                sesion_origen_id, numero_referencia, solicitante, urgencia,
                cantidad_items, descripcion, estado_entrega, cerrado, creado_en, actualizado_en
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
            """,
            (
                sesion_id,
                data.numero_referencia,
                data.solicitante,
                data.urgencia.value,
                data.cantidad_items,
                data.descripcion,
                EstadoEntrega.PENDIENTE.value,
                ahora,
                ahora,
            ),
        )
        sol_id = cur.lastrowid
        assert sol_id is not None
        _vincular_solicitud_sesion(conn, sesion_id, sol_id)
        conn.commit()
        row = conn.execute("SELECT * FROM solicitudes WHERE id = ?", (sol_id,)).fetchone()
        assert row is not None
        return _solicitud_completa(conn, row, sesion_id)


def actualizar_solicitud(sesion_id: int, solicitud_id: int, data: SolicitudUpdate) -> Solicitud:
    with _conectar() as conn:
        row = conn.execute("SELECT * FROM solicitudes WHERE id = ?", (solicitud_id,)).fetchone()
        if not row:
            raise LookupError("Solicitud no encontrada.")

        if data.numero_referencia and data.numero_referencia != row["numero_referencia"]:
            dup = conn.execute(
                """
                SELECT id FROM solicitudes
                WHERE numero_referencia = ? AND cerrado = 0 AND id != ?
                """,
                (data.numero_referencia, solicitud_id),
            ).fetchone()
            if dup:
                raise ValueError("Referencia duplicada en solicitudes activas.")

        campos: dict[str, Any] = {}
        for key in ("numero_referencia", "solicitante", "descripcion"):
            val = getattr(data, key)
            if val is not None:
                campos[key] = val
        if data.urgencia is not None:
            campos["urgencia"] = data.urgencia.value
        if data.cantidad_items is not None:
            campos["cantidad_items"] = data.cantidad_items
        if data.estado_entrega is not None:
            campos["estado_entrega"] = data.estado_entrega.value
        if data.cerrado is not None:
            campos["cerrado"] = 1 if data.cerrado else 0

        if not campos:
            return _solicitud_completa(conn, row, sesion_id)

        campos["actualizado_en"] = _ahora_iso()
        sets = ", ".join(f"{k} = ?" for k in campos)
        conn.execute(
            f"UPDATE solicitudes SET {sets} WHERE id = ?",
            (*campos.values(), solicitud_id),
        )
        conn.commit()
        updated = conn.execute("SELECT * FROM solicitudes WHERE id = ?", (solicitud_id,)).fetchone()
        assert updated is not None
        return _solicitud_completa(conn, updated, sesion_id)


def agregar_entrega(sesion_id: int, solicitud_id: int, data: EntregaParcialCreate) -> Solicitud:
    with _conectar() as conn:
        row = conn.execute("SELECT * FROM solicitudes WHERE id = ?", (solicitud_id,)).fetchone()
        if not row:
            raise LookupError("Solicitud no encontrada.")
        if row["cerrado"]:
            raise ValueError("La solicitud está cerrada.")

        entregas = _entregas_por_solicitud(conn, solicitud_id)
        total_actual = sum(e.cantidad for e in entregas) + data.cantidad
        if total_actual > row["cantidad_items"]:
            raise ValueError(
                f"La suma de entregas ({total_actual}) supera la cantidad de ítems ({row['cantidad_items']})."
            )

        ahora = _ahora_iso()
        conn.execute(
            """
            INSERT INTO entregas_parciales (solicitud_id, fecha, cantidad, observacion, creado_en)
            VALUES (?, ?, ?, ?, ?)
            """,
            (solicitud_id, data.fecha, data.cantidad, data.observacion, ahora),
        )

        entregas_nuevas = _entregas_por_solicitud(conn, solicitud_id)
        nuevo_estado = _calcular_estado_entrega(row["cantidad_items"], entregas_nuevas)
        conn.execute(
            """
            UPDATE solicitudes SET estado_entrega = ?, actualizado_en = ? WHERE id = ?
            """,
            (nuevo_estado.value, ahora, solicitud_id),
        )
        _vincular_solicitud_sesion(conn, sesion_id, solicitud_id)
        conn.commit()
        updated = conn.execute("SELECT * FROM solicitudes WHERE id = ?", (solicitud_id,)).fetchone()
        assert updated is not None
        return _solicitud_completa(conn, updated, sesion_id)


def agregar_actualizacion_solicitud(
    sesion_id: int, solicitud_id: int, data: ActualizacionCreate
) -> Actualizacion:
    with _conectar() as conn:
        if not conn.execute("SELECT 1 FROM sesiones WHERE id = ?", (sesion_id,)).fetchone():
            raise LookupError("Sesión no encontrada.")
        if not conn.execute("SELECT 1 FROM solicitudes WHERE id = ?", (solicitud_id,)).fetchone():
            raise LookupError("Solicitud no encontrada.")

        ahora = _ahora_iso()
        cur = conn.execute(
            """
            INSERT INTO actualizaciones (sesion_id, solicitud_id, texto, autor, creado_en)
            VALUES (?, ?, ?, ?, ?)
            """,
            (sesion_id, solicitud_id, data.texto, data.autor, ahora),
        )
        conn.execute(
            "UPDATE sesiones SET actualizado_en = ? WHERE id = ?",
            (ahora, sesion_id),
        )
        conn.execute(
            "UPDATE solicitudes SET actualizado_en = ? WHERE id = ?",
            (ahora, solicitud_id),
        )
        _vincular_solicitud_sesion(conn, sesion_id, solicitud_id)
        conn.commit()
        act_id = cur.lastrowid
        row = conn.execute("SELECT * FROM actualizaciones WHERE id = ?", (act_id,)).fetchone()
        assert row is not None
        return Actualizacion(
            id=row["id"],
            sesion_id=row["sesion_id"],
            solicitud_id=row["solicitud_id"],
            texto=row["texto"],
            autor=row["autor"],
            creado_en=row["creado_en"],
        )


def crear_tema(sesion_id: int, data: TemaCreate) -> Tema:
    with _conectar() as conn:
        ses = conn.execute("SELECT * FROM sesiones WHERE id = ?", (sesion_id,)).fetchone()
        if not ses:
            raise LookupError("Sesión no encontrada.")
        if ses["estado"] != EstadoSesion.ABIERTA.value:
            raise ValueError("La sesión no está abierta.")

        ahora = _ahora_iso()
        cur = conn.execute(
            """
            INSERT INTO temas (sesion_origen_id, titulo, descripcion, resuelto, creado_en, actualizado_en)
            VALUES (?, ?, ?, 0, ?, ?)
            """,
            (sesion_id, data.titulo, data.descripcion, ahora, ahora),
        )
        tema_id = cur.lastrowid
        assert tema_id is not None
        _vincular_tema_sesion(conn, sesion_id, tema_id)
        conn.commit()
        row = conn.execute("SELECT * FROM temas WHERE id = ?", (tema_id,)).fetchone()
        assert row is not None
        return Tema(
            id=row["id"],
            sesion_origen_id=row["sesion_origen_id"],
            titulo=row["titulo"],
            descripcion=row["descripcion"],
            resuelto=bool(row["resuelto"]),
            creado_en=row["creado_en"],
            actualizado_en=row["actualizado_en"],
        )


def actualizar_tema(tema_id: int, data: TemaUpdate) -> Tema:
    with _conectar() as conn:
        row = conn.execute("SELECT * FROM temas WHERE id = ?", (tema_id,)).fetchone()
        if not row:
            raise LookupError("Tema no encontrado.")

        campos: dict[str, Any] = {}
        if data.titulo is not None:
            campos["titulo"] = data.titulo
        if data.descripcion is not None:
            campos["descripcion"] = data.descripcion
        if data.resuelto is not None:
            campos["resuelto"] = 1 if data.resuelto else 0

        if not campos:
            return Tema(
                id=row["id"],
                sesion_origen_id=row["sesion_origen_id"],
                titulo=row["titulo"],
                descripcion=row["descripcion"],
                resuelto=bool(row["resuelto"]),
                creado_en=row["creado_en"],
                actualizado_en=row["actualizado_en"],
            )

        campos["actualizado_en"] = _ahora_iso()
        sets = ", ".join(f"{k} = ?" for k in campos)
        conn.execute(f"UPDATE temas SET {sets} WHERE id = ?", (*campos.values(), tema_id))
        conn.commit()
        updated = conn.execute("SELECT * FROM temas WHERE id = ?", (tema_id,)).fetchone()
        assert updated is not None
        return Tema(
            id=updated["id"],
            sesion_origen_id=updated["sesion_origen_id"],
            titulo=updated["titulo"],
            descripcion=updated["descripcion"],
            resuelto=bool(updated["resuelto"]),
            creado_en=updated["creado_en"],
            actualizado_en=updated["actualizado_en"],
        )


def marcar_sesion_enviada(sesion_id: int) -> SesionResumen:
    with _conectar() as conn:
        row = conn.execute("SELECT * FROM sesiones WHERE id = ?", (sesion_id,)).fetchone()
        if not row:
            raise LookupError("Sesión no encontrada.")
        ahora = _ahora_iso()
        conn.execute(
            """
            UPDATE sesiones
            SET estado = ?, email_enviado_en = ?, actualizado_en = ?
            WHERE id = ?
            """,
            (EstadoSesion.ENVIADA.value, ahora, ahora, sesion_id),
        )
        conn.commit()
        updated = conn.execute("SELECT * FROM sesiones WHERE id = ?", (sesion_id,)).fetchone()
        assert updated is not None
        return _row_sesion(updated)


def datos_para_email(sesion_id: int) -> SesionDetalle:
    detalle = obtener_sesion_detalle(sesion_id)
    if not detalle:
        raise LookupError("Sesión no encontrada.")
    return detalle
