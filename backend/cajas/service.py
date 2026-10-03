# -*- coding: utf-8 -*-
"""Logica de negocio del modulo Cajas de Herramientas.

Implementa:
- Validacion de UPPER(TRIM(codigo))
- Coercion "" -> NULL para descripcion, ubicacion, articulo_codigo
- Manejo de IntegrityError -> 409 Conflict
- Verificacion de permisos JWT
"""

from __future__ import annotations

from typing import Any

from db import verificar_permiso, init_db
from store import (
    listar_cajas, obtener_caja, crear_caja, actualizar_caja, eliminar_caja,
    listar_herramientas, obtener_herramienta, crear_herramienta, actualizar_herramienta, eliminar_herramienta,
    crear_inventario_txn, obtener_inventario, listar_inventarios, actualizar_estado_inventario, eliminar_inventario,
    get_ideal_actual, crear_ideal_versionado, listar_ideal_versiones, obtener_ideal_detalle,
    listar_tecnicos_cards, listar_inventarios_por_tecnico,
    get_kpis_resumen as store_get_kpis_resumen, get_kpis_por_tecnico as store_get_kpis_por_tecnico,
    listar_limpieza, crear_limpieza as store_crear_limpieza, actualizar_limpieza_estado as store_actualizar_limpieza_estado,
    eliminar_limpieza as store_eliminar_limpieza, obtener_limpieza,
    listar_asignaciones, crear_asignacion as store_crear_asignacion, cerrar_asignacion as store_cerrar_asignacion,
    obtener_asignacion, eliminar_asignacion as store_eliminar_asignacion,
    recomendar_codigo_por_descripcion,
)


def _requerir_permiso(token: str, permiso: str) -> dict[str, Any] | None:
    """Verifica JWT y permiso. Retorna payload o None."""
    resultado = verificar_permiso(token, permiso)
    if resultado is None:
        return None
    return resultado


def health_payload() -> dict[str, Any]:
    return {"status": "ok", "service": "cajas", "version": "1.0.0"}


# --------------------------------------------------------------------------- #
# Cajas Cajas
# --------------------------------------------------------------------------- #
def get_cajas_list(token: str, params: dict[str, Any]) -> dict[str, Any] | tuple[str, int]:
    if not _requerir_permiso(token, "cajas:lectura"):
        return ("No autorizado", 401)
    q = str(params.get("q", ""))
    activo = params.get("activo")
    limit = int(params.get("limit", 50))
    offset = int(params.get("offset", 0))
    if activo is not None:
        activo = 1 if str(activo) == "true" else 0
    return listar_cajas(q=q, activo=activo, limit=limit, offset=offset)


def get_caja_by_id(token: str, caja_id: int) -> dict[str, Any] | tuple[str, int]:
    if not _requerir_permiso(token, "cajas:lectura"):
        return ("No autorizado", 401)
    caja = obtener_caja(caja_id)
    if not caja:
        return ("No encontrado", 404)
    return caja


def create_caja(token: str, data: dict[str, Any]) -> dict[str, Any] | tuple[str, int]:
    if not _requerir_permiso(token, "cajas:escritura"):
        return ("No autorizado", 401)
    try:
        return crear_caja(data)
    except ValueError as e:
        msg = str(e)
        if "unicidad" in msg.lower() or "ya existe" in msg.lower():
            return (msg, 409)
        return (msg, 400)


def update_caja(token: str, caja_id: int, data: dict[str, Any]) -> dict[str, Any] | tuple[str, int]:
    if not _requerir_permiso(token, "cajas:escritura"):
        return ("No autorizado", 401)
    try:
        result = actualizar_caja(caja_id, data)
        if result is None:
            return ("No encontrado", 404)
        return result
    except ValueError as e:
        msg = str(e)
        if "unicidad" in msg.lower() or "ya existe" in msg.lower():
            return (msg, 409)
        return (msg, 400)


def delete_caja(token: str, caja_id: int) -> dict[str, Any] | tuple[str, int]:
    if not _requerir_permiso(token, "cajas:escritura"):
        return ("No autorizado", 401)
    try:
        result = eliminar_caja(caja_id)
        if result is None:
            return ("No encontrado", 404)
        return result
    except ValueError as e:
        return (str(e), 409)


