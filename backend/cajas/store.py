# -*- coding: utf-8 -*-
"""Capa de acceso a datos para cajas_cajas y cajas_herramientas (MariaDB).

Implementa:
- Queries parametrizadas con UPPER(TRIM()) para codigo
- Coercion de "" / " " a NULL para descripcion, ubicacion, articulo_codigo
- Paginacion con limit/offset
- Busqueda por q, categoria, activo
- Manejo de Integridad Referencial (FK RESTRICT/NO ACTION)
"""

from __future__ import annotations

from typing import Any

from pymysql.err import IntegrityError, DataError
from pymysql import connections
from db import get_connection


def _coerce_null(val: Any) -> Any:
    """Convierte cadena vacia o solo espacios a None (SQL NULL)."""
    if isinstance(val, str) and val.strip() == "":
        return None
    return val


def _normalizar_codigo(codigo: str) -> str:
    """Aplica UPPER(TRIM(codigo))."""
    return codigo.strip().upper()


# --------------------------------------------------------------------------- #
# Cajas Cajas
# --------------------------------------------------------------------------- #
def listar_cajas(
    *,
    q: str = "",
    activo: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    conn = get_connection()
    try:
        conditions = []
        params: list[Any] = []

        if q:
            conditions.append("UPPER(TRIM(codigo)) LIKE CONCAT('%%', UPPER(TRIM(%s)), '%%')")
            params.append(q)
        if activo is not None:
            conditions.append("activa = %s")
            params.append(activo)

        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        count_sql = f"SELECT COUNT(*) c FROM cajas_cajas{where}"
        params_count = list(params)

        with conn.cursor() as cur:
            cur.execute(count_sql, params_count)
            total = cur.fetchone()["c"]

            data_sql = (
                f"SELECT id, codigo, descripcion, ubicacion, activa "
                f"FROM cajas_cajas{where} ORDER BY codigo ASC LIMIT %s OFFSET %s"
            )
            cur.execute(data_sql, params + [limit, offset])
            rows = cur.fetchall()

        items = []
        for r in rows:
            items.append({
                "id": r["id"],
                "codigo": r["codigo"],
                "descripcion": r["descripcion"],
                "ubicacion": r["ubicacion"],
                "activa": bool(r["activa"]),
            })

        return {"items": items, "total": total}
    finally:
        conn.close()


def obtener_caja(caja_id: int) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, codigo, descripcion, ubicacion, activa FROM cajas_cajas WHERE id = %s",
                (caja_id,),
            )
            row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "codigo": row["codigo"],
            "descripcion": row["descripcion"],
            "ubicacion": row["ubicacion"],
            "activa": bool(row["activa"]),
        }
    finally:
        conn.close()


def crear_caja(data: dict[str, Any]) -> dict[str, Any]:
    codigo = _normalizar_codigo(str(data.get("codigo") or ""))
    if not codigo:
        raise ValueError("El codigo es obligatorio.")

    descripcion = _coerce_null(data.get("descripcion"))
    ubicacion = _coerce_null(data.get("ubicacion"))
    activa = data.get("activa", True)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM cajas_cajas WHERE codigo = %s", (codigo,)
            )
            existing = cur.fetchone()
            if existing:
                raise ValueError(f"Ya existe una caja con el codigo '{codigo}'.")

            cur.execute(
                """INSERT INTO cajas_cajas (codigo, descripcion, ubicacion, activa)
                   VALUES (%s, %s, %s, %s)""",
                (codigo, descripcion, ubicacion, 1 if activa else 0),
            )
            conn.commit()
            cur.execute(
                "SELECT id, codigo, descripcion, ubicacion, activa FROM cajas_cajas WHERE id = LAST_INSERT_ID()"
            )
            row = cur.fetchone()

        return {
            "id": row["id"],
            "codigo": row["codigo"],
            "descripcion": row["descripcion"],
            "ubicacion": row["ubicacion"],
            "activa": bool(row["activa"]),
        }
    except IntegrityError as e:
        conn.rollback()
        raise ValueError(f"Violacion de unicidad: {e}")
    finally:
        conn.close()


