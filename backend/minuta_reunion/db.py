# -*- coding: utf-8 -*-
"""Persistencia SQLite + export JSON por sector para minutas de reunión."""

from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_SHARE_DATA_DIR = Path(
    r"G:\Unidades compartidas\Mantenimiento\MANTENIMIENTO  OZLA 2024-2025\17. Pañol\pañol v5.0\minuta_data"
)


def _default_data_dir() -> Path:
    """Prefer the shared source of truth when available; fall back locally."""
    return DEFAULT_SHARE_DATA_DIR if DEFAULT_SHARE_DATA_DIR.exists() else BASE_DIR / "data"


DATA_DIR = Path(os.environ.get("MINUTA_DATA_DIR", _default_data_dir()))
DB_PATH = Path(os.environ.get("MINUTA_DB_PATH", DATA_DIR / "minutas.db"))
SECTORES_DIR = DATA_DIR / "sectores"

SECTORES = [
    "MANTENIMIENTO",
    "PROYECTOS",
    "EDILICIO",
    "AUTOELEVADORES",
    "PRODUCCION",
    "PAÑOL",
]

IMPORTANCIAS = ("critico", "urgente", "normal")
ESTADOS = ("sin_oc", "en_proceso", "parcial", "completado")
IMPORTANCIA_DEFAULT = "normal"
ESTADO_DEFAULT = "en_proceso"

TIPOS_REUNION = ("semanal", "diaria", "ocasion")
VISIBILIDADES = ("individual", "compartida")
TIPO_DEFAULT = "semanal"
VISIBILIDAD_DEFAULT = "individual"


def _norm_tipo(val: Any) -> str:
    s = str(val or "").strip().lower()
    return s if s in TIPOS_REUNION else TIPO_DEFAULT


def _norm_visibilidad(val: Any) -> str:
    s = str(val or "").strip().lower()
    return s if s in VISIBILIDADES else VISIBILIDAD_DEFAULT


def _norm_importancia(val: Any, actual: str = IMPORTANCIA_DEFAULT) -> str:
    s = str(val or "").strip().lower().replace(" ", "_")
    return s if s in IMPORTANCIAS else (actual if actual in IMPORTANCIAS else IMPORTANCIA_DEFAULT)


def _norm_estado(val: Any, actual: str = ESTADO_DEFAULT) -> str:
    s = str(val or "").strip().lower().replace(" ", "_")
    return s if s in ESTADOS else (actual if actual in ESTADOS else ESTADO_DEFAULT)