# --------------------------------------------------------------------------- #
# Cajas Herramientas
# --------------------------------------------------------------------------- #
def get_herramientas_list(token: str, params: dict[str, Any]) -> dict[str, Any] | tuple[str, int]:
    if not _requerir_permiso(token, "cajas:lectura"):
        return ("No autorizado", 401)
    q = str(params.get("q", ""))
    categoria = str(params.get("categoria", ""))
    limit = int(params.get("limit", 50))
    offset = int(params.get("offset", 0))
    return listar_herramientas(q=q, categoria=categoria, limit=limit, offset=offset)


def get_herramienta_by_id(token: str, herramienta_id: int) -> dict[str, Any] | tuple[str, int]:
    if not _requerir_permiso(token, "cajas:lectura"):
        return ("No autorizado", 401)
    herramienta = obtener_herramienta(herramienta_id)
    if not herramienta:
        return ("No encontrado", 404)
    return herramienta


def create_herramienta(token: str, data: dict[str, Any]) -> dict[str, Any] | tuple[str, int]:
    if not _requerir_permiso(token, "cajas:escritura"):
        return ("No autorizado", 401)
    try:
        return crear_herramienta(data)
    except ValueError as e:
        msg = str(e)
        if "unicidad" in msg.lower() or "ya existe" in msg.lower():
            return (msg, 409)
        return (msg, 400)


def update_herramienta(token: str, herramienta_id: int, data: dict[str, Any]) -> dict[str, Any] | tuple[str, int]:
    if not _requerir_permiso(token, "cajas:escritura"):
        return ("No autorizado", 401)
    try:
        result = actualizar_herramienta(herramienta_id, data)
        if result is None:
            return ("No encontrado", 404)
        return result
    except ValueError as e:
        msg = str(e)
        if "unicidad" in msg.lower() or "ya existe" in msg.lower():
            return (msg, 409)
        return (msg, 400)


def delete_herramienta(token: str, herramienta_id: int) -> dict[str, Any] | tuple[str, int]:
    if not _requerir_permiso(token, "cajas:escritura"):
        return ("No autorizado", 401)
    try:
        result = eliminar_herramienta(herramienta_id)
        if result is None:
            return ("No encontrado", 404)
        return result
    except ValueError as e:
        return (str(e), 409)


# --------------------------------------------------------------------------- #
# Cajas Inventarios
# --------------------------------------------------------------------------- #
def get_inventarios_list(token: str, params: dict[str, Any]) -> dict[str, Any] | tuple[str, int]:
    if not _requerir_permiso(token, "cajas:lectura"):
        return ("No autorizado", 401)
    caja_id = params.get("caja_id")
    periodo = params.get("periodo")
    estado = params.get("estado")
    q = str(params.get("q", ""))
    limit = int(params.get("limit", 50))
    offset = int(params.get("offset", 0))
    try:
        return listar_inventarios(
            caja_id=int(caja_id) if caja_id else None,
            periodo=periodo,
            estado=estado,
            q=q,
            limit=limit,
            offset=offset,
        )
    except ValueError as e:
        return (str(e), 400)


def get_inventario_by_id(token: str, inv_id: int) -> dict[str, Any] | tuple[str, int]:
    if not _requerir_permiso(token, "cajas:lectura"):
        return ("No autorizado", 401)
    inv = obtener_inventario(inv_id)
    if not inv:
        return ("No encontrado", 404)
    return inv


def create_inventario(token: str, data: dict[str, Any]) -> dict[str, Any] | tuple[str, int]:
    if not _requerir_permiso(token, "cajas:escritura"):
        return ("No autorizado", 401)
    try:
        return crear_inventario_txn(data)
    except ValueError as e:
        msg = str(e)
        if "ya existe inventario" in msg.lower() or "periodo" in msg.lower():
            return (msg, 409)
        if "no existe" in msg.lower() or "obligatorio" in msg.lower() or "invalido" in msg.lower():
            return (msg, 400)
        return (msg, 400)


def update_inventario_estado(token: str, inv_id: int, estado: str) -> dict[str, Any] | tuple[str, int]:
    if not _requerir_permiso(token, "cajas:escritura"):
        return ("No autorizado", 401)
    if estado not in ("borrador", "cerrado"):
        return ("estado must be 'borrador' or 'cerrado'", 400)
    try:
        result = actualizar_estado_inventario(inv_id, estado)
        if result is None:
            return ("No encontrado", 404)
        return result
    except ValueError as e:
        msg = str(e)
        if "revertir" in msg.lower():
            return (msg, 400)
        return (msg, 400)