def actualizar_caja(caja_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM cajas_cajas WHERE id = %s", (caja_id,)
            )
            existing = cur.fetchone()
            if not existing:
                return None

            updates = []
            params: list[Any] = []

            if "codigo" in data:
                codigo = _normalizar_codigo(str(data["codigo"]))
                if not codigo:
                    raise ValueError("El codigo no puede estar vacio.")
                cur.execute(
                    "SELECT id FROM cajas_cajas WHERE codigo = %s AND id != %s",
                    (codigo, caja_id),
                )
                dup = cur.fetchone()
                if dup:
                    raise ValueError(f"Ya existe otra caja con el codigo '{codigo}'.")
                updates.append("codigo = %s")
                params.append(codigo)

            if "descripcion" in data:
                desc = _coerce_null(data["descripcion"])
                updates.append("descripcion = %s")
                params.append(desc)

            if "ubicacion" in data:
                ubi = _coerce_null(data["ubicacion"])
                updates.append("ubicacion = %s")
                params.append(ubi)

            if "activa" in data:
                updates.append("activa = %s")
                params.append(1 if data["activa"] else 0)

            if updates:
                params.append(caja_id)
                set_clause = ", ".join(updates)
                cur.execute(f"UPDATE cajas_cajas SET {set_clause} WHERE id = %s", params)
                conn.commit()

            cur.execute(
                "SELECT id, codigo, descripcion, ubicacion, activa FROM cajas_cajas WHERE id = %s",
                (caja_id,),
            )
            row = cur.fetchone()

        if not row:
            return None
        return {
            "id": row["id"],
            "codigo": row["codigo"],
            "descripcion": row["descripcion"],
            "ubicacion": row["ubicacion"],
            "activa": bool(row["activa"]),
        }
    except IntegrityError as e:
        conn.rollback()
        raise ValueError(f"Violacion de unicidad: {e}")
    finally:
        conn.close()


def eliminar_caja(caja_id: int) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM cajas_cajas WHERE id = %s", (caja_id,)
            )
            existing = cur.fetchone()
            if not existing:
                return None

            # Verificar FK references: cajas_inventarios (FK desde caja) y detalle
            cur.execute(
                "SELECT COUNT(*) c FROM cajas_inventarios WHERE caja_id = %s",
                (caja_id,),
            )
            refs_inv = cur.fetchone()
            cur.execute(
                "SELECT COUNT(*) c FROM cajas_inventario_detalle WHERE inventario_id IN (SELECT id FROM cajas_inventarios WHERE caja_id = %s)",
                (caja_id,),
            )
            refs_det = cur.fetchone()

            if (refs_inv and refs_inv["c"] > 0) or (refs_det and refs_det["c"] > 0):
                raise ValueError("No se puede eliminar la caja: tiene registros asociados.")

            cur.execute("DELETE FROM cajas_cajas WHERE id = %s", (caja_id,))
            conn.commit()

        return {"id": caja_id, "eliminado": True}
    except IntegrityError as e:
        conn.rollback()
        raise ValueError(f"No se puede eliminar: restriccion FK - {e}")
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Cajas Herramientas
# --------------------------------------------------------------------------- #
def listar_herramientas(
    *,
    q: str = "",
    categoria: str = "",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    conn = get_connection()
    try:
        conditions = []
        params: list[Any] = []

        if q:
            conditions.append("UPPER(TRIM(codigo)) LIKE CONCAT('%%', UPPER(TRIM(%s)), '%%')")
            params.append(q)
        if categoria:
            conditions.append("categoria = %s")
            params.append(categoria)

        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        count_sql = f"SELECT COUNT(*) c FROM cajas_herramientas{where}"
        params_count = list(params)

        with conn.cursor() as cur:
            cur.execute(count_sql, params_count)
            total = cur.fetchone()["c"]

            data_sql = (
                f"SELECT id, codigo, descripcion, categoria, unidad, articulo_codigo "
                f"FROM cajas_herramientas{where} ORDER BY codigo ASC LIMIT %s OFFSET %s"
            )
            cur.execute(data_sql, params + [limit, offset])
            rows = cur.fetchall()

        items = []
        for r in rows:
            items.append({
                "id": r["id"],
                "codigo": r["codigo"],
                "descripcion": r["descripcion"],
                "categoria": r["categoria"],
                "unidad": r["unidad"],
                "articulo_codigo": r["articulo_codigo"],
            })

        return {"items": items, "total": total}
    finally:
        conn.close()


def obtener_herramienta(herramienta_id: int) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, codigo, descripcion, categoria, unidad, articulo_codigo FROM cajas_herramientas WHERE id = %s",
                (herramienta_id,),
            )
            row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "codigo": row["codigo"],
            "descripcion": row["descripcion"],
            "categoria": row["categoria"],
            "unidad": row["unidad"],
            "articulo_codigo": row["articulo_codigo"],
        }
    finally:
        conn.close()