def _ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug_sector(sector: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", sector.strip().upper()).strip("_")
    return s or "SIN_SECTOR"


def _conectar() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SECTORES_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def init_db() -> None:
    with _conectar() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS pedidos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pedido TEXT NOT NULL DEFAULT '',
                n_pedido TEXT NOT NULL DEFAULT '',
                fecha TEXT NOT NULL DEFAULT '',
                oc TEXT NOT NULL DEFAULT '',
                sector TEXT NOT NULL,
                reunion_id INTEGER NOT NULL DEFAULT 0,
                activo INTEGER NOT NULL DEFAULT 1,
                consultas TEXT NOT NULL DEFAULT '',
                importancia TEXT NOT NULL DEFAULT 'normal',
                estado TEXT NOT NULL DEFAULT 'en_proceso',
                orden INTEGER NOT NULL DEFAULT 0,
                creado_en TEXT NOT NULL,
                actualizado_en TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_pedidos_sector_activo
                ON pedidos(sector, activo);

            CREATE TABLE IF NOT EXISTS novedades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pedido_id INTEGER NOT NULL,
                fecha_reunion TEXT NOT NULL,
                texto TEXT NOT NULL DEFAULT '',
                sector TEXT NOT NULL,
                creado_en TEXT NOT NULL,
                FOREIGN KEY (pedido_id) REFERENCES pedidos(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_novedades_pedido
                ON novedades(pedido_id, fecha_reunion);

            CREATE TABLE IF NOT EXISTS reuniones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sector TEXT NOT NULL,
                fecha TEXT NOT NULL,
                notas_generales TEXT NOT NULL DEFAULT '',
                email_enviado_en TEXT,
                titulo TEXT NOT NULL DEFAULT '',
                tipo TEXT NOT NULL DEFAULT 'semanal',
                visibilidad TEXT NOT NULL DEFAULT 'individual',
                owner_email TEXT NOT NULL DEFAULT '',
                sectores_comprometidos TEXT NOT NULL DEFAULT '',
                archivada INTEGER NOT NULL DEFAULT 0,
                creado_en TEXT NOT NULL,
                actualizado_en TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_reuniones_sector_fecha
                ON reuniones(sector, fecha);

            CREATE TABLE IF NOT EXISTS pedido_movimientos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pedido_id INTEGER NOT NULL,
                sector_origen TEXT NOT NULL,
                sector_destino TEXT NOT NULL,
                fecha TEXT NOT NULL,
                notas TEXT NOT NULL DEFAULT '',
                creado_en TEXT NOT NULL,
                FOREIGN KEY (pedido_id) REFERENCES pedidos(id) ON DELETE CASCADE
            );
            """
        )
        _migrar(conn)


def _migrar(conn: sqlite3.Connection) -> None:
    """Agrega columnas nuevas a pedidos/reuniones en bases ya existentes."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(pedidos)").fetchall()}
    nuevas = {
        "consultas": "TEXT NOT NULL DEFAULT ''",
        "importancia": "TEXT NOT NULL DEFAULT 'normal'",
        "estado": "TEXT NOT NULL DEFAULT 'en_proceso'",
        "orden": "INTEGER NOT NULL DEFAULT 0",
        "reunion_id": "INTEGER NOT NULL DEFAULT 0",
    }
    agregadas: list[str] = []
    for col, ddl in nuevas.items():
        if col not in cols:
            conn.execute(f"ALTER TABLE pedidos ADD COLUMN {col} {ddl}")
            agregadas.append(col)
    if "orden" in agregadas:
        sectores = [
            r["sector"]
            for r in conn.execute("SELECT DISTINCT sector FROM pedidos").fetchall()
        ]
        for sector in sectores:
            filas = conn.execute(
                "SELECT id FROM pedidos WHERE sector = ? ORDER BY actualizado_en DESC, id DESC",
                (sector,),
            ).fetchall()
            for idx, fila in enumerate(filas):
                conn.execute(
                    "UPDATE pedidos SET orden = ? WHERE id = ?", (idx, int(fila["id"]))
                )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_pedidos_sector_orden ON pedidos(sector, orden)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_pedidos_reunion ON pedidos(reunion_id, activo)"
    )

    rcols = {r["name"] for r in conn.execute("PRAGMA table_info(reuniones)").fetchall()}
    r_nuevas = {
        "titulo": "TEXT NOT NULL DEFAULT ''",
        "tipo": "TEXT NOT NULL DEFAULT 'semanal'",
        "visibilidad": "TEXT NOT NULL DEFAULT 'individual'",
        "owner_email": "TEXT NOT NULL DEFAULT ''",
        "sectores_comprometidos": "TEXT NOT NULL DEFAULT ''",
        "archivada": "INTEGER NOT NULL DEFAULT 0",
    }
    for col, ddl in r_nuevas.items():
        if col not in rcols:
            conn.execute(f"ALTER TABLE reuniones ADD COLUMN {col} {ddl}")

    # Pedidos legacy (reunion_id=0): asignar a una reunión "Histórico" por sector.
    _asignar_pedidos_legacy(conn)
    # Promover reuniones que quedaron con título vacío pero tienen pedidos.
    _promover_historicos(conn)

    conn.commit()


