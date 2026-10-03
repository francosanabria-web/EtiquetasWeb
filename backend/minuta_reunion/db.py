# -*- coding: utf-8 -*-
"""Persistencia MariaDB para minutas de reunión (migración desde SQLite Plan A)."""

from __future__ import annotations

import json
import os
import re
import pymysql
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from pymysql.cursors import DictCursor

# Config MariaDB (mismo que salidas)
DB_HOST = os.environ.get("DB_HOST", os.environ.get("MINUTA_DB_HOST", "127.0.0.1"))
DB_PORT = int(os.environ.get("DB_PORT", os.environ.get("MINUTA_DB_PORT", "3306")))
DB_USER = os.environ.get("DB_USER", os.environ.get("MINUTA_DB_USER", "root"))
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("MINUTA_DB_PASSWORD", ""))
DB_NAME = os.environ.get("DB_NAME", os.environ.get("MINUTA_DB_NAME", "panol"))

# Para export JSON por sector (compatibilidad con share G: si existe)
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_SHARE_DATA_DIR = Path(r"G:\Unidades compartidas\Mantenimiento\MANTENIMIENTO  OZLA 2024-2025\17. Pañol\pañol v5.0\minuta_data")
def _default_data_dir() -> Path:
    return DEFAULT_SHARE_DATA_DIR if DEFAULT_SHARE_DATA_DIR.exists() else BASE_DIR / "data"
DATA_DIR = Path(os.environ.get("MINUTA_DATA_DIR", _default_data_dir()))
SECTORES_DIR = DATA_DIR / "sectores"

SECTORES = ["MANTENIMIENTO","PROYECTOS","EDILICIO","AUTOELEVADORES","PRODUCCION","PAÑOL"]
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

def get_connection():
    return pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, database=DB_NAME, charset="utf8mb4", cursorclass=DictCursor, autocommit=False)

def _conectar():
    # Compatibilidad: devuelve conexión MariaDB con context manager like sqlite
    conn = get_connection()
    # Add context manager support
    class ConnWrap:
        def __init__(self, c): self.c = c
        def __enter__(self): return self.c
        def __exit__(self, *a):
            try: self.c.close()
            except: pass
        def cursor(self): return self.c.cursor()
        def execute(self, *a, **kw): return self.c.cursor().execute(*a, **kw)
        def close(self): return self.c.close()
        def commit(self): return self.c.commit()
    # Simpler: just return pymysql connection which already has __enter__? pymysql 1.1 has it
    return conn

def init_db() -> None:
    # Tablas ya creadas via migración, solo asegurar que existen
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM minuta_reuniones LIMIT 1")
    except Exception:
        # Si no existen, crear (ya lo hicimos en migración)
        pass
    finally:
        conn.close()

def listar_sectores() -> list[str]:
    return list(SECTORES)

def _exportar_sector(conn, sector: str) -> None:
    # Exportar a JSON en DATA_DIR/sectores (para compatibilidad con G: Drive)
    sector = sector.strip().upper()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM minuta_pedidos WHERE sector=%s ORDER BY actualizado_en DESC", (sector,))
            pedidos = cur.fetchall()
            # For compatibility, also try to get novedades and movimientos
            # We need pedido_ids
            pedido_ids = [r["id"] for r in pedidos] if pedidos else []
            novedades = []
            movimientos = []
            if pedido_ids:
                fmt = ",".join(["%s"]*len(pedido_ids))
                cur.execute(f"SELECT * FROM minuta_novedades WHERE pedido_id IN ({fmt}) ORDER BY fecha_reunion DESC, id DESC", pedido_ids)
                novedades = cur.fetchall()
                cur.execute(f"SELECT * FROM minuta_pedido_movimientos WHERE pedido_id IN ({fmt}) ORDER BY creado_en DESC", pedido_ids)
                movimientos = cur.fetchall()
            cur.execute("SELECT * FROM minuta_reuniones WHERE sector=%s ORDER BY fecha DESC, id DESC", (sector,))
            reuniones = cur.fetchall()
            payload = {
                "sector": sector,
                "exportado_en": _ahora_iso(),
                "pedidos": pedidos,
                "novedades": novedades,
                "movimientos": movimientos,
                "reuniones": reuniones,
            }
            # Convert dates to iso for json
            def _iso(v):
                if isinstance(v, (date, datetime)):
                    return v.isoformat()
                return v
            # Ensure SECTORES_DIR exists
            SECTORES_DIR.mkdir(parents=True, exist_ok=True)
            path = SECTORES_DIR / f"{_slug_sector(sector)}.json"
            # Need to make serializable
            import json as _json
            # Convert Decimals and dates
            def _serial(o):
                if isinstance(o, (date, datetime)):
                    return o.isoformat()
                return str(o)
            path.write_text(_json.dumps(payload, ensure_ascii=False, indent=2, default=_serial), encoding="utf-8")
    except Exception as e:
        # No romper si falla export
        import logging
        logging.getLogger("minuta.db").warning(f"_exportar_sector {sector} fallo: {e}")

