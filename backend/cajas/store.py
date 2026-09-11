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

from pymysql.err import IntegrityError
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
            conditions.append("UPPER(TRIM(codigo)) LIKE CONCAT('%', UPPER(TRIM(%s)), '%')")
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

            # Verificar FK references en cajas_herramientas y cajas_inventario_detalle
            cur.execute(
                "SELECT COUNT(*) c FROM cajas_herramientas WHERE caja_id = %s",
                (caja_id,),
            )
            refs_tool = cur.fetchone()
            cur.execute(
                "SELECT COUNT(*) c FROM cajas_inventario_detalle WHERE caja_id = %s",
                (caja_id,),
            )
            refs_inv = cur.fetchone()

            if (refs_tool and refs_tool["c"] > 0) or (refs_inv and refs_inv["c"] > 0):
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
    activo: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    conn = get_connection()
    try:
        conditions = []
        params: list[Any] = []

        if q:
            conditions.append("UPPER(TRIM(codigo)) LIKE CONCAT('%', UPPER(TRIM(%s)), '%')")
            params.append(q)
        if categoria:
            conditions.append("categoria = %s")
            params.append(categoria)
        if activo is not None:
            conditions.append("activa = %s")
            params.append(activo)

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
                "SELECT COUNT(*) c FROM cajas_inventario_detalle WHERE herramienta_codigo = %s",
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