def _asignar_pedidos_legacy(conn: sqlite3.Connection) -> None:
    ahora = _ahora_iso()
    huérfanos = conn.execute(
        "SELECT DISTINCT sector FROM pedidos WHERE COALESCE(reunion_id, 0) = 0"
    ).fetchall()
    for row in huérfanos:
        sector = str(row["sector"])
        reun = conn.execute(
            """
            SELECT id FROM reuniones
            WHERE sector = ? AND (titulo LIKE 'Histórico%' OR titulo = '' OR titulo IS NULL)
            ORDER BY id ASC LIMIT 1
            """,
            (sector,),
        ).fetchone()
        if reun:
            rid = int(reun["id"])
            conn.execute(
                """
                UPDATE reuniones
                SET titulo = ?, visibilidad = 'compartida', tipo = 'ocasion',
                    sectores_comprometidos = COALESCE(NULLIF(sectores_comprometidos,''), ?)
                WHERE id = ?
                """,
                (f"Histórico — {sector}", sector, rid),
            )
        else:
            cur = conn.execute(
                """
                INSERT INTO reuniones
                    (sector, fecha, notas_generales, titulo, tipo, visibilidad,
                     owner_email, sectores_comprometidos, creado_en, actualizado_en)
                VALUES (?, ?, '', ?, 'ocasion', 'compartida', '', ?, ?, ?)
                """,
                (
                    sector,
                    date.today().isoformat(),
                    f"Histórico — {sector}",
                    sector,
                    ahora,
                    ahora,
                ),
            )
            rid = int(cur.lastrowid)
        conn.execute(
            "UPDATE pedidos SET reunion_id = ? WHERE sector = ? AND COALESCE(reunion_id, 0) = 0",
            (rid, sector),
        )

    # Reuniones legacy sin dueño, sin pedidos y sin título: etiquetar para no confundir.
    conn.execute(
        """
        UPDATE reuniones
        SET titulo = 'Legacy ' || fecha
        WHERE COALESCE(owner_email, '') = ''
          AND COALESCE(titulo, '') = ''
          AND titulo NOT LIKE 'Histórico%'
          AND NOT EXISTS (SELECT 1 FROM pedidos p WHERE p.reunion_id = reuniones.id)
        """
    )


def _promover_historicos(conn: sqlite3.Connection) -> None:
    """Si una reunión sin título (o Legacy) tiene pedidos, marcarla como Histórico compartido."""
    rows = conn.execute(
        """
        SELECT r.id, r.sector
        FROM reuniones r
        WHERE (
            r.titulo IS NULL OR r.titulo = '' OR r.titulo LIKE 'Legacy %'
          )
          AND EXISTS (SELECT 1 FROM pedidos p WHERE p.reunion_id = r.id)
        """
    ).fetchall()
    for row in rows:
        sector = str(row["sector"])
        conn.execute(
            """
            UPDATE reuniones
            SET titulo = ?, visibilidad = 'compartida', tipo = 'ocasion',
                sectores_comprometidos = COALESCE(NULLIF(sectores_comprometidos,''), ?)
            WHERE id = ?
            """,
            (f"Histórico — {sector}", sector, int(row["id"])),
        )


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def listar_sectores() -> list[str]:
    return list(SECTORES)