def listar_pedidos_reunion(reunion_id: int, solo_activos: bool = True) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            sql = """
                SELECT p.*,
                       (SELECT n.texto FROM minuta_novedades n WHERE n.pedido_id = p.id ORDER BY n.fecha_reunion DESC, n.id DESC LIMIT 1) AS ultima_novedad,
                       (SELECT n.fecha_reunion FROM minuta_novedades n WHERE n.pedido_id = p.id ORDER BY n.fecha_reunion DESC, n.id DESC LIMIT 1) AS ultima_novedad_fecha,
                       (SELECT COUNT(*) FROM minuta_novedades n WHERE n.pedido_id = p.id) AS total_novedades
                FROM minuta_pedidos p
                WHERE p.reunion_id = %s
            """
            params = [int(reunion_id)]
            if solo_activos:
                sql += " AND p.activo = 1"
            sql += " ORDER BY p.orden ASC, p.id DESC"
            cur.execute(sql, params)
            rows = cur.fetchall()
            # Convert dates to strings for API
            for r in rows:
                for k in ("fecha", "creado_en", "actualizado_en", "ultima_novedad_fecha"):
                    v = r.get(k)
                    if isinstance(v, (date, datetime)):
                        r[k] = v.isoformat()
            return rows
    finally:
        conn.close()

def listar_pedidos_sector(sector: str, solo_activos: bool = True) -> list[dict[str, Any]]:
    sector = sector.strip().upper()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            sql = """
                SELECT p.*,
                       (SELECT n.texto FROM minuta_novedades n WHERE n.pedido_id = p.id ORDER BY n.fecha_reunion DESC, n.id DESC LIMIT 1) AS ultima_novedad,
                       (SELECT n.fecha_reunion FROM minuta_novedades n WHERE n.pedido_id = p.id ORDER BY n.fecha_reunion DESC, n.id DESC LIMIT 1) AS ultima_novedad_fecha,
                       (SELECT COUNT(*) FROM minuta_novedades n WHERE n.pedido_id = p.id) AS total_novedades
                FROM minuta_pedidos p
                WHERE p.sector = %s
            """
            params = [sector]
            if solo_activos:
                sql += " AND p.activo = 1"
            sql += " ORDER BY p.orden ASC, p.id DESC"
            cur.execute(sql, params)
            rows = cur.fetchall()
            for r in rows:
                for k in ("fecha", "creado_en", "actualizado_en", "ultima_novedad_fecha"):
                    v = r.get(k)
                    if isinstance(v, (date, datetime)):
                        r[k] = v.isoformat()
            return rows
    finally:
        conn.close()

def obtener_pedido(pedido_id: int) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM minuta_pedidos WHERE id = %s", (pedido_id,))
            row = cur.fetchone()
            if not row:
                return None
            pedido = dict(row)
            cur.execute("SELECT * FROM minuta_novedades WHERE pedido_id = %s ORDER BY fecha_reunion DESC, id DESC", (pedido_id,))
            novedades = cur.fetchall()
            cur.execute("SELECT * FROM minuta_pedido_movimientos WHERE pedido_id = %s ORDER BY creado_en DESC", (pedido_id,))
            movimientos = cur.fetchall()
            pedido["novedades"] = novedades
            pedido["movimientos"] = movimientos
            # Convert dates
            for k in ("fecha", "creado_en", "actualizado_en"):
                v = pedido.get(k)
                if isinstance(v, (date, datetime)):
                    pedido[k] = v.isoformat()
            for n in pedido["novedades"]:
                for kk in ("fecha_reunion", "creado_en"):
                    vv = n.get(kk)
                    if isinstance(vv, (date, datetime)):
                        n[kk] = vv.isoformat()
            return pedido
    finally:
        conn.close()