def delete_inventario(token: str, inv_id: int) -> dict[str, Any] | tuple[str, int]:
    if not _requerir_permiso(token, "cajas:escritura"):
        return ("No autorizado", 401)
    try:
        result = eliminar_inventario(inv_id)
        if result is None:
            return ("No encontrado", 404)
        return result
    except ValueError as e:
        msg = str(e)
        if "cerrado" in msg.lower():
            return (msg, 409)
        return (msg, 400)


# --------------------------------------------------------------------------- #
# Caja Ideal (Versionado) — Slice 1
# --------------------------------------------------------------------------- #
def get_ideal(token: str, params: dict[str, Any] | None = None) -> dict[str, Any] | tuple[str, int]:
    """GET /api/cajas/ideal — retorna ideal activo o placeholder con mensaje."""
    if not _requerir_permiso(token, "cajas:lectura"):
        return ("No autorizado", 401)
    ideal = get_ideal_actual()
    if not ideal:
        # Respuesta 200 con placeholder y hint según spec/design
        return {
            "id": None,
            "nombre": None,
            "descripcion": None,
            "activa": False,
            "vigente_desde": None,
            "creado_por": None,
            "creado_en": None,
            "herramientas": [],
            "mensaje": "No hay Caja Ideal definida",
        }
    return ideal


def put_ideal(token: str, data: dict[str, Any]) -> dict[str, Any] | tuple[str, int]:
    """PUT /api/cajas/ideal — crea nueva versión versionada (escritura)."""
    perm_payload = _requerir_permiso(token, "cajas:escritura")
    if not perm_payload:
        return ("No autorizado", 401)
    # Validación básica previa para mensajes claros
    if not isinstance(data, dict):
        return ("Payload inválido.", 400)
    if not str(data.get("nombre") or "").strip():
        return ("El nombre es obligatorio.", 400)
    detalle = data.get("detalle")
    if detalle is None and isinstance(data.get("herramientas"), list):
        detalle = data.get("herramientas")
    if not isinstance(detalle, list) or len(detalle) == 0:
        return ("detalle debe contener al menos un item.", 400)
    # Extraer creado_por del token payload (id o sub)
    creado_por = None
    if isinstance(perm_payload, dict):
        cp = perm_payload.get("id")
        if cp is None:
            cp = perm_payload.get("sub")
        try:
            if cp is not None and str(cp).strip() != "" and str(cp).strip().lower() != "test":
                creado_por = int(cp)
            elif isinstance(cp, int):
                creado_por = cp
        except Exception:
            creado_por = None
    try:
        return crear_ideal_versionado(data, creado_por=creado_por)
    except ValueError as e:
        msg = str(e)
        low = msg.lower()
        if "ya asignada" in low or "duplicate" in low or "duplicado" in low or "uq_ideal_herramienta" in low:
            return (msg, 409)
        if "unicidad" in low or "ya existe" in low:
            return (msg, 409)
        return (msg, 400)


def get_ideal_versiones(token: str, params: dict[str, Any] | None = None) -> dict[str, Any] | tuple[str, int]:
    """GET /api/cajas/ideal/versiones — lista paginada de versiones."""
    if not _requerir_permiso(token, "cajas:lectura"):
        return ("No autorizado", 401)
    if params is None:
        params = {}
    try:
        limit = int(params.get("limit", 50))
    except Exception:
        limit = 50
    try:
        offset = int(params.get("offset", 0))
    except Exception:
        offset = 0
    # Infra: clamp handled in store as well, but do here too
    if limit < 1:
        limit = 1
    if limit > 100:
        limit = 100
    if offset < 0:
        offset = 0
    return listar_ideal_versiones(limit=limit, offset=offset)


def get_ideal_by_id(token: str, ideal_id: int) -> dict[str, Any] | tuple[str, int]:
    """Helper para obtener ideal por id (uso futuro / historial)."""
    if not _requerir_permiso(token, "cajas:lectura"):
        return ("No autorizado", 401)
    ideal = obtener_ideal_detalle(ideal_id)
    if not ideal:
        return ("No encontrado", 404)
    return ideal