def _exportar_sector(conn: sqlite3.Connection, sector: str) -> None:
    sector = sector.strip().upper()
    pedidos = conn.execute(
        """
        SELECT p.*,
               (
                 SELECT COUNT(*) FROM novedades n WHERE n.pedido_id = p.id
               ) AS total_novedades
        FROM pedidos p
        WHERE p.sector = ?
        ORDER BY p.actualizado_en DESC
        """,
        (sector,),
    ).fetchall()

    pedido_ids = [int(r["id"]) for r in pedidos]
    novedades: list[sqlite3.Row] = []
    movimientos: list[sqlite3.Row] = []
    if pedido_ids:
        placeholders = ",".join("?" * len(pedido_ids))
        novedades = conn.execute(
            f"""
            SELECT * FROM novedades
            WHERE pedido_id IN ({placeholders})
            ORDER BY fecha_reunion DESC, id DESC
            """,
            pedido_ids,
        ).fetchall()
        movimientos = conn.execute(
            f"""
            SELECT * FROM pedido_movimientos
            WHERE pedido_id IN ({placeholders})
            ORDER BY creado_en DESC
            """,
            pedido_ids,
        ).fetchall()

    reuniones = conn.execute(
        """
        SELECT * FROM reuniones
        WHERE sector = ?
        ORDER BY fecha DESC, id DESC
        """,
        (sector,),
    ).fetchall()

    payload = {
        "sector": sector,
        "exportado_en": _ahora_iso(),
        "pedidos": [dict(r) for r in pedidos],
        "novedades": [dict(r) for r in novedades],
        "movimientos": [dict(r) for r in movimientos],
        "reuniones": [dict(r) for r in reuniones],
    }
    path = SECTORES_DIR / f"{_slug_sector(sector)}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def listar_pedidos_reunion(
    reunion_id: int, solo_activos: bool = True
) -> list[dict[str, Any]]:
    sql = """
        SELECT p.*,
               (
                 SELECT n.texto FROM novedades n
                 WHERE n.pedido_id = p.id
                 ORDER BY n.fecha_reunion DESC, n.id DESC
                 LIMIT 1
               ) AS ultima_novedad,
               (
                 SELECT n.fecha_reunion FROM novedades n
                 WHERE n.pedido_id = p.id
                 ORDER BY n.fecha_reunion DESC, n.id DESC
                 LIMIT 1
               ) AS ultima_novedad_fecha,
               (
                 SELECT COUNT(*) FROM novedades n WHERE n.pedido_id = p.id
               ) AS total_novedades
        FROM pedidos p
        WHERE p.reunion_id = ?
    """
    params: list[Any] = [int(reunion_id)]
    if solo_activos:
        sql += " AND p.activo = 1"
    sql += " ORDER BY p.orden ASC, p.id DESC"

    with _conectar() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def listar_pedidos_sector(sector: str, solo_activos: bool = True) -> list[dict[str, Any]]:
    """Legacy: pedidos del sector (todas las reuniones). Preferir listar_pedidos_reunion."""
    sector = sector.strip().upper()
    sql = """
        SELECT p.*,
               (
                 SELECT n.texto FROM novedades n
                 WHERE n.pedido_id = p.id
                 ORDER BY n.fecha_reunion DESC, n.id DESC
                 LIMIT 1
               ) AS ultima_novedad,
               (
                 SELECT n.fecha_reunion FROM novedades n
                 WHERE n.pedido_id = p.id
                 ORDER BY n.fecha_reunion DESC, n.id DESC
                 LIMIT 1
               ) AS ultima_novedad_fecha,
               (
                 SELECT COUNT(*) FROM novedades n WHERE n.pedido_id = p.id
               ) AS total_novedades
        FROM pedidos p
        WHERE p.sector = ?
    """
    params: list[Any] = [sector]
    if solo_activos:
        sql += " AND p.activo = 1"
    sql += " ORDER BY p.orden ASC, p.id DESC"

    with _conectar() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def obtener_pedido(pedido_id: int) -> dict[str, Any] | None:
    with _conectar() as conn:
        row = conn.execute("SELECT * FROM pedidos WHERE id = ?", (pedido_id,)).fetchone()
        if not row:
            return None
        pedido = dict(row)
        novedades = conn.execute(
            """
            SELECT * FROM novedades
            WHERE pedido_id = ?
            ORDER BY fecha_reunion DESC, id DESC
            """,
            (pedido_id,),
        ).fetchall()
        movimientos = conn.execute(
            """
            SELECT * FROM pedido_movimientos
            WHERE pedido_id = ?
            ORDER BY creado_en DESC
            """,
            (pedido_id,),
        ).fetchall()
        pedido["novedades"] = [dict(n) for n in novedades]
        pedido["movimientos"] = [dict(m) for m in movimientos]
        return pedido


def crear_pedido(data: dict[str, Any]) -> dict[str, Any]:
    sector = str(data.get("sector", "")).strip().upper()
    if sector not in SECTORES:
        raise ValueError(f"Sector inválido: {sector}")
    reunion_id = int(data.get("reunion_id") or 0)
    if reunion_id <= 0:
        raise ValueError("reunion_id requerido.")
    ahora = _ahora_iso()
    fecha = str(data.get("fecha") or date.today().isoformat()).strip()
    with _conectar() as conn:
        reun = conn.execute(
            "SELECT id, sector FROM reuniones WHERE id = ?", (reunion_id,)
        ).fetchone()
        if not reun:
            raise ValueError("Reunión no encontrada.")
        sector = str(reun["sector"])
        orden_top = int(
            conn.execute(
                "SELECT COALESCE(MIN(orden), 0) - 1 FROM pedidos WHERE reunion_id = ?",
                (reunion_id,),
            ).fetchone()[0]
        )
        cur = conn.execute(
            """
            INSERT INTO pedidos
                (pedido, n_pedido, fecha, oc, sector, reunion_id, activo,
                 consultas, importancia, estado, orden, creado_en, actualizado_en)
            VALUES (?, ?, ?, ?, ?, ?, 1, '', ?, ?, ?, ?, ?)
            """,
            (
                str(data.get("pedido") or "").strip(),
                str(data.get("n_pedido") or "").strip(),
                fecha,
                str(data.get("oc") or "").strip(),
                sector,
                reunion_id,
                _norm_importancia(data.get("importancia")),
                _norm_estado(data.get("estado")),
                orden_top,
                ahora,
                ahora,
            ),
        )
        pid = int(cur.lastrowid)
        conn.commit()
        _exportar_sector(conn, sector)
        return obtener_pedido(pid) or {}