def crear_pedido(data: dict[str, Any]) -> dict[str, Any]:
    sector = str(data.get("sector", "")).strip().upper()
    if sector not in SECTORES:
        raise ValueError(f"Sector inválido: {sector}")
    reunion_id = int(data.get("reunion_id") or 0)
    if reunion_id <= 0:
        raise ValueError("reunion_id requerido.")
    ahora = _ahora_iso()
    fecha = str(data.get("fecha") or date.today().isoformat()).strip()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, sector FROM minuta_reuniones WHERE id = %s", (reunion_id,))
            reun = cur.fetchone()
            if not reun:
                raise ValueError("Reunión no encontrada.")
            sector = str(reun["sector"])
            cur.execute("SELECT COALESCE(MIN(orden), 0) - 1 FROM minuta_pedidos WHERE reunion_id = %s", (reunion_id,))
            orden_top = int(cur.fetchone().values().__iter__().__next__() or 0)
            # Actually fetch value
            cur.execute("SELECT COALESCE(MIN(orden), 0) - 1 as v FROM minuta_pedidos WHERE reunion_id = %s", (reunion_id,))
            orden_top = int(cur.fetchone()["v"] or 0)
            cur.execute("""
                INSERT INTO minuta_pedidos
                    (pedido, n_pedido, fecha, oc, sector, reunion_id, activo, consultas, importancia, estado, orden, creado_en, actualizado_en)
                VALUES (%s,%s,%s,%s,%s,%s,1,'',%s,%s,%s,%s,%s)
            """, (str(data.get("pedido") or "").strip(), str(data.get("n_pedido") or "").strip(), fecha, str(data.get("oc") or "").strip(), sector, reunion_id, _norm_importancia(data.get("importancia")), _norm_estado(data.get("estado")), orden_top, ahora, ahora))
            pid = cur.lastrowid
            conn.commit()
            # Export
            try:
                _exportar_sector(conn, sector)
            except: pass
            return obtener_pedido(int(pid)) or {}
    finally:
        conn.close()