# --------------------------------------------------------------------------- #
# Tecnicos-Cards + Historial + KPIs (Slice 2)
# --------------------------------------------------------------------------- #
def get_tecnicos_cards(token: str, params: dict[str, Any] | None = None) -> dict[str, Any] | tuple[str, int]:
    """GET /api/cajas/tecnicos-cards — lista técnicos con % faltantes vs ideal."""
    if not _requerir_permiso(token, "cajas:lectura"):
        return ("No autorizado", 401)
    if params is None:
        params = {}
    q = str(params.get("q", "") or "")
    # con_inventario param: solo técnicos que ya tienen al menos un inventario
    con_inv_raw = params.get("con_inventario")
    if con_inv_raw is None:
        con_inv_raw = params.get("soloConInventario") or params.get("conInventario")
    # Default True: solo con inventario (pedido del usuario) — solo si explícitamente piden false se muestra todo
    con_inventario = True
    if con_inv_raw is not None:
        s = str(con_inv_raw).strip().lower()
        if s in ("0", "false", "no", "off"):
            con_inventario = False
        elif s in ("1", "true", "si", "sí", "yes"):
            con_inventario = True
        else:
            # valor no reconocido → mantener True
            con_inventario = True
    try:
        limit = int(params.get("limit", 25))
    except Exception:
        limit = 25
    try:
        offset = int(params.get("offset", 0))
    except Exception:
        offset = 0
    if limit < 1:
        limit = 1
    if limit > 100:
        limit = 100
    if offset < 0:
        offset = 0
    try:
        return listar_tecnicos_cards(q=q, limit=limit, offset=offset, con_inventario=con_inventario)
    except ValueError as e:
        return (str(e), 400)


def get_inventarios_por_tecnico(
    token: str, tecnico_id: int, params: dict[str, Any] | None = None
) -> dict[str, Any] | tuple[str, int]:
    """GET /api/cajas/tecnicos/{id}/inventarios — historial por técnico."""
    if not _requerir_permiso(token, "cajas:lectura"):
        return ("No autorizado", 401)
    # Validar técnico existe en personal (read-only FK)
    try:
        from db import get_connection as _get_conn
        conn = _get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, tipo FROM personal WHERE id = %s", (tecnico_id,))
                row = cur.fetchone()
                if not row:
                    return ("Tecnico no encontrado", 404)
        finally:
            try:
                if conn.open:
                    conn.close()
            except Exception:
                pass
    except Exception:
        # Si falla la verificación por infra, no bloqueamos pero reportamos 404 solo si row is None
        pass
    if params is None:
        params = {}
    try:
        limit = int(params.get("limit", 25))
    except Exception:
        limit = 25
    try:
        offset = int(params.get("offset", 0))
    except Exception:
        offset = 0
    estado = params.get("estado")
    if estado is not None and str(estado).strip() == "":
        estado = None
    if limit < 1:
        limit = 1
    if limit > 100:
        limit = 100
    if offset < 0:
        offset = 0
    try:
        return listar_inventarios_por_tecnico(tecnico_id, limit=limit, offset=offset, estado=estado)
    except ValueError as e:
        return (str(e), 400)


def get_kpis_resumen(token: str, params: dict[str, Any] | None = None) -> dict[str, Any] | tuple[str, int]:
    """GET /api/cajas/kpis/resumen — KPIs agregados globales y por técnico."""
    if not _requerir_permiso(token, "cajas:lectura"):
        return ("No autorizado", 401)
    if params is None:
        params = {}
    q = str(params.get("q", "") or "")
    limit_raw = params.get("limit")
    offset_raw = params.get("offset", 0)
    limit = None
    offset = 0
    if limit_raw is not None:
        try:
            limit = int(limit_raw)
        except Exception:
            limit = None
    try:
        offset = int(offset_raw)
    except Exception:
        offset = 0
    try:
        return store_get_kpis_resumen(q=q, limit=limit, offset=offset)
    except ValueError as e:
        return (str(e), 400)


