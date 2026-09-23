# -*- coding: utf-8 -*-
"""Capa de acceso a datos para areas y personal (MariaDB).

Implementa:
- Queries parametrizadas con UPPER(TRIM()) para nombres
- Coercion de "" / " " a NULL para legajo y email
- Paginacion con limit/offset
- Busqueda por q, area_id, tipo, activo
- Manejo de Integridad Referencial (FK RESTRICT)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pymysql.err import IntegrityError
from db import get_connection


def _coerce_null(val: Any) -> Any:
    """Convierte cadena vacia o solo espacios a None (SQL NULL)."""
    if isinstance(val, str) and val.strip() == "":
        return None
    return val


def _normalizar_nombre(nombre: str) -> str:
    """Aplica UPPER(TRIM(nombre))."""
    return nombre.strip().upper()


# --------------------------------------------------------------------------- #
# Areas
# --------------------------------------------------------------------------- #
def listar_areas() -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, nombre FROM areas WHERE activo = 1 ORDER BY nombre ASC"
            )
            rows = cur.fetchall()
        return [{"id": r["id"], "nombre": r["nombre"]} for r in rows]
    finally:
        conn.close()


def obtener_area(area_id: int) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, nombre FROM areas WHERE id = %s AND activo = 1", (area_id,)
            )
            row = cur.fetchone()
        return {"id": row["id"], "nombre": row["nombre"]} if row else None
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Personal
# --------------------------------------------------------------------------- #
def listar_personal(
    *,
    q: str = "",
    area_id: int | None = None,
    tipo: str = "",
    activo: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    conn = get_connection()
    try:
        conditions = []
        params: list[Any] = []

        if q:
            conditions.append("UPPER(TRIM(nombre)) LIKE CONCAT('%', UPPER(TRIM(%s)), '%')")
            params.append(q)
        if area_id is not None:
            conditions.append("area_id = %s")
            params.append(area_id)
        if tipo:
            conditions.append("tipo = %s")
            params.append(tipo)
        if activo is not None:
            conditions.append("activo = %s")
            params.append(activo)

        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        count_sql = f"SELECT COUNT(*) c FROM personal{where}"
        params_count = list(params)

        with conn.cursor() as cur:
            cur.execute(count_sql, params_count)
            total = cur.fetchone()["c"]

            data_sql = (
                f"SELECT id, legajo, nombre, email, area_id, tipo, activo "
                f"FROM personal{where} ORDER BY nombre ASC LIMIT %s OFFSET %s"
            )
            cur.execute(data_sql, params + [limit, offset])
            rows = cur.fetchall()

        items = []
        for r in rows:
            items.append({
                "id": r["id"],
                "legajo": r["legajo"],
                "nombre": r["nombre"],
                "email": r["email"],
                "area_id": r["area_id"],
                "tipo": r["tipo"],
                "activo": bool(r["activo"]),
            })

        return {"items": items, "total": total}
    finally:
        conn.close()


def obtener_personal(personal_id: int) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, legajo, nombre, email, area_id, tipo, activo FROM personal WHERE id = %s",
                (personal_id,),
            )
            row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "legajo": row["legajo"],
            "nombre": row["nombre"],
            "email": row["email"],
            "area_id": row["area_id"],
            "tipo": row["tipo"],
            "activo": bool(row["activo"]),
        }
    finally:
        conn.close()


def crear_personal(data: dict[str, Any]) -> dict[str, Any]:
    nombre = _normalizar_nombre(str(data.get("nombre") or ""))
    if not nombre:
        raise ValueError("El nombre es obligatorio.")

    legajo = _coerce_null(data.get("legajo"))
    email = _coerce_null(data.get("email"))
    raw_area = data.get("area_id")
    # Normalizar 0 / "0" / "" -> None (Sin área) para compat con bug frontend Number("") => 0
    # Frontend ya envía ""/null tras fix, pero backend coerce 0 por seguridad (no 500)
    if raw_area == "" or raw_area == 0 or raw_area == "0":
        area_id = None
    else:
        area_id = raw_area
    # Normalizar area_id a int si es != None, pero validar dentro de la transacción
    area_id_int: int | None = None
    if area_id is not None:
        try:
            area_id_int = int(area_id)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            raise ValueError(f"Area con id {area_id} no existe.")
        if area_id_int == 0:
            area_id = None
            area_id_int = None

    tipo = str(data.get("tipo", "tecnico")).strip()
    activo = data.get("activo", True)

    TIPOS_VALIDOS = ("tecnico", "supervisor", "produccion", "generico", "panol")
    if tipo not in TIPOS_VALIDOS:
        raise ValueError(f"Tipo invalido: {tipo}. Debe ser uno de {TIPOS_VALIDOS}.")

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Validar área dentro de la misma conexión (evita cerrar el pool compartido)
            if area_id is not None:
                # area_id_int ya validado arriba (no 0, int convertible)
                cur.execute("SELECT id FROM areas WHERE id=%s AND activo=1", (area_id_int,))
                if not cur.fetchone():
                    raise ValueError(f"Area con id {area_id} no existe.")

            cur.execute(
                "SELECT id FROM personal WHERE UPPER(TRIM(nombre)) = %s", (nombre,)
            )
            existing = cur.fetchone()
            if existing:
                raise ValueError(f"Ya existe un personal con el nombre '{nombre}'.")

            cur.execute(
                """INSERT INTO personal (legajo, nombre, email, area_id, tipo, activo)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (legajo, nombre, email, area_id_int, tipo, 1 if activo else 0),
            )
            conn.commit()
            cur.execute(
                "SELECT id, legajo, nombre, email, area_id, tipo, activo FROM personal WHERE id = LAST_INSERT_ID()"
            )
            row = cur.fetchone()

        return {
            "id": row["id"],
            "legajo": row["legajo"],
            "nombre": row["nombre"],
            "email": row["email"],
            "area_id": row["area_id"],
            "tipo": row["tipo"],
            "activo": bool(row["activo"]),
        }
    except IntegrityError as e:
        conn.rollback()
        raise ValueError(f"Violacion de unicidad: {e}")
    finally:
        conn.close()