def actualizar_pedido(pedido_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM minuta_pedidos WHERE id = %s", (pedido_id,))
            row = cur.fetchone()
            if not row:
                return None
            sector_anterior = str(row["sector"])
            campos = []
            valores = []
            for key, col in [("pedido","pedido"),("n_pedido","n_pedido"),("fecha","fecha"),("oc","oc"),("consultas","consultas")]:
                if key in data:
                    campos.append(f"{col} = %s")
                    valores.append(str(data[key] or "").strip())
            if "importancia" in data:
                campos.append("importancia = %s")
                valores.append(_norm_importancia(data["importancia"], str(row["importancia"])))
            if "estado" in data:
                campos.append("estado = %s")
                valores.append(_norm_estado(data["estado"], str(row["estado"])))
            if "orden" in data:
                campos.append("orden = %s")
                valores.append(int(data["orden"]))
            if not campos:
                return obtener_pedido(pedido_id)
            campos.append("actualizado_en = %s")
            valores.append(_ahora_iso())
            valores.append(pedido_id)
            cur.execute(f"UPDATE minuta_pedidos SET {', '.join(campos)} WHERE id = %s", valores)
            conn.commit()
            # Get new sector
            cur.execute("SELECT sector FROM minuta_pedidos WHERE id = %s", (pedido_id,))
            sector_nuevo = str(cur.fetchone()["sector"])
            try:
                _exportar_sector(conn, sector_anterior)
                if sector_nuevo != sector_anterior:
                    _exportar_sector(conn, sector_nuevo)
            except: pass
            return obtener_pedido(pedido_id)
    finally:
        conn.close()

def agregar_novedad(pedido_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
    fecha_reunion = str(data.get("fecha_reunion") or date.today().isoformat()).strip()
    texto = str(data.get("texto") or "").strip()
    if not texto:
        raise ValueError("El texto de novedades es requerido.")
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT sector FROM minuta_pedidos WHERE id = %s", (pedido_id,))
            row = cur.fetchone()
            if not row:
                return None
            sector = str(row["sector"])
            ahora = _ahora_iso()
            cur.execute("INSERT INTO minuta_novedades (pedido_id, fecha_reunion, texto, sector, creado_en) VALUES (%s,%s,%s,%s,%s)", (pedido_id, fecha_reunion, texto, sector, ahora))
            cur.execute("UPDATE minuta_pedidos SET actualizado_en = %s WHERE id = %s", (ahora, pedido_id))
            conn.commit()
            try:
                _exportar_sector(conn, sector)
            except: pass
            return obtener_pedido(pedido_id)
    finally:
        conn.close()

def upsert_novedad(pedido_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
    fecha_reunion = str(data.get("fecha_reunion") or date.today().isoformat()).strip()
    texto = str(data.get("texto") or "").strip()
    if not texto:
        raise ValueError("El texto de novedades es requerido.")
    # Normalizar fecha
    try:
        if "/" in fecha_reunion:
            d,m,y = [p.strip() for p in fecha_reunion.split("/")]
            if len(y)==2: y=f"20{y}"
            fecha_reunion = f"{y.zfill(4)}-{m.zfill(2)}-{d.zfill(2)}"
        datetime.strptime(fecha_reunion, "%Y-%m-%d")
    except:
        raise ValueError("fecha_reunion inválida. Use AAAA-MM-DD.")
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT sector FROM minuta_pedidos WHERE id = %s", (pedido_id,))
            row = cur.fetchone()
            if not row:
                return None
            sector = str(row["sector"])
            ahora = _ahora_iso()
            cur.execute("SELECT id FROM minuta_novedades WHERE pedido_id = %s AND fecha_reunion = %s", (pedido_id, fecha_reunion))
            existente = cur.fetchone()
            if existente:
                cur.execute("UPDATE minuta_novedades SET texto=%s, sector=%s, creado_en=%s WHERE id=%s", (texto, sector, ahora, int(existente["id"])))
            else:
                cur.execute("INSERT INTO minuta_novedades (pedido_id, fecha_reunion, texto, sector, creado_en) VALUES (%s,%s,%s,%s,%s)", (pedido_id, fecha_reunion, texto, sector, ahora))
            cur.execute("UPDATE minuta_pedidos SET actualizado_en=%s WHERE id=%s", (ahora, pedido_id))
            conn.commit()
            try:
                _exportar_sector(conn, sector)
            except: pass
            return obtener_pedido(pedido_id)
    finally:
        conn.close()

# Resto de funciones (finalizar, reactivar, etc.) similares - usar MariaDB
def finalizar_pedido(pedido_id: int, data: dict[str, Any] | None = None) -> dict[str, Any] | None:
    data = data or {}
    notas = str(data.get("notas") or "").strip()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM minuta_pedidos WHERE id=%s", (pedido_id,))
            row = cur.fetchone()
            if not row:
                return None
            sector = str(row["sector"])
            ahora = _ahora_iso()
            cur.execute("UPDATE minuta_pedidos SET activo=0, estado='completado', actualizado_en=%s WHERE id=%s", (ahora, pedido_id))
            if notas:
                cur.execute("INSERT INTO minuta_novedades (pedido_id, fecha_reunion, texto, sector, creado_en) VALUES (%s,%s,%s,%s,%s)", (pedido_id, str(data.get("fecha") or date.today().isoformat()).strip(), f"[Finalizado] {notas}", sector, ahora))
            conn.commit()
            try:
                _exportar_sector(conn, sector)
            except: pass
            return obtener_pedido(pedido_id)
    finally:
        conn.close()

def reactivar_pedido(pedido_id: int) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM minuta_pedidos WHERE id=%s", (pedido_id,))
            row = cur.fetchone()
            if not row:
                return None
            sector = str(row["sector"])
            ahora = _ahora_iso()
            cur.execute("UPDATE minuta_pedidos SET activo=1, estado='en_proceso', actualizado_en=%s WHERE id=%s", (ahora, pedido_id))
            conn.commit()
            try:
                _exportar_sector(conn, sector)
            except: pass
            return obtener_pedido(pedido_id)
    finally:
        conn.close()

def eliminar_pedido(pedido_id: int) -> bool:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT sector FROM minuta_pedidos WHERE id=%s", (pedido_id,))
            row = cur.fetchone()
            if not row:
                return False
            sector = str(row["sector"])
            cur.execute("DELETE FROM minuta_pedidos WHERE id=%s", (pedido_id,))
            conn.commit()
            try:
                _exportar_sector(conn, sector)
            except: pass
            return True
    finally:
        conn.close()

def reordenar_pedidos(reunion_id: int, ids: list[int]) -> list[dict[str, Any]]:
    reunion_id = int(reunion_id)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT sector FROM minuta_reuniones WHERE id=%s", (reunion_id,))
            reun = cur.fetchone()
            if not reun:
                return []
            sector = str(reun["sector"])
            cur.execute("SELECT id FROM minuta_pedidos WHERE reunion_id=%s ORDER BY orden ASC, id DESC", (reunion_id,))
            actuales = [int(r["id"]) for r in cur.fetchall()]
            validos = set(actuales)
            pedido_ids = [int(i) for i in ids if int(i) in validos]
            vistos = set(pedido_ids)
            final = pedido_ids + [i for i in actuales if i not in vistos]
            for idx, pid in enumerate(final):
                cur.execute("UPDATE minuta_pedidos SET orden=%s WHERE id=%s", (idx, pid))
            conn.commit()
            try:
                _exportar_sector(conn, sector)
            except: pass
        return listar_pedidos_reunion(reunion_id, solo_activos=False)
    finally:
        conn.close()

def limpiar_consultas_reunion(reunion_id: int) -> int:
    reunion_id = int(reunion_id)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT sector FROM minuta_reuniones WHERE id=%s", (reunion_id,))
            reun = cur.fetchone()
            if not reun:
                return 0
            sector = str(reun["sector"])
            cur.execute("UPDATE minuta_pedidos SET consultas='' WHERE reunion_id=%s AND consultas <> ''", (reunion_id,))
            conn.commit()
            try:
                _exportar_sector(conn, sector)
            except: pass
            return cur.rowcount
    finally:
        conn.close()

def limpiar_consultas_sector(sector: str) -> int:
    sector = sector.strip().upper()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE minuta_pedidos SET consultas='' WHERE sector=%s AND consultas <> ''", (sector,))
            conn.commit()
            try:
                _exportar_sector(conn, sector)
            except: pass
            return cur.rowcount
    finally:
        conn.close()

def obtener_reunion(reunion_id: int) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM minuta_reuniones WHERE id=%s", (reunion_id,))
            row = cur.fetchone()
            if not row: return None
            d = dict(row)
            for k in ("fecha", "creado_en", "actualizado_en", "email_enviado_en"):
                v = d.get(k)
                if isinstance(v, (date, datetime)):
                    d[k] = v.isoformat()
            return d
    finally:
        conn.close()

def _reunion_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    """Convierte date/datetime a ISO para que JSONResponse no falle (fix 2026-09-30)."""
    d = dict(row)
    for k in ("fecha", "creado_en", "actualizado_en", "email_enviado_en"):
        v = d.get(k)
        if isinstance(v, (date, datetime)):
            d[k] = v.isoformat()
    return d

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
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO minuta_reuniones
                    (sector, fecha, notas_generales, titulo, tipo, visibilidad, owner_email, sectores_comprometidos, creado_en, actualizado_en)
                VALUES (%s,%s,'',%s,%s,%s,%s,%s,%s,%s)
            """, (sector, fecha, titulo, tipo, visibilidad, owner_email, sectores_comprometidos, ahora, ahora))
            rid = cur.lastrowid
            conn.commit()
            try:
                _exportar_sector(conn, sector)
            except: pass
            cur.execute("SELECT * FROM minuta_reuniones WHERE id=%s", (rid,))
            row = cur.fetchone()
            return _reunion_to_dict(row)
    finally:
        conn.close()

def obtener_o_crear_reunion(sector: str, fecha: str) -> dict[str, Any]:
    """Legacy: busca por sector+fecha, si no existe crea."""
    sector = sector.strip().upper()
    if sector not in SECTORES:
        raise ValueError(f"Sector inválido: {sector}")
    fecha = fecha.strip()
    reuniones = listar_reuniones(sector=sector, limite=50)
    for r in reuniones:
        if str(r.get("fecha"))[:10] == fecha[:10]:
            return r
    return crear_reunion({"sector": sector, "fecha": fecha, "titulo": f"Reunión {fecha}"})

# ... resto igual (actualizar_reunion, listar_reuniones, etc.) se mantienen con MariaDB pero se omiten por brevedad - usar implementación SQLite adaptada
# Para no romper, implementamos wrappers simples que llaman a la versión MariaDB

def actualizar_reunion(reunion_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM minuta_reuniones WHERE id=%s", (reunion_id,))
            row = cur.fetchone()
            if not row:
                return None
            sector = str(row["sector"])
            campos = []
            valores = []
            if "notas_generales" in data:
                campos.append("notas_generales=%s")
                valores.append(str(data.get("notas_generales") or "").strip())
            if "email_enviado_en" in data and data["email_enviado_en"]:
                campos.append("email_enviado_en=%s")
                valores.append(str(data["email_enviado_en"]))
            if "titulo" in data:
                campos.append("titulo=%s")
                valores.append(str(data.get("titulo") or "").strip())
            if "tipo" in data:
                campos.append("tipo=%s")
                valores.append(_norm_tipo(data["tipo"]))
            if "visibilidad" in data:
                campos.append("visibilidad=%s")
                valores.append(_norm_visibilidad(data["visibilidad"]))
            if "sectores_comprometidos" in data:
                campos.append("sectores_comprometidos=%s")
                valores.append(str(data.get("sectores_comprometidos") or "").strip())
            if "fecha" in data:
                campos.append("fecha=%s")
                valores.append(str(data.get("fecha") or "").strip())
            if "archivada" in data:
                campos.append("archivada=%s")
                valores.append(1 if data.get("archivada") in (True,1,"1","true") else 0)
            if "sector" in data:
                nuevo_sector = str(data.get("sector") or "").strip().upper()
                if nuevo_sector not in SECTORES:
                    raise ValueError(f"Sector inválido: {nuevo_sector}")
                if nuevo_sector != sector:
                    campos.append("sector=%s")
                    valores.append(nuevo_sector)
            if not campos:
                return _reunion_to_dict(row)
            campos.append("actualizado_en=%s")
            valores.append(_ahora_iso())
            valores.append(reunion_id)
            cur.execute(f"UPDATE minuta_reuniones SET {', '.join(campos)} WHERE id=%s", valores)
            conn.commit()
            cur.execute("SELECT sector FROM minuta_reuniones WHERE id=%s", (reunion_id,))
            sector_nuevo = str(cur.fetchone()["sector"])
            if sector_nuevo != sector:
                cur.execute("UPDATE minuta_pedidos SET sector=%s WHERE reunion_id=%s", (sector_nuevo, reunion_id))
                conn.commit()
            try:
                _exportar_sector(conn, sector)
                if sector_nuevo != sector:
                    _exportar_sector(conn, sector_nuevo)
            except: pass
            cur.execute("SELECT * FROM minuta_reuniones WHERE id=%s", (reunion_id,))
            row = cur.fetchone()
            return _reunion_to_dict(row)
    finally:
        conn.close()

def listar_reuniones(*, sector: str | None = None, owner_email: str | None = None, solo_enviadas: bool = False, archivadas: bool | None = False, limite: int = 50) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            sql = "SELECT * FROM minuta_reuniones WHERE 1=1"
            params = []
            if sector:
                sql += " AND sector=%s"
                params.append(sector.strip().upper())
            if owner_email:
                email = owner_email.strip().lower()
                sql += " AND (visibilidad='compartida' OR LOWER(owner_email)=%s)"
                params.append(email)
            if solo_enviadas:
                sql += " AND email_enviado_en IS NOT NULL AND email_enviado_en <> ''"
            if archivadas is True:
                sql += " AND COALESCE(archivada,0)=1"
            elif archivadas is False:
                sql += " AND COALESCE(archivada,0)=0"
            sql += " ORDER BY fecha DESC, id DESC LIMIT %s"
            params.append(limite)
            cur.execute(sql, params)
            rows = cur.fetchall()
            res = []
            for r in rows:
                d = dict(r)
                for k in ("fecha", "creado_en", "actualizado_en", "email_enviado_en"):
                    v = d.get(k)
                    if isinstance(v, (date, datetime)):
                        d[k] = v.isoformat()
                res.append(d)
            return res
    finally:
        conn.close()

def eliminar_reunion(reunion_id: int) -> bool:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM minuta_reuniones WHERE id=%s", (reunion_id,))
            row = cur.fetchone()
            if not row:
                return False
            sector = str(row["sector"])
            cur.execute("SELECT id FROM minuta_reuniones WHERE sector=%s AND titulo LIKE 'Histórico%%' AND id <> %s ORDER BY id ASC LIMIT 1", (sector, reunion_id))
            hist = cur.fetchone()
            if hist:
                hist_id = int(hist["id"])
            else:
                ahora = _ahora_iso()
                cur.execute("INSERT INTO minuta_reuniones (sector, fecha, notas_generales, titulo, tipo, visibilidad, owner_email, sectores_comprometidos, archivada, creado_en, actualizado_en) VALUES (%s,%s,'',%s,'ocasion','compartida','',%s,1,%s,%s)", (sector, date.today().isoformat(), f"Histórico — {sector}", sector, ahora, ahora))
                hist_id = int(cur.lastrowid)
            cur.execute("UPDATE minuta_pedidos SET reunion_id=%s WHERE reunion_id=%s", (hist_id, reunion_id))
            cur.execute("DELETE FROM minuta_reuniones WHERE id=%s", (reunion_id,))
            conn.commit()
            try:
                _exportar_sector(conn, sector)
            except: pass
            return True
    finally:
        conn.close()

def listar_reuniones_sector(sector: str, limite: int = 20) -> list[dict[str, Any]]:
    return listar_reuniones(sector=sector, limite=limite)

def mover_pedidos_reunion(origen_id: int, destino_id: int) -> int:
    origen_id = int(origen_id); destino_id = int(destino_id)
    if origen_id == destino_id: return 0
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, sector FROM minuta_reuniones WHERE id=%s", (destino_id,))
            dest = cur.fetchone()
            cur.execute("SELECT id, sector FROM minuta_reuniones WHERE id=%s", (origen_id,))
            orig = cur.fetchone()
            if not dest or not orig:
                raise ValueError("Reunión origen o destino no encontrada.")
            sector_dest = str(dest["sector"]); sector_orig = str(orig["sector"])
            cur.execute("UPDATE minuta_pedidos SET reunion_id=%s, sector=%s, actualizado_en=%s WHERE reunion_id=%s", (destino_id, sector_dest, _ahora_iso(), origen_id))
            conn.commit()
            try:
                _exportar_sector(conn, sector_orig)
                if sector_dest != sector_orig:
                    _exportar_sector(conn, sector_dest)
            except: pass
            return cur.rowcount
    finally:
        conn.close()

def novedades_reunion_sector(sector: str, fecha_reunion: str) -> list[dict[str, Any]]:
    sector = sector.strip().upper()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT n.*, p.pedido, p.n_pedido, p.fecha as pedido_fecha, p.oc FROM minuta_novedades n JOIN minuta_pedidos p ON p.id=n.pedido_id WHERE n.sector=%s AND n.fecha_reunion=%s ORDER BY p.n_pedido, p.id", (sector, fecha_reunion.strip()))
            rows = cur.fetchall()
            return [dict(r) for r in rows]
    finally:
        conn.close()