def get_kpis_por_tecnico(token: str, tecnico_id: int) -> dict[str, Any] | tuple[str, int]:
    """GET /api/cajas/kpis/tecnico/{id} — KPIs individuales con historial."""
    if not _requerir_permiso(token, "cajas:lectura"):
        return ("No autorizado", 401)
    # Validar técnico existe
    try:
        from db import get_connection as _get_conn2
        conn = _get_conn2()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM personal WHERE id = %s", (tecnico_id,))
                row = cur.fetchone()
                if not row:
                    return ("Tecnico no encontrado", 404)
        finally:
            try:
                if conn.open:
                    conn.close()
            except Exception:
                pass
    except Exception:
        pass
    try:
        result = store_get_kpis_por_tecnico(tecnico_id)
        if result is None:
            return ("Tecnico no encontrado", 404)
        return result
    except ValueError as e:
        return (str(e), 400)


# --------------------------------------------------------------------------- #
# Limpieza Historial (Fase 2)
# --------------------------------------------------------------------------- #
def get_limpieza_list(token: str, params: dict[str, Any] | None = None) -> dict[str, Any] | tuple[str, int]:
    """GET /api/cajas/limpieza — lista paginada con filtros."""
    if not _requerir_permiso(token, "cajas:lectura"):
        return ("No autorizado", 401)
    if params is None:
        params = {}
    try:
        caja_id = params.get("caja_id")
        tecnico_id = params.get("tecnico_id")
        estado = params.get("estado")
        limit = params.get("limit", 50)
        offset = params.get("offset", 0)
        # Normalizar '' -> None
        if caja_id is not None and str(caja_id).strip() == "":
            caja_id = None
        if tecnico_id is not None and str(tecnico_id).strip() == "":
            tecnico_id = None
        if estado is not None and str(estado).strip() == "":
            estado = None
        return listar_limpieza(caja_id=caja_id, tecnico_id=tecnico_id, estado=estado, limit=limit, offset=offset)
    except ValueError as e:
        return (str(e), 400)


def create_limpieza(token: str, data: dict[str, Any]) -> dict[str, Any] | tuple[str, int]:
    """POST /api/cajas/limpieza — crea evento."""
    if not _requerir_permiso(token, "cajas:escritura"):
        return ("No autorizado", 401)
    if not isinstance(data, dict):
        return ("Payload inválido.", 400)
    try:
        return store_crear_limpieza(data)
    except ValueError as e:
        msg = str(e)
        low = msg.lower()
        if "no existe" in low or "fk" in low or "integridad" in low:
            return (msg, 400)
        if "obligatorio" in low or "formato inválido" in low or "debe ser uno de" in low or "tipo" in low:
            return (msg, 400)
        return (msg, 400)


def update_limpieza_estado(token: str, limpieza_id: int, data: dict[str, Any]) -> dict[str, Any] | tuple[str, int]:
    """PATCH /api/cajas/limpieza/{id}/estado — actualiza estado/observaciones."""
    if not _requerir_permiso(token, "cajas:escritura"):
        return ("No autorizado", 401)
    if not isinstance(data, dict):
        return ("Payload inválido.", 400)
    try:
        result = store_actualizar_limpieza_estado(limpieza_id, data)
        if result is None:
            return ("No encontrado", 404)
        return result
    except ValueError as e:
        msg = str(e)
        low = msg.lower()
        if "solo se puede cambiar" in low or "transición inválida" in low:
            return (msg, 409)
        if "debe ser uno de" in low or "formato" in low:
            return (msg, 400)
        return (msg, 400)


def delete_limpieza(token: str, limpieza_id: int) -> dict[str, Any] | tuple[str, int]:
    """DELETE /api/cajas/limpieza/{id} — solo si pendiente."""
    if not _requerir_permiso(token, "cajas:escritura"):
        return ("No autorizado", 401)
    try:
        result = store_eliminar_limpieza(limpieza_id)
        if result is None:
            return ("No encontrado", 404)
        return result
    except ValueError as e:
        msg = str(e)
        if "no está en estado pendiente" in msg.lower() or "no se puede eliminar" in msg.lower():
            return (msg, 409)
        return (msg, 400)


def get_limpieza_by_id(token: str, limpieza_id: int) -> dict[str, Any] | tuple[str, int]:
    """GET /api/cajas/limpieza/{id} — helper."""
    if not _requerir_permiso(token, "cajas:lectura"):
        return ("No autorizado", 401)
    result = obtener_limpieza(limpieza_id)
    if result is None:
        return ("No encontrado", 404)
    return result


