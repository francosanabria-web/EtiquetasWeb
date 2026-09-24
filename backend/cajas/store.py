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
# Caja Ideal (Versionado) — slice 1
# --------------------------------------------------------------------------- #
def get_ideal_actual() -> dict[str, Any] | None:
    """Retorna la Caja Ideal activa con su detalle (herramientas join) o None."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, nombre, descripcion, activa, vigente_desde, creado_por, creado_en
                FROM cajas_caja_ideal
                WHERE activa = 1
                ORDER BY vigente_desde DESC
                LIMIT 1
                """
            )
            row = cur.fetchone()
            if not row:
                return None
            ideal_id = row["id"]
            cur.execute(
                """
                SELECT d.id, d.herramienta_id, d.cantidad_minima, d.articulo_codigo,
                       h.codigo, h.descripcion
                FROM cajas_caja_ideal_detalle d
                JOIN cajas_herramientas h ON h.id = d.herramienta_id
                WHERE d.caja_ideal_id = %s
                ORDER BY h.codigo ASC
                """,
                (ideal_id,),
            )
            detalle_rows = cur.fetchall()
            herramientas = []
            for dr in detalle_rows:
                herramientas.append({
                    "id": dr["id"],
                    "herramienta_id": dr["herramienta_id"],
                    "codigo": dr["codigo"],
                    "descripcion": dr["descripcion"],
                    "cantidad_minima": dr["cantidad_minima"],
                    "articulo_codigo": dr["articulo_codigo"],
                })
            return {
                "id": row["id"],
                "nombre": row["nombre"],
                "descripcion": row["descripcion"],
                "activa": bool(row["activa"]),
                "vigente_desde": str(row["vigente_desde"]) if row["vigente_desde"] else None,
                "creado_por": row["creado_por"],
                "creado_en": str(row["creado_en"]) if row["creado_en"] else None,
                "herramientas": herramientas,
            }
    finally:
        try:
            if conn.open:
                conn.close()
        except Exception:
            pass