def crear_herramienta(data: dict[str, Any]) -> dict[str, Any]:
    codigo = _normalizar_codigo(str(data.get("codigo") or ""))
    if not codigo:
        raise ValueError("El codigo es obligatorio.")

    descripcion = _coerce_null(data.get("descripcion"))
    # DB schema requires descripcion NOT NULL, use empty string if None
    if descripcion is None:
        descripcion = ""
    categoria = str(data.get("categoria") or "HERRAMIENTA").strip()
    unidad = str(data.get("unidad") or "UND").strip()
    articulo_codigo = _coerce_null(data.get("articulo_codigo"))

    CATEGORIAS_VALIDAS = ("HERRAMIENTA", "REPUESTO", "ACCESORIO", "MEDIDA", "OTRO")
    if categoria not in CATEGORIAS_VALIDAS:
        raise ValueError(f"Categoria invalida: {categoria}. Debe ser una de {CATEGORIAS_VALIDAS}.")

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM cajas_herramientas WHERE codigo = %s", (codigo,)
            )
            existing = cur.fetchone()
            if existing:
                raise ValueError(f"Ya existe una herramienta con el codigo '{codigo}'.")

            cur.execute(
                """INSERT INTO cajas_herramientas (codigo, descripcion, categoria, unidad, articulo_codigo)
                   VALUES (%s, %s, %s, %s, %s)""",
                (codigo, descripcion, categoria, unidad, articulo_codigo),
            )
            conn.commit()
            cur.execute(
                "SELECT id, codigo, descripcion, categoria, unidad, articulo_codigo FROM cajas_herramientas WHERE id = LAST_INSERT_ID()"
            )
            row = cur.fetchone()

        return {
            "id": row["id"],
            "codigo": row["codigo"],
            "descripcion": row["descripcion"],
            "categoria": row["categoria"],
            "unidad": row["unidad"],
            "articulo_codigo": row["articulo_codigo"],
        }
    except IntegrityError as e:
        conn.rollback()
        raise ValueError(f"Violacion de unicidad: {e}")
    finally:
        conn.close()