# --------------------------------------------------------------------------- #
# Asignaciones (Fase 2)
# --------------------------------------------------------------------------- #
def get_asignaciones_list(token: str, params: dict[str, Any] | None = None) -> dict[str, Any] | tuple[str, int]:
    """GET /api/cajas/asignaciones — lista paginada."""
    if not _requerir_permiso(token, "cajas:lectura"):
        return ("No autorizado", 401)
    if params is None:
        params = {}
    try:
        caja_id = params.get("caja_id")
        tecnico_id = params.get("tecnico_id")
        activa = params.get("activa")
        limit = params.get("limit", 50)
        offset = params.get("offset", 0)
        if caja_id is not None and str(caja_id).strip() == "":
            caja_id = None
        if tecnico_id is not None and str(tecnico_id).strip() == "":
            tecnico_id = None
        if activa is not None and str(activa).strip() == "":
            activa = None
        return listar_asignaciones(caja_id=caja_id, tecnico_id=tecnico_id, activa=activa, limit=limit, offset=offset)
    except ValueError as e:
        return (str(e), 400)


def create_asignacion(token: str, data: dict[str, Any]) -> dict[str, Any] | tuple[str, int]:
    """POST /api/cajas/asignaciones — crea asignación transaccional."""
    if not _requerir_permiso(token, "cajas:escritura"):
        return ("No autorizado", 401)
    if not isinstance(data, dict):
        return ("Payload inválido.", 400)
    try:
        return store_crear_asignacion(data)
    except ValueError as e:
        msg = str(e)
        low = msg.lower()
        if "ya hay una asignación activa" in low:
            return (msg, 409)
        if "no existe" in low or "fk" in low or "integridad" in low:
            return (msg, 400)
        if "obligatorio" in low or "formato inválido" in low or "tipo" in low or "no puede ser anterior" in low:
            return (msg, 400)
        return (msg, 400)


def cerrar_asignacion(token: str, asignacion_id: int) -> dict[str, Any] | tuple[str, int]:
    """PATCH /api/cajas/asignaciones/{id}/cerrar — cierra asignación activa."""
    if not _requerir_permiso(token, "cajas:escritura"):
        return ("No autorizado", 401)
    try:
        result = store_cerrar_asignacion(asignacion_id)
        if result is None:
            return ("No encontrado", 404)
        return result
    except ValueError as e:
        msg = str(e)
        if "ya está cerrada" in msg.lower():
            return (msg, 409)
        return (msg, 400)


def delete_asignacion(token: str, asignacion_id: int) -> dict[str, Any] | tuple[str, int]:
    """DELETE /api/cajas/asignaciones/{id} — solo si inactiva."""
    if not _requerir_permiso(token, "cajas:escritura"):
        return ("No autorizado", 401)
    try:
        result = store_eliminar_asignacion(asignacion_id)
        if result is None:
            return ("No encontrado", 404)
        return result
    except ValueError as e:
        msg = str(e)
        if "no se puede eliminar una asignación activa" in msg.lower():
            return (msg, 409)
        return (msg, 400)


def get_asignacion_by_id(token: str, asignacion_id: int) -> dict[str, Any] | tuple[str, int]:
    """GET /api/cajas/asignaciones/{id} — helper."""
    if not _requerir_permiso(token, "cajas:lectura"):
        return ("No autorizado", 401)
    result = obtener_asignacion(asignacion_id)
    if result is None:
        return ("No encontrado", 404)
    return result


# --------------------------------------------------------------------------- #
# Recomendacion codigo maestro_stock por descripcion
# --------------------------------------------------------------------------- #
def get_recomendacion_codigo(token: str, params: dict[str, Any] | None = None) -> dict[str, Any] | tuple[str, int]:
    """GET /api/cajas/herramientas/recomendar-codigo?descripcion=... — sugiere codigos maestro_stock."""
    if not _requerir_permiso(token, "cajas:lectura"):
        return ("No autorizado", 401)
    if params is None:
        params = {}
    descripcion = str(params.get("descripcion") or params.get("q") or "").strip()
    if not descripcion:
        return ({"detail": "descripcion es obligatoria."}, 400)  # type: ignore
    try:
        limit = int(params.get("limit", 5))
    except Exception:
        limit = 5
    try:
        return recomendar_codigo_por_descripcion(descripcion=descripcion, limit=limit)
    except ValueError as e:
        return (str(e), 400)