def actualizar_pedido(pedido_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
    with _conectar() as conn:
        row = conn.execute("SELECT * FROM pedidos WHERE id = ?", (pedido_id,)).fetchone()
        if not row:
            return None
        sector_anterior = str(row["sector"])
        campos = []
        valores: list[Any] = []
        for key, col in [
            ("pedido", "pedido"),
            ("n_pedido", "n_pedido"),
            ("fecha", "fecha"),
            ("oc", "oc"),
            ("consultas", "consultas"),
        ]:
            if key in data:
                campos.append(f"{col} = ?")
                valores.append(str(data[key] or "").strip())
        if "importancia" in data:
            campos.append("importancia = ?")
            valores.append(_norm_importancia(data["importancia"], str(row["importancia"])))
        if "estado" in data:
            campos.append("estado = ?")
            valores.append(_norm_estado(data["estado"], str(row["estado"])))
        if "orden" in data:
            campos.append("orden = ?")
            valores.append(int(data["orden"]))
        if not campos:
            return obtener_pedido(pedido_id)
        campos.append("actualizado_en = ?")
        valores.append(_ahora_iso())
        valores.append(pedido_id)
        conn.execute(
            f"UPDATE pedidos SET {', '.join(campos)} WHERE id = ?",
            valores,
        )
        conn.commit()
        sector_nuevo = str(
            conn.execute("SELECT sector FROM pedidos WHERE id = ?", (pedido_id,)).fetchone()["sector"]
        )
        _exportar_sector(conn, sector_anterior)
        if sector_nuevo != sector_anterior:
            _exportar_sector(conn, sector_nuevo)
        return obtener_pedido(pedido_id)


def agregar_novedad(pedido_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
    fecha_reunion = str(data.get("fecha_reunion") or date.today().isoformat()).strip()
    texto = str(data.get("texto") or "").strip()
    if not texto:
        raise ValueError("El texto de novedades es requerido.")
    with _conectar() as conn:
        row = conn.execute("SELECT sector FROM pedidos WHERE id = ?", (pedido_id,)).fetchone()
        if not row:
            return None
        sector = str(row["sector"])
        ahora = _ahora_iso()
        conn.execute(
            """
            INSERT INTO novedades (pedido_id, fecha_reunion, texto, sector, creado_en)
            VALUES (?, ?, ?, ?, ?)
            """,
            (pedido_id, fecha_reunion, texto, sector, ahora),
        )
        conn.execute(
            "UPDATE pedidos SET actualizado_en = ? WHERE id = ?",
            (ahora, pedido_id),
        )
        conn.commit()
        _exportar_sector(conn, sector)
        return obtener_pedido(pedido_id)


def finalizar_pedido(pedido_id: int, data: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Marca el pedido como finalizado (activo=0) sin cambiar de sector."""
    data = data or {}
    notas = str(data.get("notas") or "").strip()
    with _conectar() as conn:
        row = conn.execute("SELECT * FROM pedidos WHERE id = ?", (pedido_id,)).fetchone()
        if not row:
            return None
        sector = str(row["sector"])
        ahora = _ahora_iso()
        conn.execute(
            """
            UPDATE pedidos
            SET activo = 0, estado = 'completado', actualizado_en = ?
            WHERE id = ?
            """,
            (ahora, pedido_id),
        )
        if notas:
            conn.execute(
                """
                INSERT INTO novedades (pedido_id, fecha_reunion, texto, sector, creado_en)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    pedido_id,
                    str(data.get("fecha") or date.today().isoformat()).strip(),
                    f"[Finalizado] {notas}",
                    sector,
                    ahora,
                ),
            )
        conn.commit()
        _exportar_sector(conn, sector)
        return obtener_pedido(pedido_id)


def reactivar_pedido(pedido_id: int) -> dict[str, Any] | None:
    with _conectar() as conn:
        row = conn.execute("SELECT * FROM pedidos WHERE id = ?", (pedido_id,)).fetchone()
        if not row:
            return None
        sector = str(row["sector"])
        ahora = _ahora_iso()
        conn.execute(
            """
            UPDATE pedidos
            SET activo = 1, estado = 'en_proceso', actualizado_en = ?
            WHERE id = ?
            """,
            (ahora, pedido_id),
        )
        conn.commit()
        _exportar_sector(conn, sector)
        return obtener_pedido(pedido_id)


def eliminar_pedido(pedido_id: int) -> bool:
    with _conectar() as conn:
        row = conn.execute("SELECT sector FROM pedidos WHERE id = ?", (pedido_id,)).fetchone()
        if not row:
            return False
        sector = str(row["sector"])
        conn.execute("DELETE FROM pedidos WHERE id = ?", (pedido_id,))
        conn.commit()
        _exportar_sector(conn, sector)
        return True


def reordenar_pedidos(reunion_id: int, ids: list[int]) -> list[dict[str, Any]]:
    """Asigna orden 0..n a los pedidos de la reunión según la lista de ids."""
    reunion_id = int(reunion_id)
    with _conectar() as conn:
        reun = conn.execute(
            "SELECT sector FROM reuniones WHERE id = ?", (reunion_id,)
        ).fetchone()
        if not reun:
            return []
        sector = str(reun["sector"])
        actuales = [
            int(r["id"])
            for r in conn.execute(
                "SELECT id FROM pedidos WHERE reunion_id = ? ORDER BY orden ASC, id DESC",
                (reunion_id,),
            ).fetchall()
        ]
        validos = set(actuales)
        pedido_ids = [int(i) for i in ids if int(i) in validos]
        vistos = set(pedido_ids)
        final = pedido_ids + [i for i in actuales if i not in vistos]
        for idx, pid in enumerate(final):
            conn.execute("UPDATE pedidos SET orden = ? WHERE id = ?", (idx, pid))
        conn.commit()
        _exportar_sector(conn, sector)
    return listar_pedidos_reunion(reunion_id, solo_activos=False)


def limpiar_consultas_reunion(reunion_id: int) -> int:
    reunion_id = int(reunion_id)
    with _conectar() as conn:
        reun = conn.execute(
            "SELECT sector FROM reuniones WHERE id = ?", (reunion_id,)
        ).fetchone()
        if not reun:
            return 0
        sector = str(reun["sector"])
        cur = conn.execute(
            "UPDATE pedidos SET consultas = '' WHERE reunion_id = ? AND consultas <> ''",
            (reunion_id,),
        )
        conn.commit()
        _exportar_sector(conn, sector)
        return cur.rowcount


def limpiar_consultas_sector(sector: str) -> int:
    """Legacy: limpia consultas de todo el sector."""
    sector = sector.strip().upper()
    with _conectar() as conn:
        cur = conn.execute(
            "UPDATE pedidos SET consultas = '' WHERE sector = ? AND consultas <> ''",
            (sector,),
        )
        conn.commit()
        _exportar_sector(conn, sector)
        return cur.rowcount


def obtener_reunion(reunion_id: int) -> dict[str, Any] | None:
    with _conectar() as conn:
        row = conn.execute("SELECT * FROM reuniones WHERE id = ?", (reunion_id,)).fetchone()
        return dict(row) if row else None


def crear_reunion(data: dict[str, Any]) -> dict[str, Any]:
    sector = str(data.get("sector") or "MANTENIMIENTO").strip().upper()
    if sector not in SECTORES:
        raise ValueError(f"Sector inválido: {sector}")
    fecha = str(data.get("fecha") or date.today().isoformat()).strip()
    titulo = str(data.get("titulo") or "").strip() or f"Reunión {fecha}"
    tipo = _norm_tipo(data.get("tipo"))
    visibilidad = _norm_visibilidad(data.get("visibilidad"))
    owner_email = str(data.get("owner_email") or "").strip().lower()
    sectores_comprometidos = str(data.get("sectores_comprometidos") or sector).strip()
    ahora = _ahora_iso()
    with _conectar() as conn:
        cur = conn.execute(
            """
            INSERT INTO reuniones
                (sector, fecha, notas_generales, titulo, tipo, visibilidad,
                 owner_email, sectores_comprometidos, creado_en, actualizado_en)
            VALUES (?, ?, '', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sector,
                fecha,
                titulo,
                tipo,
                visibilidad,
                owner_email,
                sectores_comprometidos,
                ahora,
                ahora,
            ),
        )
        conn.commit()
        rid = int(cur.lastrowid)
        _exportar_sector(conn, sector)
        row = conn.execute("SELECT * FROM reuniones WHERE id = ?", (rid,)).fetchone()
        return dict(row)


def obtener_o_crear_reunion(sector: str, fecha: str) -> dict[str, Any]:
    """Compatibilidad: obtiene o crea reunión básica por sector+fecha."""
    sector = sector.strip().upper()
    fecha = fecha.strip()
    with _conectar() as conn:
        row = conn.execute(
            """
            SELECT * FROM reuniones
            WHERE sector = ? AND fecha = ?
            ORDER BY id DESC LIMIT 1
            """,
            (sector, fecha),
        ).fetchone()
        if row:
            return dict(row)
    return crear_reunion({"sector": sector, "fecha": fecha, "titulo": f"Reunión {fecha}"})


def actualizar_reunion(reunion_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
    with _conectar() as conn:
        row = conn.execute("SELECT * FROM reuniones WHERE id = ?", (reunion_id,)).fetchone()
        if not row:
            return None
        sector = str(row["sector"])
        campos: list[str] = []
        valores: list[Any] = []
        if "notas_generales" in data:
            campos.append("notas_generales = ?")
            valores.append(str(data.get("notas_generales") or "").strip())
        if "email_enviado_en" in data and data["email_enviado_en"]:
            campos.append("email_enviado_en = ?")
            valores.append(str(data["email_enviado_en"]))
        if "titulo" in data:
            campos.append("titulo = ?")
            valores.append(str(data.get("titulo") or "").strip())
        if "tipo" in data:
            campos.append("tipo = ?")
            valores.append(_norm_tipo(data["tipo"]))
        if "visibilidad" in data:
            campos.append("visibilidad = ?")
            valores.append(_norm_visibilidad(data["visibilidad"]))
        if "sectores_comprometidos" in data:
            campos.append("sectores_comprometidos = ?")
            valores.append(str(data.get("sectores_comprometidos") or "").strip())
        if "fecha" in data:
            campos.append("fecha = ?")
            valores.append(str(data.get("fecha") or "").strip())
        if "archivada" in data:
            campos.append("archivada = ?")
            valores.append(1 if data.get("archivada") in (True, 1, "1", "true") else 0)
        if "sector" in data:
            nuevo_sector = str(data.get("sector") or "").strip().upper()
            if nuevo_sector not in SECTORES:
                raise ValueError(f"Sector inválido: {nuevo_sector}")
            if nuevo_sector != sector:
                campos.append("sector = ?")
                valores.append(nuevo_sector)
        if not campos:
            return dict(row)
        campos.append("actualizado_en = ?")
        valores.append(_ahora_iso())
        valores.append(reunion_id)
        conn.execute(
            f"UPDATE reuniones SET {', '.join(campos)} WHERE id = ?",
            valores,
        )
        sector_nuevo = str(
            conn.execute("SELECT sector FROM reuniones WHERE id = ?", (reunion_id,)).fetchone()[
                "sector"
            ]
        )
        if sector_nuevo != sector:
            conn.execute(
                "UPDATE pedidos SET sector = ? WHERE reunion_id = ?",
                (sector_nuevo, reunion_id),
            )
        conn.commit()
        _exportar_sector(conn, sector)
        if sector_nuevo != sector:
            _exportar_sector(conn, sector_nuevo)
        row = conn.execute("SELECT * FROM reuniones WHERE id = ?", (reunion_id,)).fetchone()
        return dict(row)


def listar_reuniones(
    *,
    sector: str | None = None,
    owner_email: str | None = None,
    solo_enviadas: bool = False,
    archivadas: bool | None = False,
    limite: int = 50,
) -> list[dict[str, Any]]:
    """Lista reuniones visibles para el usuario demo (propias + compartidas del sector).

    archivadas:
      False → solo activas (default)
      True → solo archivadas
      None → todas
    """
    sql = "SELECT * FROM reuniones WHERE 1=1"
    params: list[Any] = []
    if sector:
        sql += " AND sector = ?"
        params.append(sector.strip().upper())
    if owner_email:
        email = owner_email.strip().lower()
        # Solo propias o compartidas — no incluir legacy con owner vacío.
        sql += " AND (visibilidad = 'compartida' OR lower(owner_email) = ?)"
        params.append(email)
    if solo_enviadas:
        sql += " AND email_enviado_en IS NOT NULL AND email_enviado_en <> ''"
    if archivadas is True:
        sql += " AND COALESCE(archivada, 0) = 1"
    elif archivadas is False:
        sql += " AND COALESCE(archivada, 0) = 0"
    sql += " ORDER BY fecha DESC, id DESC LIMIT ?"
    params.append(limite)
    with _conectar() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def eliminar_reunion(reunion_id: int) -> bool:
    """Borra la reunión. Los pedidos pasan al Histórico del sector (no se pierden)."""
    with _conectar() as conn:
        row = conn.execute("SELECT * FROM reuniones WHERE id = ?", (reunion_id,)).fetchone()
        if not row:
            return False
        sector = str(row["sector"])
        # Reutilizar / crear histórico del sector
        hist = conn.execute(
            """
            SELECT id FROM reuniones
            WHERE sector = ? AND titulo LIKE 'Histórico%' AND id <> ?
            ORDER BY id ASC LIMIT 1
            """,
            (sector, reunion_id),
        ).fetchone()
        if hist:
            hist_id = int(hist["id"])
        else:
            ahora = _ahora_iso()
            cur = conn.execute(
                """
                INSERT INTO reuniones
                    (sector, fecha, notas_generales, titulo, tipo, visibilidad,
                     owner_email, sectores_comprometidos, archivada,
                     creado_en, actualizado_en)
                VALUES (?, ?, '', ?, 'ocasion', 'compartida', '', ?, 1, ?, ?)
                """,
                (
                    sector,
                    date.today().isoformat(),
                    f"Histórico — {sector}",
                    sector,
                    ahora,
                    ahora,
                ),
            )
            hist_id = int(cur.lastrowid)
        conn.execute(
            "UPDATE pedidos SET reunion_id = ? WHERE reunion_id = ?",
            (hist_id, reunion_id),
        )
        conn.execute("DELETE FROM reuniones WHERE id = ?", (reunion_id,))
        conn.commit()
        _exportar_sector(conn, sector)
        return True


def listar_reuniones_sector(sector: str, limite: int = 20) -> list[dict[str, Any]]:
    return listar_reuniones(sector=sector, limite=limite)


def mover_pedidos_reunion(origen_id: int, destino_id: int) -> int:
    """Mueve todos los pedidos de una reunión a otra (misma operación, recuperación)."""
    origen_id = int(origen_id)
    destino_id = int(destino_id)
    if origen_id == destino_id:
        return 0
    with _conectar() as conn:
        dest = conn.execute(
            "SELECT id, sector FROM reuniones WHERE id = ?", (destino_id,)
        ).fetchone()
        orig = conn.execute(
            "SELECT id, sector FROM reuniones WHERE id = ?", (origen_id,)
        ).fetchone()
        if not dest or not orig:
            raise ValueError("Reunión origen o destino no encontrada.")
        sector_dest = str(dest["sector"])
        sector_orig = str(orig["sector"])
        cur = conn.execute(
            """
            UPDATE pedidos
            SET reunion_id = ?, sector = ?, actualizado_en = ?
            WHERE reunion_id = ?
            """,
            (destino_id, sector_dest, _ahora_iso(), origen_id),
        )
        conn.commit()
        _exportar_sector(conn, sector_orig)
        if sector_dest != sector_orig:
            _exportar_sector(conn, sector_dest)
        return cur.rowcount


def novedades_reunion_sector(sector: str, fecha_reunion: str) -> list[dict[str, Any]]:
    """Novedades registradas en una fecha de reunión para pedidos del sector."""
    sector = sector.strip().upper()
    with _conectar() as conn:
        rows = conn.execute(
            """
            SELECT n.*, p.pedido, p.n_pedido, p.fecha AS pedido_fecha, p.oc
            FROM novedades n
            JOIN pedidos p ON p.id = n.pedido_id
            WHERE n.sector = ? AND n.fecha_reunion = ?
            ORDER BY p.n_pedido, p.id
            """,
            (sector, fecha_reunion.strip()),
        ).fetchall()
        return [dict(r) for r in rows]