def obtener_ideal_detalle(ideal_id: int) -> dict[str, Any] | None:
    """Retorna ideal por id con su detalle (helper para historial)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, nombre, descripcion, activa, vigente_desde, creado_por, creado_en
                FROM cajas_caja_ideal
                WHERE id = %s
                """,
                (ideal_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            cur.execute(
                """
                SELECT d.id, d.herramienta_id, d.cantidad_minima, d.articulo_codigo,
                       h.codigo, h.descripcion
                FROM cajas_caja_ideal_detalle d
                JOIN cajas_herramientas h ON h.id = d.herramienta_id
                WHERE d.caja_ideal_id = %s
                ORDER BY h.codigo ASC
                """,
                (ideal_id,),
            )
            detalle_rows = cur.fetchall()
            herramientas = []
            for dr in detalle_rows:
                herramientas.append({
                    "id": dr["id"],
                    "herramienta_id": dr["herramienta_id"],
                    "codigo": dr["codigo"],
                    "descripcion": dr["descripcion"],
                    "cantidad_minima": dr["cantidad_minima"],
                    "articulo_codigo": dr["articulo_codigo"],
                })
            return {
                "id": row["id"],
                "nombre": row["nombre"],
                "descripcion": row["descripcion"],
                "activa": bool(row["activa"]),
                "vigente_desde": str(row["vigente_desde"]) if row["vigente_desde"] else None,
                "creado_por": row["creado_por"],
                "creado_en": str(row["creado_en"]) if row["creado_en"] else None,
                "herramientas": herramientas,
            }
    finally:
        try:
            if conn.open:
                conn.close()
        except Exception:
            pass


def listar_ideal_versiones(
    *,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Lista paginada de versiones de Caja Ideal ordenadas vigente_desde DESC."""
    # Normalizar paginación como en listar_cajas
    try:
        limit = int(limit)
    except Exception:
        limit = 50
    try:
        offset = int(offset)
    except Exception:
        offset = 0
    if limit < 1:
        limit = 1
    if limit > 100:
        limit = 100
    if offset < 0:
        offset = 0
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) c FROM cajas_caja_ideal")
            total = cur.fetchone()["c"]
            cur.execute(
                """
                SELECT id, nombre, descripcion, activa, vigente_desde, creado_por, creado_en
                FROM cajas_caja_ideal
                ORDER BY vigente_desde DESC, id DESC
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            )
            rows = cur.fetchall()
        items = []
        for r in rows:
            items.append({
                "id": r["id"],
                "nombre": r["nombre"],
                "descripcion": r["descripcion"],
                "activa": bool(r["activa"]),
                "vigente_desde": str(r["vigente_desde"]) if r["vigente_desde"] else None,
                "creado_por": r["creado_por"],
                "creado_en": str(r["creado_en"]) if r["creado_en"] else None,
            })
        return {"items": items, "total": total}
    finally:
        try:
            if conn.open:
                conn.close()
        except Exception:
            pass


def crear_ideal_versionado(data: dict[str, Any], creado_por: int | None = None) -> dict[str, Any]:
    """Crea una nueva versión de Caja Ideal versionada transaccionalmente.

    Transacción: UPDATE activa=0 WHERE activa=1; INSERT nueva activa=1 NOW(); batch INSERT detalle.
    Valida:
    - nombre obligatorio
    - detalle list min 1 item
    - cada item herramienta_codigo existe, cantidad_minima int>0
    - duplicate herramienta en mismo payload -> 409 (ValueError con 'ya asignada')
    - herramienta no encontrada -> 400
    Retorna ideal completo vía get_ideal_actual() / obtener_ideal_detalle.
    """
    nombre = str(data.get("nombre") or "").strip()
    if not nombre:
        raise ValueError("El nombre es obligatorio.")
    descripcion = _coerce_null(data.get("descripcion"))
    detalle = data.get("detalle")
    # Aceptar también 'herramientas' como alias si viene del frontend
    if detalle is None and isinstance(data.get("herramientas"), list):
        detalle = data.get("herramientas")
    if not isinstance(detalle, list) or len(detalle) == 0:
        raise ValueError("detalle debe contener al menos un item.")
    # Coerción y validación previa (sin DB) para detectar duplicados y cantidad
    seen_codigos: set[str] = set()
    # Validación preliminar de estructura
    for i, item in enumerate(detalle):
        if not isinstance(item, dict):
            raise ValueError(f"detalle[{i}]: formato inválido, se esperaba objeto.")
        raw_codigo = item.get("herramienta_codigo") or item.get("codigo") or item.get("herramientaCodigo")
        if not raw_codigo or not str(raw_codigo).strip():
            raise ValueError(f"detalle[{i}]: herramienta_codigo es obligatorio.")
        codigo_norm = _normalizar_codigo(str(raw_codigo))
        if codigo_norm in seen_codigos:
            raise ValueError("Herramienta ya asignada a esta Caja Ideal: codigo duplicado en el payload")
        seen_codigos.add(codigo_norm)
        # cantidad_minima puede venir como cantidad_minima o cantidad
        raw_cant = item.get("cantidad_minima")
        if raw_cant is None:
            raw_cant = item.get("cantidad")
        try:
            cant = int(raw_cant)
        except Exception:
            raise ValueError(f"detalle[{i}]: cantidad_minima debe ser entero > 0.")
        if cant <= 0:
            raise ValueError(f"detalle[{i}]: cantidad_minima debe ser > 0.")
    # Transacción DB
    conn = get_connection()
    ideal_id: int | None = None
    try:
        with conn.cursor() as cur:
            cur.execute("BEGIN")
            # Resolver herramienta_id y validar existencia dentro de la transacción
            resolved: list[dict[str, Any]] = []
            seen_for_fk: set[str] = set()
            for i, item in enumerate(detalle):
                raw_codigo = item.get("herramienta_codigo") or item.get("codigo") or item.get("herramientaCodigo")
                codigo_norm = _normalizar_codigo(str(raw_codigo))
                # Ya validado duplicado arriba, pero re-chequear por seguridad post-BEGIN
                if codigo_norm in seen_for_fk:
                    conn.rollback()
                    raise ValueError("Herramienta ya asignada a esta Caja Ideal")
                seen_for_fk.add(codigo_norm)
                cur.execute("SELECT id FROM cajas_herramientas WHERE codigo = %s", (codigo_norm,))
                hr = cur.fetchone()
                if not hr:
                    conn.rollback()
                    raise ValueError(f"detalle[{i}]: herramienta_codigo '{codigo_norm}' no existe.")
                herramienta_id = hr["id"]
                raw_cant = item.get("cantidad_minima")
                if raw_cant is None:
                    raw_cant = item.get("cantidad")
                cantidad_minima = int(raw_cant)
                articulo_codigo = _coerce_null(item.get("articulo_codigo"))
                # Si articulo_codigo viene vacío, permitir NULL
                resolved.append({
                    "herramienta_id": herramienta_id,
                    "cantidad_minima": cantidad_minima,
                    "articulo_codigo": articulo_codigo,
                })
            # Singleton activa: desactivar previas
            cur.execute("UPDATE cajas_caja_ideal SET activa = 0 WHERE activa = 1")
            # Insertar cabecera versionada
            cur.execute(
                """
                INSERT INTO cajas_caja_ideal (nombre, descripcion, activa, vigente_desde, creado_por)
                VALUES (%s, %s, 1, NOW(), %s)
                """,
                (nombre, descripcion, creado_por),
            )
            ideal_id = cur.lastrowid
            # Batch insert detalle
            for r in resolved:
                cur.execute(
                    """
                    INSERT INTO cajas_caja_ideal_detalle (caja_ideal_id, herramienta_id, cantidad_minima, articulo_codigo)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (ideal_id, r["herramienta_id"], r["cantidad_minima"], r["articulo_codigo"]),
                )
            conn.commit()
        # Fuera de la transacción, obtener ideal completo
        if ideal_id is not None:
            fetched = obtener_ideal_detalle(ideal_id)
            if fetched:
                return fetched
            # Fallback a get_ideal_actual
            actual = get_ideal_actual()
            if actual:
                return actual
        # Si algo raro, retornar por id
        actual = get_ideal_actual()
        if actual:
            return actual
        raise ValueError("No se pudo crear la Caja Ideal.")
    except IntegrityError as e:
        try:
            conn.rollback()
        except Exception:
            pass
        msg = str(e).lower()
        if "uq_ideal_herramienta" in msg or "duplicate" in msg:
            raise ValueError("Herramienta ya asignada a esta Caja Ideal")
        raise ValueError(f"Violacion de unicidad: {e}")
    except ValueError:
        # Ya con mensaje apropiado, asegurar rollback si aún hay transacción
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    except DataError as e:
        try:
            conn.rollback()
        except Exception:
            pass
        raise ValueError(f"Error de datos: {e}")
    finally:
        try:
            if conn.open:
                conn.close()
        except Exception:
            pass


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


# --------------------------------------------------------------------------- #
# Tecnicos-Cards + Historial + KPIs (Slice 2)
# --------------------------------------------------------------------------- #
def _clamp_limit(limit: Any, default: int = 25) -> int:
    try:
        limit = int(limit)
    except Exception:
        limit = default
    if limit < 1:
        limit = 1
    if limit > 100:
        limit = 100
    return limit


def _clamp_offset(offset: Any) -> int:
    try:
        offset = int(offset)
    except Exception:
        offset = 0
    if offset < 0:
        offset = 0
    return offset


def _get_ideal_meta(cur) -> tuple[int | None, int]:
    """Return (ideal_id, ideal_count) for active ideal, 0 if none."""
    cur.execute("SELECT id FROM cajas_caja_ideal WHERE activa = 1 LIMIT 1")
    row = cur.fetchone()
    if not row:
        return None, 0
    ideal_id = row["id"]
    cur.execute("SELECT COUNT(*) c FROM cajas_caja_ideal_detalle WHERE caja_ideal_id = %s", (ideal_id,))
    cnt = cur.fetchone()["c"]
    return ideal_id, int(cnt or 0)


def _calc_faltantes_completitud(ideal_count: int, presente_count: int) -> tuple[float | None, float]:
    if ideal_count == 0:
        return None, 0.0
    falt = ((ideal_count - presente_count) / ideal_count * 100) if ideal_count else 0.0
    if falt < 0:
        falt = 0.0
    if falt > 100:
        falt = 100.0
    comp = 100.0 - falt
    return round(float(falt), 2), round(float(comp), 2)


def listar_tecnicos_cards(
    *,
    q: str = "",
    limit: int = 25,
    offset: int = 0,
) -> dict[str, Any]:
    """Lista paginada de técnicos con métricas vs Caja Ideal.

    Filtra personal WHERE tipo IN ('tecnico','supervisor','generico','panol') AND activo=1
    q filtra por UPPER(TRIM(nombre)) LIKE %q% OR legajo LIKE %q%.
    Para cada técnico, obtiene último inventario (periodo DESC) y computa
    presente_count, faltantes_pct, completitud_pct, limpieza_score.
    """
    limit = _clamp_limit(limit, default=25)
    offset = _clamp_offset(offset)
    q = str(q or "").strip()

    conditions = ["p.tipo IN ('tecnico','supervisor','generico','panol')", "p.activo = 1"]
    params: list[Any] = []
    if q:
        conditions.append("(UPPER(TRIM(p.nombre)) LIKE CONCAT('%%', UPPER(TRIM(%s)), '%%') OR UPPER(TRIM(IFNULL(p.legajo,''))) LIKE CONCAT('%%', UPPER(TRIM(%s)), '%%'))")
        params.extend([q, q])

    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) c FROM personal p{where}", params)
            total = int(cur.fetchone()["c"] or 0)
            if total == 0:
                return {"items": [], "total": 0}

            cur.execute(
                f"SELECT p.id AS tecnico_id, p.nombre AS tecnico_nombre, p.tipo AS tecnico_tipo, p.legajo "
                f"FROM personal p{where} ORDER BY p.nombre ASC LIMIT %s OFFSET %s",
                params + [limit, offset],
            )
            tecnicos = cur.fetchall()

            _, ideal_count = _get_ideal_meta(cur)

            # Batch fetch latest inventario per tecnico
            tecnico_ids = [t["tecnico_id"] for t in tecnicos]
            latest_map: dict[int, dict] = {}
            if tecnico_ids:
                fmt = ",".join(["%s"] * len(tecnico_ids))
                cur.execute(
                    f"""
                    SELECT inv.id, inv.tecnico_id, inv.caja_id, inv.periodo, inv.estado, cj.codigo AS caja_codigo
                    FROM cajas_inventarios inv
                    LEFT JOIN cajas_cajas cj ON inv.caja_id = cj.id
                    WHERE inv.tecnico_id IN ({fmt})
                    ORDER BY inv.tecnico_id ASC, inv.periodo DESC, inv.id DESC
                    """,
                    tecnico_ids,
                )
                for r in cur.fetchall():
                    tid = r["tecnico_id"]
                    if tid not in latest_map:
                        latest_map[tid] = r

                # Batch detalle counts for those latest
                inv_ids = [v["id"] for v in latest_map.values()]
                counts_map: dict[int, dict] = {}
                if inv_ids:
                    fmt2 = ",".join(["%s"] * len(inv_ids))
                    cur.execute(
                        f"""
                        SELECT inventario_id,
                               COUNT(*) AS total,
                               SUM(CASE WHEN presente = 1 THEN 1 ELSE 0 END) AS presente_count,
                               SUM(CASE WHEN estado = 'malo' THEN 1 ELSE 0 END) AS malos
                        FROM cajas_inventario_detalle
                        WHERE inventario_id IN ({fmt2})
                        GROUP BY inventario_id
                        """,
                        inv_ids,
                    )
                    for cr in cur.fetchall():
                        counts_map[int(cr["inventario_id"])] = cr

                # Ensure counts_map in scope for building items
            else:
                counts_map = {}

            items: list[dict[str, Any]] = []
            for t in tecnicos:
                tid = t["tecnico_id"]
                latest = latest_map.get(tid)
                if latest:
                    caja_id = latest["caja_id"]
                    caja_codigo = latest["caja_codigo"]
                    ultimo_periodo = str(latest["periodo"]) if latest["periodo"] else None
                    ultimo_estado = latest["estado"]
                    inv_id = int(latest["id"])
                    cnt = counts_map.get(inv_id, {})
                    total_det = int(cnt.get("total") or 0) if cnt else 0
                    presente = int(cnt.get("presente_count") or 0) if cnt else 0
                    malos = int(cnt.get("malos") or 0) if cnt else 0
                else:
                    caja_id = None
                    caja_codigo = None
                    ultimo_periodo = None
                    ultimo_estado = None
                    total_det = 0
                    presente = 0
                    malos = 0

                if ideal_count == 0:
                    faltantes_pct = None
                    completitud_pct = 0.0
                    # limpieza still computed if detalle exists
                    if total_det > 0:
                        limpieza_score = round((malos / total_det * 100), 2)
                    else:
                        limpieza_score = 0.0
                else:
                    if latest is None:
                        # 100% faltantes when no inventario but ideal exists
                        faltantes_pct, completitud_pct = 100.0, 0.0
                    else:
                        faltantes_pct, completitud_pct = _calc_faltantes_completitud(ideal_count, presente)
                    if total_det > 0:
                        limpieza_score = round((malos / total_det * 100), 2)
                    else:
                        limpieza_score = 0.0

                items.append({
                    "tecnico_id": tid,
                    "tecnico_nombre": t["tecnico_nombre"],
                    "tecnico_tipo": t["tecnico_tipo"],
                    "caja_id": caja_id,
                    "caja_codigo": caja_codigo,
                    "ultimo_periodo": ultimo_periodo,
                    "ultimo_estado": ultimo_estado,
                    "ideal_count": ideal_count,
                    "presente_count": presente if ideal_count else 0,
                    "faltantes_pct": faltantes_pct,
                    "completitud_pct": completitud_pct if ideal_count else 0.0,
                    "limpieza_score": float(limpieza_score),
                })

            return {"items": items, "total": total}
    finally:
        try:
            if conn.open:
                conn.close()
        except Exception:
            pass


def listar_inventarios_por_tecnico(
    tecnico_id: int,
    *,
    limit: int = 25,
    offset: int = 0,
    estado: str | None = None,
) -> dict[str, Any]:
    """Historial completo de inventarios para un técnico, ordenado periodo DESC."""
    limit = _clamp_limit(limit, default=25)
    offset = _clamp_offset(offset)
    if estado is not None and estado not in ("borrador", "cerrado"):
        raise ValueError("estado debe ser 'borrador' o 'cerrado'.")

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            conditions = ["inv.tecnico_id = %s"]
            params: list[Any] = [tecnico_id]
            if estado:
                conditions.append("inv.estado = %s")
                params.append(estado)
            where = " WHERE " + " AND ".join(conditions)

            cur.execute(f"SELECT COUNT(*) c FROM cajas_inventarios inv{where}", params)
            total = int(cur.fetchone()["c"] or 0)

            cur.execute(
                f"""
                SELECT inv.*, cj.codigo AS caja_codigo,
                       p_tec.nombre AS tecnico_nombre, p_sup.nombre AS supervisor_nombre
                FROM cajas_inventarios inv
                LEFT JOIN cajas_cajas cj ON inv.caja_id = cj.id
                LEFT JOIN personal p_tec ON inv.tecnico_id = p_tec.id
                LEFT JOIN personal p_sup ON inv.supervisor_id = p_sup.id
                {where} ORDER BY inv.periodo DESC, inv.id DESC LIMIT %s OFFSET %s
                """,
                params + [limit, offset],
            )
            rows = cur.fetchall()

            inv_ids = [int(r["id"]) for r in rows]
            detalle_map: dict[int, list[dict[str, Any]]] = {iid: [] for iid in inv_ids}
            if inv_ids:
                fmt = ",".join(["%s"] * len(inv_ids))
                cur.execute(
                    f"""
                    SELECT d.inventario_id, d.id, d.herramienta_id, d.nro_item, d.cantidad, d.estado, d.presente, d.observaciones,
                           h.codigo AS herramienta_codigo
                    FROM cajas_inventario_detalle d
                    LEFT JOIN cajas_herramientas h ON h.id = d.herramienta_id
                    WHERE d.inventario_id IN ({fmt})
                    ORDER BY d.inventario_id ASC, d.nro_item ASC, d.id ASC
                    """,
                    inv_ids,
                )
                for dr in cur.fetchall():
                    iid = int(dr["inventario_id"])
                    # cantidad may be Decimal
                    raw_cant = dr["cantidad"]
                    try:
                        # handle Decimal
                        if raw_cant is not None:
                            # convert to int if whole, else float
                            fval = float(raw_cant)
                            cant = int(fval) if fval.is_integer() else fval
                        else:
                            cant = None
                    except Exception:
                        cant = raw_cant
                    detalle_map.setdefault(iid, []).append({
                        "id": dr["id"],
                        "herramienta_id": dr["herramienta_id"],
                        "herramienta_codigo": dr["herramienta_codigo"] if dr["herramienta_codigo"] else str(dr["herramienta_id"]),
                        "nro_item": dr["nro_item"],
                        "cantidad": cant,
                        "estado": dr["estado"],
                        "presente": bool(dr["presente"]),
                        "observaciones": dr["observaciones"],
                    })

            items: list[dict[str, Any]] = []
            for r in rows:
                iid = int(r["id"])
                items.append({
                    "id": iid,
                    "caja_id": r["caja_id"],
                    "caja_codigo": r.get("caja_codigo"),
                    "fecha": str(r["fecha"]) if r.get("fecha") else None,
                    "periodo": str(r["periodo"]) if r.get("periodo") else None,
                    "tecnico_id": r["tecnico_id"],
                    "tecnico_nombre": r.get("tecnico_nombre"),
                    "supervisor_id": r.get("supervisor_id"),
                    "supervisor_nombre": r.get("supervisor_nombre"),
                    "area": r.get("area"),
                    "estado": r.get("estado"),
                    "obs": r.get("obs") or r.get("obs_generales"),
                    "obs_generales": r.get("obs_generales"),
                    "detalle": detalle_map.get(iid, []),
                })

            return {"items": items, "total": total}
    finally:
        try:
            if conn.open:
                conn.close()
        except Exception:
            pass


def get_kpis_resumen(
    *,
    q: str = "",
    limit: int | None = None,
    offset: int = 0,
) -> dict[str, Any]:
    """KPIs agregados globales y por técnico (computed-on-read).

    Calcula para cada técnico su último inventario vs ideal activo.
    Agrega AVG faltantes, distribución, etc.
    """
    q = str(q or "").strip()
    # build tecnico filter same as cards
    conditions = ["p.tipo IN ('tecnico','supervisor','generico','panol')", "p.activo = 1"]
    params: list[Any] = []
    if q:
        conditions.append("(UPPER(TRIM(p.nombre)) LIKE CONCAT('%%', UPPER(TRIM(%s)), '%%') OR UPPER(TRIM(IFNULL(p.legajo,''))) LIKE CONCAT('%%', UPPER(TRIM(%s)), '%%'))")
        params.extend([q, q])
    where = " WHERE " + " AND ".join(conditions) if conditions else ""

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            _, ideal_count = _get_ideal_meta(cur)

            cur.execute(f"SELECT p.id AS tecnico_id, p.nombre AS tecnico_nombre, p.tipo AS tecnico_tipo FROM personal p{where} ORDER BY p.nombre ASC", params)
            tecnicos = cur.fetchall()
            total_tecnicos = len(tecnicos)

            if ideal_count == 0:
                # No ideal -> return hint structure
                # Still need to provide distribution empty, averages 0
                return {
                    "ideal_count": 0,
                    "total_tecnicos": total_tecnicos,
                    "tecnicos_con_inventario": 0,
                    "tecnicos_sin_inventario": total_tecnicos,
                    "avg_faltantes_pct": 0.0,
                    "avg_completitud_pct": 0.0,
                    "avg_limpieza_score": 0.0,
                    "promedio_faltantes_pct": 0.0,
                    "promedio_completitud_pct": 0.0,
                    "distribucion_faltantes": {"0-25": 0, "25-50": 0, "50-75": 0, "75-100": 0},
                    "tecnicos": [],
                    "global": {
                        "ideal_count": 0,
                        "total_tecnicos": total_tecnicos,
                        "tecnicos_con_inventario": 0,
                        "tecnicos_sin_inventario": total_tecnicos,
                        "promedio_faltantes_pct": 0.0,
                        "promedio_completitud_pct": 0.0,
                        "avg_faltantes_pct": 0.0,
                        "avg_completitud_pct": 0.0,
                        "avg_limpieza_score": 0.0,
                    },
                    "total": total_tecnicos,
                    "mensaje": "No hay Caja Ideal definida — define una para calcular KPIs",
                    "hint": "No hay Caja Ideal definida — define una para calcular KPIs",
                }

            # Batch latest per tecnico
            tecnico_ids = [t["tecnico_id"] for t in tecnicos]
            latest_map: dict[int, dict] = {}
            counts_map: dict[int, dict] = {}
            if tecnico_ids:
                fmt = ",".join(["%s"] * len(tecnico_ids))
                cur.execute(
                    f"""
                    SELECT inv.id, inv.tecnico_id, inv.caja_id, inv.periodo, inv.estado, cj.codigo AS caja_codigo
                    FROM cajas_inventarios inv
                    LEFT JOIN cajas_cajas cj ON inv.caja_id = cj.id
                    WHERE inv.tecnico_id IN ({fmt})
                    ORDER BY inv.tecnico_id ASC, inv.periodo DESC, inv.id DESC
                    """,
                    tecnico_ids,
                )
                for r in cur.fetchall():
                    tid = r["tecnico_id"]
                    if tid not in latest_map:
                        latest_map[tid] = r
                inv_ids = [int(v["id"]) for v in latest_map.values()]
                if inv_ids:
                    fmt2 = ",".join(["%s"] * len(inv_ids))
                    cur.execute(
                        f"""
                        SELECT inventario_id,
                               COUNT(*) AS total,
                               SUM(CASE WHEN presente = 1 THEN 1 ELSE 0 END) AS presente_count,
                               SUM(CASE WHEN estado = 'malo' THEN 1 ELSE 0 END) AS malos
                        FROM cajas_inventario_detalle
                        WHERE inventario_id IN ({fmt2})
                        GROUP BY inventario_id
                        """,
                        inv_ids,
                    )
                    for cr in cur.fetchall():
                        counts_map[int(cr["inventario_id"])] = cr

            per_tecnico: list[dict[str, Any]] = []
            faltantes_vals: list[float] = []
            completitud_vals: list[float] = []
            limpieza_vals: list[float] = []
            distrib = {"0-25": 0, "25-50": 0, "50-75": 0, "75-100": 0}
            con_inventario = 0

            for t in tecnicos:
                tid = t["tecnico_id"]
                latest = latest_map.get(tid)
                if latest:
                    inv_id = int(latest["id"])
                    cnt = counts_map.get(inv_id, {})
                    total_det = int(cnt.get("total") or 0) if cnt else 0
                    presente = int(cnt.get("presente_count") or 0) if cnt else 0
                    malos = int(cnt.get("malos") or 0) if cnt else 0
                    falt, comp = _calc_faltantes_completitud(ideal_count, presente)
                    # falt cannot be None here because ideal_count >0
                    assert falt is not None
                    limpieza = round((malos / total_det * 100), 2) if total_det else 0.0
                    con_inventario += 1
                    faltantes_vals.append(float(falt))
                    completitud_vals.append(float(comp))
                    limpieza_vals.append(float(limpieza))
                    # distribution
                    if falt <= 25:
                        distrib["0-25"] += 1
                    elif falt <= 50:
                        distrib["25-50"] += 1
                    elif falt <= 75:
                        distrib["50-75"] += 1
                    else:
                        distrib["75-100"] += 1
                    ultimo_periodo = str(latest["periodo"]) if latest["periodo"] else None
                    ultimo_estado = latest["estado"]
                    caja_codigo = latest.get("caja_codigo")
                else:
                    # sin inventario -> 100% faltantes
                    falt, comp = 100.0, 0.0
                    limpieza = 0.0
                    faltantes_vals.append(float(falt))
                    completitud_vals.append(float(comp))
                    # limpieza not counted for sin inventario? but we may not count
                    # For distribution, count sin inventario as 75-100 bucket
                    distrib["75-100"] += 1
                    ultimo_periodo = None
                    ultimo_estado = None
                    caja_codigo = None
                    presente = 0
                    total_det = 0
                    malos = 0

                per_tecnico.append({
                    "tecnico_id": tid,
                    "tecnico_nombre": t["tecnico_nombre"],
                    "tecnico_tipo": t["tecnico_tipo"],
                    "caja_codigo": caja_codigo,
                    "ultimo_periodo": ultimo_periodo,
                    "ultimo_estado": ultimo_estado,
                    "ideal_count": ideal_count,
                    "presente_count": presente if latest else 0,
                    "faltantes_pct": falt,
                    "completitud_pct": comp,
                    "limpieza_score": float(limpieza),
                })

            # Apply limit/offset pagination to per_tecnico list if requested
            if limit is not None:
                lim = _clamp_limit(limit, default=25)
                off = _clamp_offset(offset)
                paginated = per_tecnico[off: off + lim]
            else:
                paginated = per_tecnico
                lim = len(per_tecnico)
                off = 0

            avg_falt = round(sum(faltantes_vals) / len(faltantes_vals), 2) if faltantes_vals else 0.0
            avg_comp = round(sum(completitud_vals) / len(completitud_vals), 2) if completitud_vals else 0.0
            # avg limpieza only over con_inventario (where we have detalle)
            # If sin inventario they have 0 limpieza, but we filtered earlier limpieza_vals only for con_inventario
            # So use limpieza_vals collected only for con_inventario
            # For sin inventario we didn't push limpieza_vals, so avg is over con_inventario only
            # If no con_inventario, avg 0
            avg_limp = round(sum(limpieza_vals) / len(limpieza_vals), 2) if limpieza_vals else 0.0
            sin_inventario = total_tecnicos - con_inventario

            return {
                "ideal_count": ideal_count,
                "total_tecnicos": total_tecnicos,
                "tecnicos_con_inventario": con_inventario,
                "tecnicos_sin_inventario": sin_inventario,
                "avg_faltantes_pct": avg_falt,
                "avg_completitud_pct": avg_comp,
                "avg_limpieza_score": avg_limp,
                "promedio_faltantes_pct": avg_falt,
                "promedio_completitud_pct": avg_comp,
                "distribucion_faltantes": distrib,
                "distribucion": distrib,
                "tecnicos": paginated,
                "items": paginated,
                "total": total_tecnicos,
                "global": {
                    "ideal_count": ideal_count,
                    "total_tecnicos": total_tecnicos,
                    "tecnicos_con_inventario": con_inventario,
                    "tecnicos_sin_inventario": sin_inventario,
                    "promedio_faltantes_pct": avg_falt,
                    "promedio_completitud_pct": avg_comp,
                    "avg_faltantes_pct": avg_falt,
                    "avg_completitud_pct": avg_comp,
                    "avg_limpieza_score": avg_limp,
                    "distribucion_faltantes": distrib,
                },
                "mensaje": None,
                "hint": None,
            }
    finally:
        try:
            if conn.open:
                conn.close()
        except Exception:
            pass


def get_kpis_por_tecnico(tecnico_id: int, historial_limit: int = 12) -> dict[str, Any] | None:
    """KPIs por técnico individual, con historial de faltantes por periodo."""
    # Validate bounds
    try:
        historial_limit = int(historial_limit)
    except Exception:
        historial_limit = 12
    if historial_limit < 1:
        historial_limit = 1
    if historial_limit > 100:
        historial_limit = 100

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Fetch tecnico info
            cur.execute("SELECT id, nombre, tipo, legajo FROM personal WHERE id = %s", (tecnico_id,))
            tec = cur.fetchone()
            if not tec:
                return None

            _, ideal_count = _get_ideal_meta(cur)

            if ideal_count == 0:
                return {
                    "tecnico_id": tec["id"],
                    "tecnico_nombre": tec["nombre"],
                    "tecnico_tipo": tec["tipo"],
                    "ideal_count": 0,
                    "presente_count": 0,
                    "faltantes_pct": 0.0,
                    "completitud_pct": 0.0,
                    "limpieza_score": 0.0,
                    "ultimo_periodo": None,
                    "ultimo_estado": None,
                    "historial": [],
                    "total_inventarios": 0,
                    "mensaje": "No hay Caja Ideal definida — define una para calcular KPIs",
                    "hint": "No hay Caja Ideal definida — define una para calcular KPIs",
                }

            # Fetch all inventarios for tecnico ordered DESC, limit historial_limit for trend but also total count
            cur.execute("SELECT COUNT(*) c FROM cajas_inventarios WHERE tecnico_id = %s", (tecnico_id,))
            total_inv = int(cur.fetchone()["c"] or 0)

            cur.execute(
                """
                SELECT inv.*, cj.codigo AS caja_codigo
                FROM cajas_inventarios inv
                LEFT JOIN cajas_cajas cj ON inv.caja_id = cj.id
                WHERE inv.tecnico_id = %s
                ORDER BY inv.periodo DESC, inv.id DESC
                LIMIT %s
                """,
                (tecnico_id, historial_limit),
            )
            inv_rows = cur.fetchall()

            # Batch detalle counts for these invs
            inv_ids = [int(r["id"]) for r in inv_rows]
            counts_map: dict[int, dict] = {}
            if inv_ids:
                fmt = ",".join(["%s"] * len(inv_ids))
                cur.execute(
                    f"""
                    SELECT inventario_id,
                           COUNT(*) AS total,
                           SUM(CASE WHEN presente = 1 THEN 1 ELSE 0 END) AS presente_count,
                           SUM(CASE WHEN estado = 'malo' THEN 1 ELSE 0 END) AS malos
                    FROM cajas_inventario_detalle
                    WHERE inventario_id IN ({fmt})
                    GROUP BY inventario_id
                    """,
                    inv_ids,
                )
                for cr in cur.fetchall():
                    counts_map[int(cr["inventario_id"])] = cr

            historial: list[dict[str, Any]] = []
            latest_falt = None
            latest_comp = None
            latest_limp = None
            latest_presente = 0
            latest_periodo = None
            latest_estado = None

            for idx, r in enumerate(inv_rows):
                iid = int(r["id"])
                cnt = counts_map.get(iid, {})
                total_det = int(cnt.get("total") or 0) if cnt else 0
                presente = int(cnt.get("presente_count") or 0) if cnt else 0
                malos = int(cnt.get("malos") or 0) if cnt else 0
                falt, comp = _calc_faltantes_completitud(ideal_count, presente)
                assert falt is not None
                limpieza = round((malos / total_det * 100), 2) if total_det else 0.0
                entry = {
                    "inventario_id": iid,
                    "periodo": str(r["periodo"]) if r.get("periodo") else None,
                    "estado": r.get("estado"),
                    "caja_id": r.get("caja_id"),
                    "caja_codigo": r.get("caja_codigo"),
                    "presente_count": presente,
                    "total_detalle": total_det,
                    "faltantes_pct": falt,
                    "completitud_pct": comp,
                    "limpieza_score": float(limpieza),
                    "mal_count": malos,
                    "malos": malos,
                }
                historial.append(entry)
                if idx == 0:
                    latest_falt = falt
                    latest_comp = comp
                    latest_limp = limpieza
                    latest_presente = presente
                    latest_periodo = entry["periodo"]
                    latest_estado = entry["estado"]

            if not inv_rows:
                # Sin inventarios -> 100% faltantes per spec
                latest_falt, latest_comp = 100.0, 0.0
                latest_limp = 0.0
                latest_presente = 0

            return {
                "tecnico_id": tec["id"],
                "tecnico_nombre": tec["nombre"],
                "tecnico_tipo": tec["tipo"],
                "ideal_count": ideal_count,
                "presente_count": latest_presente,
                "faltantes_pct": latest_falt,
                "completitud_pct": latest_comp,
                "limpieza_score": float(latest_limp) if latest_limp is not None else 0.0,
                "ultimo_periodo": latest_periodo,
                "ultimo_estado": latest_estado,
                "historial": historial,
                "historial_faltantes": historial,
                "total_inventarios": total_inv,
                "total": total_inv,
                "mensaje": None,
                "hint": None,
            }
    finally:
        try:
            if conn.open:
                conn.close()
        except Exception:
            pass


# --------------------------------------------------------------------------- #
# Limpieza Historial + Asignaciones (Fase 2)
# --------------------------------------------------------------------------- #

# Tipos permitidos para tecnico_id / responsable_id — reutiliza personal.tipo
# personal ENUM: tecnico, supervisor, produccion, generico, panol
# Para cajas solo se permiten tecnico/supervisor/generico/panol (excluye produccion)
TIPOS_PERSONAL_PERMITIDOS = ("tecnico", "supervisor", "generico", "panol")
ESTADOS_LIMPIEZA = ("pendiente", "realizada", "vencida")


def _validar_personal_existe(cur, personal_id: int, campo: str = "tecnico_id") -> dict[str, Any]:
    """Valida que personal_id exista y tenga tipo permitido. Retorna row o lanza ValueError."""
    try:
        pid = int(personal_id)
    except Exception:
        raise ValueError(f"{campo} debe ser un entero válido.")
    cur.execute("SELECT id, nombre, tipo FROM personal WHERE id = %s", (pid,))
    row = cur.fetchone()
    if not row:
        raise ValueError(f"{campo} {pid} no existe.")
    if row["tipo"] not in TIPOS_PERSONAL_PERMITIDOS:
        raise ValueError(f"{campo} {pid}: tipo '{row['tipo']}' no permitido. Debe ser tecnico/supervisor/generico/panol.")
    return row


def _validar_caja_existe(cur, caja_id: int) -> dict[str, Any]:
    """Valida que caja_id exista en cajas_cajas."""
    try:
        cid = int(caja_id)
    except Exception:
        raise ValueError("caja_id debe ser un entero válido.")
    cur.execute("SELECT id, codigo FROM cajas_cajas WHERE id = %s", (cid,))
    row = cur.fetchone()
    if not row:
        raise ValueError(f"caja_id {cid} no existe.")
    return row


def _parse_fecha_limpieza(val: Any) -> str | None:
    """Parsea fecha para limpieza. Acepta YYYY-MM-DD o YYYY-MM-DD HH:MM:SS. Retorna string normalizado o None si val es None."""
    if val is None or (isinstance(val, str) and val.strip() == ""):
        return None
    s = str(val).strip()
    # Intentar datetime con hora
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            from datetime import datetime
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            continue
    raise ValueError(f"fecha '{s}' formato inválido. Use YYYY-MM-DD o YYYY-MM-DD HH:MM:SS.")


def _parse_desde(val: Any) -> str:
    """Parsea desde (DATE) para asignaciones. Requerido, formato YYYY-MM-DD."""
    if val is None or (isinstance(val, str) and val.strip() == ""):
        raise ValueError("desde es obligatorio (YYYY-MM-DD).")
    s = str(val).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            from datetime import datetime
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            continue
    raise ValueError(f"desde '{s}' formato inválido. Use YYYY-MM-DD.")


# -- Limpieza Historial CRUD -- #

def listar_limpieza(
    *,
    caja_id: int | None = None,
    tecnico_id: int | None = None,
    estado: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Lista paginada de eventos de limpieza con filtros opcionales."""
    limit = _clamp_limit(limit, default=50)
    offset = _clamp_offset(offset)
    if estado is not None and str(estado).strip() != "":
        estado = str(estado).strip().lower()
        if estado not in ESTADOS_LIMPIEZA:
            raise ValueError(f"estado debe ser uno de {ESTADOS_LIMPIEZA}.")
    else:
        estado = None
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            conditions = []
            params: list[Any] = []
            if caja_id is not None:
                try:
                    caja_id = int(caja_id)
                except Exception:
                    raise ValueError("caja_id debe ser entero.")
                conditions.append("l.caja_id = %s")
                params.append(caja_id)
            if tecnico_id is not None:
                try:
                    tecnico_id = int(tecnico_id)
                except Exception:
                    raise ValueError("tecnico_id debe ser entero.")
                conditions.append("l.tecnico_id = %s")
                params.append(tecnico_id)
            if estado:
                conditions.append("l.estado = %s")
                params.append(estado)
            where = " WHERE " + " AND ".join(conditions) if conditions else ""
            cur.execute(f"SELECT COUNT(*) c FROM cajas_limpieza_historial l{where}", params)
            total = int(cur.fetchone()["c"] or 0)
            cur.execute(
                f"""
                SELECT l.*, cj.codigo AS caja_codigo, p.nombre AS tecnico_nombre
                FROM cajas_limpieza_historial l
                LEFT JOIN cajas_cajas cj ON l.caja_id = cj.id
                LEFT JOIN personal p ON l.tecnico_id = p.id
                {where}
                ORDER BY l.fecha DESC, l.id DESC
                LIMIT %s OFFSET %s
                """,
                params + [limit, offset],
            )
            rows = cur.fetchall()
        items = []
        for r in rows:
            items.append({
                "id": r["id"],
                "caja_id": r["caja_id"],
                "caja_codigo": r.get("caja_codigo"),
                "tecnico_id": r["tecnico_id"],
                "tecnico_nombre": r.get("tecnico_nombre"),
                "fecha": str(r["fecha"]) if r.get("fecha") else None,
                "estado": r["estado"],
                "responsable_id": r.get("responsable_id"),
                "observaciones": r.get("observaciones"),
                "creado_en": str(r["creado_en"]) if r.get("creado_en") else None,
            })
        return {"items": items, "total": total}
    finally:
        try:
            if conn.open:
                conn.close()
        except Exception:
            pass


def crear_limpieza(data: dict[str, Any]) -> dict[str, Any]:
    """Crea un evento de limpieza. Valida FKs y estado."""
    caja_id = data.get("caja_id")
    if caja_id is None or (isinstance(caja_id, str) and str(caja_id).strip() == ""):
        raise ValueError("caja_id es obligatorio.")
    tecnico_id = data.get("tecnico_id")
    if tecnico_id is None or (isinstance(tecnico_id, str) and str(tecnico_id).strip() == ""):
        raise ValueError("tecnico_id es obligatorio.")
    estado = str(data.get("estado") or "pendiente").strip().lower()
    if estado not in ESTADOS_LIMPIEZA:
        raise ValueError(f"estado debe ser uno de {ESTADOS_LIMPIEZA}.")
    observaciones = _coerce_null(data.get("observaciones"))
    responsable_id = data.get("responsable_id")
    if responsable_id is not None and str(responsable_id).strip() != "":
        try:
            responsable_id = int(responsable_id)
        except Exception:
            raise ValueError("responsable_id debe ser entero.")
    else:
        responsable_id = None
    fecha_raw = data.get("fecha")
    fecha_val = _parse_fecha_limpieza(fecha_raw) if fecha_raw is not None else None

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Validar FKs
            _validar_caja_existe(cur, int(caja_id))
            _validar_personal_existe(cur, int(tecnico_id), campo="tecnico_id")
            if responsable_id is not None:
                _validar_personal_existe(cur, int(responsable_id), campo="responsable_id")
            # Insertar
            if fecha_val is not None:
                cur.execute(
                    """
                    INSERT INTO cajas_limpieza_historial (caja_id, tecnico_id, fecha, estado, responsable_id, observaciones)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (int(caja_id), int(tecnico_id), fecha_val, estado, responsable_id, observaciones),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO cajas_limpieza_historial (caja_id, tecnico_id, estado, responsable_id, observaciones)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (int(caja_id), int(tecnico_id), estado, responsable_id, observaciones),
                )
            conn.commit()
            new_id = cur.lastrowid
            cur.execute(
                """
                SELECT l.*, cj.codigo AS caja_codigo, p.nombre AS tecnico_nombre
                FROM cajas_limpieza_historial l
                LEFT JOIN cajas_cajas cj ON l.caja_id = cj.id
                LEFT JOIN personal p ON l.tecnico_id = p.id
                WHERE l.id = %s
                """,
                (new_id,),
            )
            row = cur.fetchone()
            if not row:
                raise ValueError("No se pudo crear el evento de limpieza.")
            return {
                "id": row["id"],
                "caja_id": row["caja_id"],
                "caja_codigo": row.get("caja_codigo"),
                "tecnico_id": row["tecnico_id"],
                "tecnico_nombre": row.get("tecnico_nombre"),
                "fecha": str(row["fecha"]) if row.get("fecha") else None,
                "estado": row["estado"],
                "responsable_id": row.get("responsable_id"),
                "observaciones": row.get("observaciones"),
                "creado_en": str(row["creado_en"]) if row.get("creado_en") else None,
            }
    except IntegrityError as e:
        try:
            conn.rollback()
        except Exception:
            pass
        raise ValueError(f"Violación de integridad (FK): {e}")
    except ValueError:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            if conn.open:
                conn.close()
        except Exception:
            pass


def actualizar_limpieza_estado(limpieza_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
    """Actualiza estado y/o observaciones de un evento de limpieza.

    Solo permite transición pendiente -> realizada/vencida. Si estado actual no es pendiente y se intenta cambiar, 409.
    Retorna None si no existe.
    """
    try:
        limpieza_id = int(limpieza_id)
    except Exception:
        raise ValueError("id debe ser entero.")
    nuevo_estado = data.get("estado")
    if nuevo_estado is not None:
        nuevo_estado = str(nuevo_estado).strip().lower()
        if nuevo_estado not in ESTADOS_LIMPIEZA:
            raise ValueError(f"estado debe ser uno de {ESTADOS_LIMPIEZA}.")
    observaciones = data.get("observaciones") if "observaciones" in data else None
    if observaciones is not None:
        observaciones = _coerce_null(observaciones)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM cajas_limpieza_historial WHERE id = %s", (limpieza_id,))
            row = cur.fetchone()
            if not row:
                return None
            estado_actual = row["estado"]
            # Validar transición si se cambia estado
            if nuevo_estado is not None and nuevo_estado != estado_actual:
                if estado_actual != "pendiente":
                    raise ValueError("Solo se puede cambiar el estado de un evento pendiente.")
                if nuevo_estado not in ("realizada", "vencida"):
                    raise ValueError("Transición inválida: pendiente solo puede pasar a realizada o vencida.")
                # válido: pendiente -> realizada/vencida
            updates = []
            params: list[Any] = []
            if nuevo_estado is not None and nuevo_estado != estado_actual:
                updates.append("estado = %s")
                params.append(nuevo_estado)
            if "observaciones" in data:
                updates.append("observaciones = %s")
                params.append(observaciones)
            if not updates:
                # Sin cambios, retornar actual
                return {
                    "id": row["id"],
                    "caja_id": row["caja_id"],
                    "tecnico_id": row["tecnico_id"],
                    "fecha": str(row["fecha"]) if row.get("fecha") else None,
                    "estado": row["estado"],
                    "responsable_id": row.get("responsable_id"),
                    "observaciones": row.get("observaciones"),
                    "creado_en": str(row["creado_en"]) if row.get("creado_en") else None,
                }
            params.append(limpieza_id)
            set_clause = ", ".join(updates)
            cur.execute(f"UPDATE cajas_limpieza_historial SET {set_clause} WHERE id = %s", params)
            conn.commit()
            cur.execute("SELECT * FROM cajas_limpieza_historial WHERE id = %s", (limpieza_id,))
            updated = cur.fetchone()
            return {
                "id": updated["id"],
                "caja_id": updated["caja_id"],
                "tecnico_id": updated["tecnico_id"],
                "fecha": str(updated["fecha"]) if updated.get("fecha") else None,
                "estado": updated["estado"],
                "responsable_id": updated.get("responsable_id"),
                "observaciones": updated.get("observaciones"),
                "creado_en": str(updated["creado_en"]) if updated.get("creado_en") else None,
            }
    except IntegrityError as e:
        try:
            conn.rollback()
        except Exception:
            pass
        raise ValueError(f"Violación de integridad: {e}")
    finally:
        try:
            if conn.open:
                conn.close()
        except Exception:
            pass


def eliminar_limpieza(limpieza_id: int) -> dict[str, Any] | None:
    """Elimina un evento de limpieza solo si estado = pendiente. Retorna None si no existe, lanza ValueError 409 si no es pendiente."""
    try:
        limpieza_id = int(limpieza_id)
    except Exception:
        raise ValueError("id debe ser entero.")
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT estado FROM cajas_limpieza_historial WHERE id = %s", (limpieza_id,))
            row = cur.fetchone()
            if not row:
                return None
            if row["estado"] != "pendiente":
                raise ValueError("No se puede eliminar un evento de limpieza que no está en estado pendiente")
            cur.execute("DELETE FROM cajas_limpieza_historial WHERE id = %s", (limpieza_id,))
            conn.commit()
            return {"id": limpieza_id, "eliminado": True}
    except IntegrityError as e:
        try:
            conn.rollback()
        except Exception:
            pass
        raise ValueError(f"No se puede eliminar: restricción FK - {e}")
    finally:
        try:
            if conn.open:
                conn.close()
        except Exception:
            pass


def obtener_limpieza(limpieza_id: int) -> dict[str, Any] | None:
    """Obtiene un evento de limpieza por id."""
    try:
        limpieza_id = int(limpieza_id)
    except Exception:
        raise ValueError("id debe ser entero.")
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT l.*, cj.codigo AS caja_codigo, p.nombre AS tecnico_nombre
                FROM cajas_limpieza_historial l
                LEFT JOIN cajas_cajas cj ON l.caja_id = cj.id
                LEFT JOIN personal p ON l.tecnico_id = p.id
                WHERE l.id = %s
                """,
                (limpieza_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "id": row["id"],
                "caja_id": row["caja_id"],
                "caja_codigo": row.get("caja_codigo"),
                "tecnico_id": row["tecnico_id"],
                "tecnico_nombre": row.get("tecnico_nombre"),
                "fecha": str(row["fecha"]) if row.get("fecha") else None,
                "estado": row["estado"],
                "responsable_id": row.get("responsable_id"),
                "observaciones": row.get("observaciones"),
                "creado_en": str(row["creado_en"]) if row.get("creado_en") else None,
            }
    finally:
        try:
            if conn.open:
                conn.close()
        except Exception:
            pass


# -- Asignaciones CRUD -- #

def listar_asignaciones(
    *,
    caja_id: int | None = None,
    tecnico_id: int | None = None,
    activa: int | bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Lista paginada de asignaciones con filtros opcionales."""
    limit = _clamp_limit(limit, default=50)
    offset = _clamp_offset(offset)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            conditions = []
            params: list[Any] = []
            if caja_id is not None:
                try:
                    caja_id = int(caja_id)
                except Exception:
                    raise ValueError("caja_id debe ser entero.")
                conditions.append("a.caja_id = %s")
                params.append(caja_id)
            if tecnico_id is not None:
                try:
                    tecnico_id = int(tecnico_id)
                except Exception:
                    raise ValueError("tecnico_id debe ser entero.")
                conditions.append("a.tecnico_id = %s")
                params.append(tecnico_id)
            if activa is not None:
                # Normalizar bool/string/int a 0/1
                if isinstance(activa, str):
                    activa_norm = activa.strip().lower()
                    if activa_norm in ("1", "true", "si", "sí"):
                        activa_int = 1
                    elif activa_norm in ("0", "false", "no"):
                        activa_int = 0
                    else:
                        try:
                            activa_int = int(activa_norm)
                        except Exception:
                            raise ValueError("activa debe ser 0/1 o true/false.")
                else:
                    activa_int = 1 if bool(activa) else 0 if str(activa).strip() != "" else None
                    # Handle int directly
                    try:
                        activa_int = int(activa)
                        activa_int = 1 if activa_int else 0
                    except Exception:
                        activa_int = 1 if activa else 0
                conditions.append("a.activa = %s")
                params.append(activa_int)
            where = " WHERE " + " AND ".join(conditions) if conditions else ""
            cur.execute(f"SELECT COUNT(*) c FROM cajas_asignaciones a{where}", params)
            total = int(cur.fetchone()["c"] or 0)
            cur.execute(
                f"""
                SELECT a.*, cj.codigo AS caja_codigo, p.nombre AS tecnico_nombre
                FROM cajas_asignaciones a
                LEFT JOIN cajas_cajas cj ON a.caja_id = cj.id
                LEFT JOIN personal p ON a.tecnico_id = p.id
                {where}
                ORDER BY a.creado_en DESC, a.id DESC
                LIMIT %s OFFSET %s
                """,
                params + [limit, offset],
            )
            rows = cur.fetchall()
        items = []
        for r in rows:
            items.append({
                "id": r["id"],
                "caja_id": r["caja_id"],
                "caja_codigo": r.get("caja_codigo"),
                "tecnico_id": r["tecnico_id"],
                "tecnico_nombre": r.get("tecnico_nombre"),
                "desde": str(r["desde"]) if r.get("desde") else None,
                "hasta": str(r["hasta"]) if r.get("hasta") else None,
                "activa": bool(r["activa"]),
                "creado_en": str(r["creado_en"]) if r.get("creado_en") else None,
            })
        return {"items": items, "total": total}
    finally:
        try:
            if conn.open:
                conn.close()
        except Exception:
            pass


def crear_asignacion(data: dict[str, Any]) -> dict[str, Any]:
    """Crea una asignación versionada transaccionalmente.

    Transacción: si existe activa para caja_id, validar duplicado mismo tecnico -> 409, sino cerrar previa (activa=0,hasta=CURDATE()), luego INSERT nueva activa=1.
    Singleton activa por caja garantizado vía transacción.
    """
    caja_id = data.get("caja_id")
    tecnico_id = data.get("tecnico_id")
    desde_raw = data.get("desde")
    if caja_id is None or (isinstance(caja_id, str) and str(caja_id).strip() == ""):
        raise ValueError("caja_id es obligatorio.")
    if tecnico_id is None or (isinstance(tecnico_id, str) and str(tecnico_id).strip() == ""):
        raise ValueError("tecnico_id es obligatorio.")
    desde = _parse_desde(desde_raw)
    hasta_raw = data.get("hasta")
    hasta_val = None
    if hasta_raw is not None and str(hasta_raw).strip() != "":
        try:
            from datetime import datetime
            dt = datetime.strptime(str(hasta_raw).strip(), "%Y-%m-%d")
            hasta_val = dt.strftime("%Y-%m-%d")
        except Exception:
            raise ValueError(f"hasta '{hasta_raw}' formato inválido. Use YYYY-MM-DD.")
        # Validar hasta >= desde
        from datetime import datetime as _dt
        if _dt.strptime(hasta_val, "%Y-%m-%d") < _dt.strptime(desde, "%Y-%m-%d"):
            raise ValueError("hasta no puede ser anterior a desde.")
        # Si hasta no es NULL, activa debe ser 0
        activa = 0
    else:
        activa = 1
        hasta_val = None

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Validar FKs dentro de transacción
            cur.execute("BEGIN")
            _validar_caja_existe(cur, int(caja_id))
            _validar_personal_existe(cur, int(tecnico_id), campo="tecnico_id")
            # Verificar activa existente para esta caja
            cur.execute("SELECT id, tecnico_id FROM cajas_asignaciones WHERE caja_id = %s AND activa = 1 LIMIT 1", (int(caja_id),))
            existente = cur.fetchone()
            if existente:
                if int(existente["tecnico_id"]) == int(tecnico_id):
                    conn.rollback()
                    raise ValueError("Ya hay una asignación activa para esta caja y técnico")
                # Cerrar previa activa (diferente tecnico) — singleton por caja
                cur.execute("UPDATE cajas_asignaciones SET activa = 0, hasta = CURDATE() WHERE caja_id = %s AND activa = 1", (int(caja_id),))
            # Insertar nueva
            cur.execute(
                """
                INSERT INTO cajas_asignaciones (caja_id, tecnico_id, desde, hasta, activa)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (int(caja_id), int(tecnico_id), desde, hasta_val, activa),
            )
            new_id = cur.lastrowid
            conn.commit()
            cur.execute(
                """
                SELECT a.*, cj.codigo AS caja_codigo, p.nombre AS tecnico_nombre
                FROM cajas_asignaciones a
                LEFT JOIN cajas_cajas cj ON a.caja_id = cj.id
                LEFT JOIN personal p ON a.tecnico_id = p.id
                WHERE a.id = %s
                """,
                (new_id,),
            )
            row = cur.fetchone()
            if not row:
                raise ValueError("No se pudo crear la asignación.")
            return {
                "id": row["id"],
                "caja_id": row["caja_id"],
                "caja_codigo": row.get("caja_codigo"),
                "tecnico_id": row["tecnico_id"],
                "tecnico_nombre": row.get("tecnico_nombre"),
                "desde": str(row["desde"]) if row.get("desde") else None,
                "hasta": str(row["hasta"]) if row.get("hasta") else None,
                "activa": bool(row["activa"]),
                "creado_en": str(row["creado_en"]) if row.get("creado_en") else None,
            }
    except IntegrityError as e:
        try:
            conn.rollback()
        except Exception:
            pass
        msg = str(e).lower()
        if "duplicate" in msg or "uq_" in msg:
            raise ValueError("Ya hay una asignación activa para esta caja y técnico")
        raise ValueError(f"Violación de integridad: {e}")
    except ValueError:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    except DataError as e:
        try:
            conn.rollback()
        except Exception:
            pass
        raise ValueError(f"Error de datos: {e}")
    finally:
        try:
            if conn.open:
                conn.close()
        except Exception:
            pass


def cerrar_asignacion(asignacion_id: int) -> dict[str, Any] | None:
    """Cierra una asignación activa: set hasta=CURDATE(), activa=0. Retorna None si no existe, 409 si ya inactiva."""
    try:
        asignacion_id = int(asignacion_id)
    except Exception:
        raise ValueError("id debe ser entero.")
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM cajas_asignaciones WHERE id = %s", (asignacion_id,))
            row = cur.fetchone()
            if not row:
                return None
            if not bool(row["activa"]) or row["hasta"] is not None:
                # Ya cerrada — para idempotencia distinguir: si activa=0 ya está cerrada
                if not bool(row["activa"]):
                    raise ValueError("La asignación ya está cerrada")
                # activa=0 pero hasta NULL raro, igual considerar cerrada
            cur.execute("UPDATE cajas_asignaciones SET activa = 0, hasta = CURDATE() WHERE id = %s AND activa = 1", (asignacion_id,))
            # Si no afectó filas, ya estaba cerrada
            if cur.rowcount == 0:
                # Verificar si ya cerrada
                cur.execute("SELECT activa FROM cajas_asignaciones WHERE id = %s", (asignacion_id,))
                r2 = cur.fetchone()
                if r2 and not bool(r2["activa"]):
                    raise ValueError("La asignación ya está cerrada")
                # Si no, igualmente marcar
                cur.execute("UPDATE cajas_asignaciones SET hasta = CURDATE(), activa = 0 WHERE id = %s", (asignacion_id,))
            conn.commit()
            cur.execute(
                """
                SELECT a.*, cj.codigo AS caja_codigo, p.nombre AS tecnico_nombre
                FROM cajas_asignaciones a
                LEFT JOIN cajas_cajas cj ON a.caja_id = cj.id
                LEFT JOIN personal p ON a.tecnico_id = p.id
                WHERE a.id = %s
                """,
                (asignacion_id,),
            )
            updated = cur.fetchone()
            return {
                "id": updated["id"],
                "caja_id": updated["caja_id"],
                "caja_codigo": updated.get("caja_codigo"),
                "tecnico_id": updated["tecnico_id"],
                "tecnico_nombre": updated.get("tecnico_nombre"),
                "desde": str(updated["desde"]) if updated.get("desde") else None,
                "hasta": str(updated["hasta"]) if updated.get("hasta") else None,
                "activa": bool(updated["activa"]),
                "creado_en": str(updated["creado_en"]) if updated.get("creado_en") else None,
            }
    except IntegrityError as e:
        try:
            conn.rollback()
        except Exception:
            pass
        raise ValueError(f"No se puede cerrar asignación: {e}")
    finally:
        try:
            if conn.open:
                conn.close()
        except Exception:
            pass


def eliminar_asignacion(asignacion_id: int) -> dict[str, Any] | None:
    """Hard delete solo si activa=0 y hasta NOT NULL. Retorna None si no existe, 409 si activa."""
    try:
        asignacion_id = int(asignacion_id)
    except Exception:
        raise ValueError("id debe ser entero.")
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT activa, hasta FROM cajas_asignaciones WHERE id = %s", (asignacion_id,))
            row = cur.fetchone()
            if not row:
                return None
            if bool(row["activa"]):
                raise ValueError("No se puede eliminar una asignación activa")
            cur.execute("DELETE FROM cajas_asignaciones WHERE id = %s", (asignacion_id,))
            conn.commit()
            return {"id": asignacion_id, "eliminado": True}
    except IntegrityError as e:
        try:
            conn.rollback()
        except Exception:
            pass
        raise ValueError(f"No se puede eliminar: restricción FK - {e}")
    finally:
        try:
            if conn.open:
                conn.close()
        except Exception:
            pass


def obtener_asignacion(asignacion_id: int) -> dict[str, Any] | None:
    """Obtiene una asignación por id."""
    try:
        asignacion_id = int(asignacion_id)
    except Exception:
        raise ValueError("id debe ser entero.")
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT a.*, cj.codigo AS caja_codigo, p.nombre AS tecnico_nombre
                FROM cajas_asignaciones a
                LEFT JOIN cajas_cajas cj ON a.caja_id = cj.id
                LEFT JOIN personal p ON a.tecnico_id = p.id
                WHERE a.id = %s
                """,
                (asignacion_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "id": row["id"],
                "caja_id": row["caja_id"],
                "caja_codigo": row.get("caja_codigo"),
                "tecnico_id": row["tecnico_id"],
                "tecnico_nombre": row.get("tecnico_nombre"),
                "desde": str(row["desde"]) if row.get("desde") else None,
                "hasta": str(row["hasta"]) if row.get("hasta") else None,
                "activa": bool(row["activa"]),
                "creado_en": str(row["creado_en"]) if row.get("creado_en") else None,
            }
    finally:
        try:
            if conn.open:
                conn.close()
        except Exception:
            pass