def actualizar_herramienta(herramienta_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM cajas_herramientas WHERE id = %s", (herramienta_id,)
            )
            existing = cur.fetchone()
            if not existing:
                return None

            updates = []
            params: list[Any] = []

            if "codigo" in data:
                codigo = _normalizar_codigo(str(data["codigo"]))
                if not codigo:
                    raise ValueError("El codigo no puede estar vacio.")
                cur.execute(
                    "SELECT id FROM cajas_herramientas WHERE codigo = %s AND id != %s",
                    (codigo, herramienta_id),
                )
                dup = cur.fetchone()
                if dup:
                    raise ValueError(f"Ya existe otra herramienta con el codigo '{codigo}'.")
                updates.append("codigo = %s")
                params.append(codigo)

            if "descripcion" in data:
                desc = _coerce_null(data["descripcion"])
                updates.append("descripcion = %s")
                params.append(desc)

            if "categoria" in data:
                cat = str(data["categoria"]).strip()
                CATEGORIAS_VALIDAS = ("HERRAMIENTA", "REPUESTO", "ACCESORIO", "MEDIDA", "OTRO")
                if cat not in CATEGORIAS_VALIDAS:
                    raise ValueError(f"Categoria invalida: {cat}")
                updates.append("categoria = %s")
                params.append(cat)

            if "unidad" in data:
                updates.append("unidad = %s")
                params.append(str(data["unidad"]).strip())

            if "articulo_codigo" in data:
                art = _coerce_null(data["articulo_codigo"])
                updates.append("articulo_codigo = %s")
                params.append(art)

            if updates:
                params.append(herramienta_id)
                set_clause = ", ".join(updates)
                cur.execute(f"UPDATE cajas_herramientas SET {set_clause} WHERE id = %s", params)
                conn.commit()

            cur.execute(
                "SELECT id, codigo, descripcion, categoria, unidad, articulo_codigo FROM cajas_herramientas WHERE id = %s",
                (herramienta_id,),
            )
            row = cur.fetchone()

        if not row:
            return None
        return {
            "id": row["id"],
            "codigo": row["codigo"],
            "descripcion": row["descripcion"],
            "categoria": row["categoria"],
            "unidad": row["unidad"],
            "articulo_codigo": row["articulo_codigo"],
        }
    except IntegrityError as e:
        conn.rollback()
        raise ValueError(f"Violacion de unicidad: {e}")
    finally:
        conn.close()


def eliminar_herramienta(herramienta_id: int) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM cajas_herramientas WHERE id = %s", (herramienta_id,)
            )
            existing = cur.fetchone()
            if not existing:
                return None

            # Verificar FK references en cajas_inventario_detalle
            cur.execute(
                "SELECT COUNT(*) c FROM cajas_inventario_detalle WHERE herramienta_id = %s",
                (herramienta_id,),
            )
            refs = cur.fetchone()
            if refs and refs["c"] > 0:
                raise ValueError("No se puede eliminar la herramienta: tiene registros de inventario asociados.")

            cur.execute("DELETE FROM cajas_herramientas WHERE id = %s", (herramienta_id,))
            conn.commit()

        return {"id": herramienta_id, "eliminado": True}
    except IntegrityError as e:
        conn.rollback()
        raise ValueError(f"No se puede eliminar: restriccion FK - {e}")
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Cajas Inventarios (Transaccional)
# --------------------------------------------------------------------------- #
def _normalizar_periodo(periodo_str: str) -> str:
    """Normaliza una fecha al primer dia del mes (YYYY-MM-DD)."""
    from datetime import datetime
    dt = datetime.strptime(periodo_str, "%Y-%m-%d")
    return dt.replace(day=1).strftime("%Y-%m-%d")