def actualizar_personal(personal_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM personal WHERE id = %s", (personal_id,)
            )
            existing = cur.fetchone()
            if not existing:
                return None

            updates = []
            params: list[Any] = []

            if "nombre" in data:
                nombre = _normalizar_nombre(str(data["nombre"]))
                if not nombre:
                    raise ValueError("El nombre no puede estar vacio.")
                cur.execute(
                    "SELECT id FROM personal WHERE UPPER(TRIM(nombre)) = %s AND id != %s",
                    (nombre, personal_id),
                )
                dup = cur.fetchone()
                if dup:
                    raise ValueError(f"Ya existe otro personal con el nombre '{nombre}'.")
                updates.append("nombre = %s")
                params.append(nombre)

            if "legajo" in data:
                legajo = _coerce_null(data["legajo"])
                updates.append("legajo = %s")
                params.append(legajo)

            if "email" in data:
                email = _coerce_null(data["email"])
                updates.append("email = %s")
                params.append(email)

            if "area_id" in data:
                raw_area = data["area_id"]
                # Normalizar 0 / "0" / "" -> None (Sin área) - compat bug frontend Number("") => 0
                if raw_area == "" or raw_area == 0 or raw_area == "0":
                    area_id_val = None
                else:
                    area_id_val = raw_area
                if area_id_val is not None:
                    try:
                        area_id_int = int(area_id_val)  # type: ignore[arg-type]
                    except (TypeError, ValueError):
                        raise ValueError(f"Area con id {area_id_val} no existe.")
                    if area_id_int == 0:
                        area_id_val = None
                    else:
                        cur.execute("SELECT id FROM areas WHERE id=%s AND activo=1", (area_id_int,))
                        if not cur.fetchone():
                            raise ValueError(f"Area con id {area_id_val} no existe.")
                        area_id_val = area_id_int
                updates.append("area_id = %s")
                params.append(area_id_val)

            if "tipo" in data:
                tipo = str(data["tipo"]).strip()
                TIPOS_VALIDOS = ("tecnico", "supervisor", "produccion", "generico", "panol")
                if tipo not in TIPOS_VALIDOS:
                    raise ValueError(f"Tipo invalido: {tipo}")
                updates.append("tipo = %s")
                params.append(tipo)

            if "activo" in data:
                updates.append("activo = %s")
                params.append(1 if data["activo"] else 0)

            if updates:
                params.append(personal_id)
                set_clause = ", ".join(updates)
                cur.execute(f"UPDATE personal SET {set_clause} WHERE id = %s", params)
                conn.commit()

            cur.execute(
                "SELECT id, legajo, nombre, email, area_id, tipo, activo FROM personal WHERE id = %s",
                (personal_id,),
            )
            row = cur.fetchone()

        if not row:
            return None
        return {
            "id": row["id"],
            "legajo": row["legajo"],
            "nombre": row["nombre"],
            "email": row["email"],
            "area_id": row["area_id"],
            "tipo": row["tipo"],
            "activo": bool(row["activo"]),
        }
    except IntegrityError as e:
        conn.rollback()
        raise ValueError(f"Violacion de unicidad: {e}")
    finally:
        conn.close()


def eliminar_personal(personal_id: int) -> dict[str, Any]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM personal WHERE id = %s", (personal_id,)
            )
            existing = cur.fetchone()
            if not existing:
                return None

            cur.execute(
                "SELECT COUNT(*) c FROM cajas_inventarios WHERE tecnico_id = %s OR supervisor_id = %s",
                (personal_id, personal_id),
            )
            refs = cur.fetchone()
            if refs and refs["c"] > 0:
                raise ValueError(
                    "No se puede eliminar el trabajador porque tiene registros de actividad asociados."
                )

            cur.execute("UPDATE personal SET activo = 0 WHERE id = %s", (personal_id,))
            conn.commit()

        return {"id": personal_id, "eliminado": True}
    except IntegrityError as e:
        conn.rollback()
        raise ValueError(f"No se puede eliminar: restriccion FK - {e}")
    finally:
        conn.close()


def contar_personal_con_area(area_id: int) -> int:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) c FROM personal WHERE area_id = %s AND activo = 1",
                (area_id,),
            )
            row = cur.fetchone()
        return row["c"]
    finally:
        conn.close()