def crear_inventario_txn(data: dict[str, Any]) -> dict[str, Any]:
    """CREA inventario header + detalle en TRANSACCION. UNIQUE caja_id+periodo -> 409."""
    caja_id = data.get("caja_id")
    tecnico_id = data.get("tecnico_id")
    supervisor_id = data.get("supervisor_id")
    periodo_raw = data.get("periodo")
    estado = data.get("estado", "borrador")
    obs = data.get("obs")
    detalle = data.get("detalle", [])

    if not caja_id:
        raise ValueError("caja_id es obligatorio.")
    if not tecnico_id:
        raise ValueError("tecnico_id es obligatorio.")
    if not supervisor_id:
        raise ValueError("supervisor_id es obligatorio.")
    if not periodo_raw:
        raise ValueError("periodo es obligatorio.")

    periodo = _normalizar_periodo(str(periodo_raw))

    if estado not in ("borrador", "cerrado"):
        raise ValueError("estado must be 'borrador' or 'cerrado'.")

    if not isinstance(detalle, list) or len(detalle) == 0:
        raise ValueError("detalle must contain at least one item.")

    # Validar cada item del detalle
    for i, item in enumerate(detalle):
        if not item.get("herramienta_codigo"):
            raise ValueError(f"detalle[{i}]: herramienta_codigo es obligatorio.")
        cantidad = item.get("cantidad")
        if not isinstance(cantidad, (int, float)) or cantidad <= 0:
            raise ValueError(f"detalle[{i}]: cantidad must be integer > 0.")
        presente = item.get("presente")
        if not isinstance(presente, bool):
            raise ValueError(f"detalle[{i}]: presente must be boolean.")

    # Validar tipos de personal (CRITICAL #7) - inside main transaction to avoid pool close issues
    TIPOS_PERMITIDOS = ("tecnico", "supervisor", "generico", "panol")
    conn = get_connection()
    inventario_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT tipo FROM personal WHERE id = %s", (tecnico_id,))
            t_row = cur.fetchone()
            if not t_row or t_row["tipo"] not in TIPOS_PERMITIDOS:
                raise ValueError(f"tecnico_id {tecnico_id}: tipo '{t_row['tipo'] if t_row else 'N/A'}' no permitido. Debe ser tecnico/supervisor/generico.")
            cur.execute("SELECT tipo FROM personal WHERE id = %s", (supervisor_id,))
            s_row = cur.fetchone()
            if not s_row or s_row["tipo"] not in TIPOS_PERMITIDOS:
                raise ValueError(f"supervisor_id {supervisor_id}: tipo '{s_row['tipo'] if s_row else 'N/A'}' no permitido. Debe ser tecnico/supervisor/generico.")
            # BEGIN transaccion
            cur.execute("BEGIN")

            # Verificar UNIQUE caja_id + periodo
            cur.execute(
                "SELECT id FROM cajas_inventarios WHERE caja_id = %s AND periodo = %s",
                (caja_id, periodo),
            )
            if cur.fetchone():
                conn.rollback()
                raise ValueError("ya existe inventario de esta caja para ese período")

            # Snapshot area desde cajas_cajas.ubicacion
            cur.execute(
                "SELECT ubicacion FROM cajas_cajas WHERE id = %s", (caja_id,)
            )
            caja_row = cur.fetchone()
            if not caja_row:
                conn.rollback()
                raise ValueError(f"caja_id {caja_id} no existe.")
            area = caja_row["ubicacion"] or "General"
            if not area or str(area).strip() == "":
                area = "General"

            # Insertar header - use actual schema columns (area NOT NULL, obs_generales)
            cur.execute(
                """INSERT INTO cajas_inventarios
                   (caja_id, fecha, periodo, tecnico_id, area, supervisor_id, obs_generales, estado)
                   VALUES (%s, CURDATE(), %s, %s, %s, %s, %s, %s)""",
                (caja_id, periodo, tecnico_id, area, supervisor_id,
                 obs or None, estado),
            )
            inventario_id = cur.lastrowid

            # Insertar detalle — buscar herramienta_id desde herramienta_codigo
            for i, item in enumerate(detalle):
                cur.execute(
                    "SELECT id FROM cajas_herramientas WHERE codigo = %s",
                    (item["herramienta_codigo"],),
                )
                ht_row = cur.fetchone()
                if not ht_row:
                    conn.rollback()
                    raise ValueError(f"detalle[{i}]: herramienta_codigo '{item['herramienta_codigo']}' no existe.")
                herramienta_id = ht_row["id"]
                cur.execute(
                    """INSERT INTO cajas_inventario_detalle
                       (inventario_id, herramienta_id, nro_item, cantidad, estado, presente, observaciones)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (inventario_id, herramienta_id, i + 1,
                     int(item["cantidad"]), "bueno" if item.get("estado") == "bueno" else "regular",
                     item["presente"],
                     item.get("observaciones") or None),
                )

            conn.commit()
        # Fetch complete object after transaction, outside cursor context
        if inventario_id is not None:
            return obtener_inventario(inventario_id)
        return None

    except IntegrityError as e:
        conn.rollback()
        # Verificar si es violacion UNIQUE caja_id+periodo
        if "uq_caja_periodo" in str(e).lower() or "Duplicate" in str(e):
            raise ValueError("ya existe inventario de esta caja para ese período")
        raise ValueError(f"Violacion de integridad: {e}")
    except DataError as e:
        conn.rollback()
        raise ValueError(f"Error de datos: {e}")
    finally:
        try:
            if conn.open:
                conn.close()
        except Exception:
            pass


def obtener_inventario(inventario_id: int) -> dict[str, Any] | None:
    """Retorna inventario completo con JOIN personal names y detalle."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT inv.*,
                          p_tec.nombre as tecnico_nombre,
                          p_sup.nombre as supervisor_nombre,
                          cj.codigo as caja_codigo
                   FROM cajas_inventarios inv
                   LEFT JOIN personal p_tec ON inv.tecnico_id = p_tec.id
                   LEFT JOIN personal p_sup ON inv.supervisor_id = p_sup.id
                   LEFT JOIN cajas_cajas cj ON inv.caja_id = cj.id
                   WHERE inv.id = %s""",
                (inventario_id,),
            )
            row = cur.fetchone()
            if not row:
                return None

            # Obtener detalle
            cur.execute(
                """SELECT id, herramienta_id, nro_item, cantidad, estado, presente, observaciones
                   FROM cajas_inventario_detalle
                   WHERE inventario_id = %s ORDER BY nro_item ASC""",
                (inventario_id,),
            )
            detalle_rows = cur.fetchall()

            detalle = []
            for dr in detalle_rows:
                # Obtener codigo de herramienta
                cur.execute(
                    "SELECT codigo FROM cajas_herramientas WHERE id = %s",
                    (dr["herramienta_id"],),
                )
                ht_row = cur.fetchone()
                detalle.append({
                    "id": dr["id"],
                    "herramienta_codigo": ht_row["codigo"] if ht_row else str(dr["herramienta_id"]),
                    "nro_item": dr["nro_item"],
                    "cantidad": dr["cantidad"],
                    "estado": dr["estado"],
                    "presente": bool(dr["presente"]),
                    "observaciones": dr["observaciones"],
                })

            return {
                "id": row["id"],
                "caja_id": row["caja_id"],
                "caja_codigo": row["caja_codigo"],
                "fecha": str(row["fecha"]) if row["fecha"] else None,
                "periodo": str(row["periodo"]),
                "tecnico_id": row["tecnico_id"],
                "tecnico_nombre": row.get("tecnico_nombre"),
                "supervisor_id": row["supervisor_id"],
                "supervisor_nombre": row.get("supervisor_nombre"),
                "area": row["area"],
                "estado": row["estado"],
                "obs": row.get("obs") or row.get("obs_generales"),
                "detalle": detalle,
            }
    finally:
        conn.close()


def listar_inventarios(
    *,
    caja_id: int | None = None,
    periodo: str | None = None,
    estado: str | None = None,
    q: str = "",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Lista inventarios con filtros y JOIN personal names."""
    conn = get_connection()
    try:
        conditions = []
        params: list[Any] = []

        if caja_id is not None:
            conditions.append("inv.caja_id = %s")
            params.append(caja_id)
        if periodo:
            p = _normalizar_periodo(periodo)
            conditions.append("inv.periodo = %s")
            params.append(p)
        if estado:
            conditions.append("inv.estado = %s")
            params.append(estado)
        if q:
            conditions.append("(UPPER(TRIM(p_tec.nombre)) LIKE CONCAT('%%', UPPER(TRIM(%s)), '%%') OR UPPER(TRIM(p_sup.nombre)) LIKE CONCAT('%%', UPPER(TRIM(%s)), '%%'))")
            params.append(q)
            params.append(q)

        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        count_sql = f"SELECT COUNT(*) c FROM cajas_inventarios inv LEFT JOIN personal p_tec ON inv.tecnico_id = p_tec.id LEFT JOIN personal p_sup ON inv.supervisor_id = p_sup.id{where}"
        params_count = list(params)

        with conn.cursor() as cur:
            cur.execute(count_sql, params_count)
            total = cur.fetchone()["c"]

            data_sql = (
                f"""SELECT inv.*, p_tec.nombre as tecnico_nombre, p_sup.nombre as supervisor_nombre
                    FROM cajas_inventarios inv
                    LEFT JOIN personal p_tec ON inv.tecnico_id = p_tec.id
                    LEFT JOIN personal p_sup ON inv.supervisor_id = p_sup.id
                    {where} ORDER BY inv.periodo DESC, inv.id DESC
                    LIMIT %s OFFSET %s"""
            )
            cur.execute(data_sql, params + [limit, offset])
            rows = cur.fetchall()

        items = []
        for r in rows:
            items.append({
                "id": r["id"],
                "caja_id": r["caja_id"],
                "periodo": str(r["periodo"]),
                "estado": r["estado"],
                "tecnico_id": r["tecnico_id"],
                "tecnico_nombre": r.get("tecnico_nombre"),
                "supervisor_id": r["supervisor_id"],
                "supervisor_nombre": r.get("supervisor_nombre"),
                "obs": r.get("obs") or r.get("obs_generales"),
                "area": r["area"],
            })

        return {"items": items, "total": total}
    finally:
        conn.close()


def actualizar_estado_inventario(inventario_id: int, nuevo_estado: str) -> dict[str, Any] | None:
    """Actualiza estado de inventario con máquina de estados."""
    if nuevo_estado not in ("borrador", "cerrado"):
        raise ValueError("estado must be 'borrador' or 'cerrado'.")

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT estado FROM cajas_inventarios WHERE id = %s", (inventario_id,)
            )
            row = cur.fetchone()
            if not row:
                return None

            estado_actual = row["estado"]

            # Transiciones validas: borrador -> cerrado
            if estado_actual == "cerrado" and nuevo_estado == "borrador":
                raise ValueError("no se puede revertir a borrador una vez cerrado")
            if estado_actual == nuevo_estado:
                return {"id": inventario_id, "estado": nuevo_estado, "changed": False}

            cur.execute(
                "UPDATE cajas_inventarios SET estado = %s WHERE id = %s",
                (nuevo_estado, inventario_id),
            )
            conn.commit()

        return {"id": inventario_id, "estado": nuevo_estado, "changed": True}
    except IntegrityError as e:
        conn.rollback()
        raise ValueError(f"No se puede actualizar estado: {e}")
    finally:
        conn.close()


def eliminar_inventario(inventario_id: int) -> dict[str, Any] | None:
    """Elimina inventario solo si estado = borrador."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT estado FROM cajas_inventarios WHERE id = %s", (inventario_id,)
            )
            row = cur.fetchone()
            if not row:
                return None

            if row["estado"] != "borrador":
                raise ValueError("no se puede borrar un inventario cerrado")

            # Verificar FK references en detalle (cascade delete para borrador)
            cur.execute(
                "DELETE FROM cajas_inventario_detalle WHERE inventario_id = %s",
                (inventario_id,),
            )
            cur.execute("DELETE FROM cajas_inventarios WHERE id = %s", (inventario_id,))
            conn.commit()

        return {"id": inventario_id, "eliminado": True}
    except IntegrityError as e:
        conn.rollback()
        raise ValueError(f"No se puede eliminar: restriccion FK - {e}")
    finally:
        conn.close()
