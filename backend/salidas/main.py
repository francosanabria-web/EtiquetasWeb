# -*- coding: utf-8 -*-
"""API Salidas — Starlette (puerto 8018). Egreso de material del pañol."""

from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager
from typing import Callable

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from config import PORT, cors_origins_list, data_path, maestro_path, maestro_writable
from db import verificar_permiso
from firebase_sync import iniciar_alias_sync_background, iniciar_sync_background

# Maestro stock - imported lazily to avoid circular issues if DB not ready
try:
    from routes.maestro_stock import (
        get_codigo_history as maestro_codigo_history,
        get_import_diff as maestro_import_diff,
        get_import_log as maestro_import_log,
        get_import_log_by_id as maestro_import_log_by_id,
        get_list as maestro_list,
        get_stats as maestro_stats,
        post_import as maestro_import,
        post_sync_alias as maestro_sync_alias,
        put_alias as maestro_put_alias,
    )
except ImportError:
    # Fallback when routes package not found (e.g., flat file)
    try:
        from maestro_stock_routes import (  # type: ignore
            get_codigo_history as maestro_codigo_history,  # type: ignore
            get_import_diff as maestro_import_diff,  # type: ignore
            get_import_log as maestro_import_log,
            get_import_log_by_id as maestro_import_log_by_id,
            get_list as maestro_list,
            get_stats as maestro_stats,
            post_import as maestro_import,
            post_sync_alias as maestro_sync_alias,
            put_alias as maestro_put_alias,
        )
    except ImportError:
        maestro_import = maestro_list = maestro_import_log = maestro_import_log_by_id = maestro_stats = maestro_sync_alias = maestro_put_alias = maestro_import_diff = maestro_codigo_history = None  # type: ignore
        # Ensure names exist for route wiring
        maestro_import_diff = None  # type: ignore
        maestro_codigo_history = None  # type: ignore
from service import (
    actualizar_motivo,
    anular_movimiento,
    atenciones_export_data,
    buscar_articulo,
    buscar_articulos,
    confirmar_devolucion,
    confirmar_salida,
    crear_motivo,
    editar_movimiento,
    eliminar_motivo,
    generar_diario_para_mail,
    generar_remito_para_orden,
    get_catalogos,
    health_payload,
    kpi_atenciones,
    listar_atenciones,
    listar_auditoria,
    listar_motivos,
    listar_movimientos,
    proyectar_stock,
    refresh_maestro,
    registrar_atencion,
    resumen_diario,
    sync_firebase_ahora,
)
from store import CargandoDatosError, RedNoDisponibleError, SalidasStore

log = logging.getLogger("salidas")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def _err(e: Exception, code: int = 500) -> JSONResponse:
    return JSONResponse({"detail": str(e)}, status_code=code)


async def _run_json(work: Callable[[], dict], *, ok_status: int = 200) -> JSONResponse:
    try:
        data = await run_in_threadpool(work)
    except CargandoDatosError as e:
        return _err(e, 503)
    except RedNoDisponibleError as e:
        return _err(e, 503)
    except FileNotFoundError as e:
        return _err(e, 503)
    except TimeoutError as e:
        return _err(e, 409)
    except PermissionError as e:
        return _err(e, 409)
    except ValueError as e:
        return _err(e, 400)
    except Exception as e:
        log.exception("Error en endpoint")
        return _err(e, 500)
    return JSONResponse(data, status_code=ok_status)


async def health(_: Request) -> JSONResponse:
    payload = health_payload()
    code = 200 if payload.get("estado") == "ok" else 503
    return JSONResponse(payload, status_code=code)


async def get_catalogos_ep(_: Request) -> JSONResponse:
    return await _run_json(get_catalogos)


async def get_articulo(request: Request) -> JSONResponse:
    codigo = (request.path_params.get("codigo") or "").strip()
    return await _run_json(lambda: buscar_articulo(codigo))


async def post_proyectar(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return _err(ValueError("JSON inválido."), 400)
    if not isinstance(body, dict):
        return _err(ValueError("JSON inválido."), 400)

    def work() -> dict:
        return proyectar_stock(
            str(body.get("codigo") or ""),
            body.get("cantidad", 0),
            pendientes=body.get("pendientes") if isinstance(body.get("pendientes"), list) else [],
            es_devolucion=bool(body.get("es_devolucion")),
        )

    return await _run_json(work)


async def post_confirmar(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return _err(ValueError("JSON inválido."), 400)
    if not isinstance(body, dict):
        return _err(ValueError("JSON inválido."), 400)
    return await _run_json(lambda: confirmar_salida(body))


async def post_devolucion(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return _err(ValueError("JSON inválido."), 400)
    if not isinstance(body, dict):
        return _err(ValueError("JSON inválido."), 400)
    return await _run_json(lambda: confirmar_devolucion(body))


async def get_movimientos(request: Request) -> JSONResponse:
    q = request.query_params
    limite_raw = q.get("limite") or "100"
    try:
        limite = max(1, min(1000, int(limite_raw)))
    except ValueError:
        limite = 100
    incluir_raw = q.get("incluir_anulados") or q.get("incluirAnulados") or q.get("mostrar_anulados") or "0"
    incluir_anulados = str(incluir_raw).strip().lower() not in ("0", "false", "no", "off", "")

    def work() -> dict:
        return listar_movimientos(
            desde=q.get("desde"),
            hasta=q.get("hasta"),
            limite=limite,
            codigo=q.get("codigo"),
            q=q.get("q"),
            sector=q.get("sector"),
            numero_orden=q.get("numero_orden") or q.get("orden"),
            incluir_anulados=incluir_anulados,
        )

    return await _run_json(work)


async def delete_movimiento(request: Request) -> JSONResponse:
    ok, payload = _exigir_admin(request)
    if not ok:
        return JSONResponse({"detail": "Solo admin puede anular bajas (requiere rol admin + salidas:escritura)."}, status_code=403)
    mov_id = request.path_params.get("id") or request.path_params.get("movimiento_id") or ""
    # motivo puede venir en JSON body o query
    motivo = None
    try:
        body = await request.json()
        if isinstance(body, dict):
            motivo = body.get("motivo") or body.get("motivo_anulacion") or body.get("reason")
    except Exception:
        pass
    if not motivo:
        motivo = request.query_params.get("motivo") or request.query_params.get("reason") or ""
    motivo = str(motivo or "").strip()
    if len(motivo) < 3:
        return _err(ValueError("motivo requerido (3..500 caracteres). Motivo obligatorio para trazabilidad."), 400)
    if len(motivo) > 500:
        return _err(ValueError("motivo max 500 caracteres."), 400)
    realizado_por = str((payload or {}).get("usuario") or (payload or {}).get("sub") or "SISTEMA")

    def work() -> dict:
        return anular_movimiento(mov_id, motivo=motivo, realizado_por=realizado_por)

    return await _run_json(work)


async def put_movimiento(request: Request) -> JSONResponse:
    ok, payload = _exigir_admin(request)
    if not ok:
        return JSONResponse({"detail": "Solo admin puede editar bajas (requiere rol admin + salidas:escritura)."}, status_code=403)
    mov_id = request.path_params.get("id") or request.path_params.get("movimiento_id") or ""
    try:
        body = await request.json()
    except Exception:
        return _err(ValueError("JSON invalido."), 400)
    if not isinstance(body, dict):
        return _err(ValueError("JSON invalido."), 400)
    # Extraer motivo opcional (para auditoria)
    motivo = body.get("motivo") or body.get("motivo_edicion") or None
    # Filtrar campos permitidos (fecha solo admin - es admin-only porque este endpoint ya exige admin)
    permitidos = ("tipo_comprobante", "numero_orden", "maquina_sitio", "sector_nombre", "operario_nombre", "cantidad", "precio_unitario", "fecha")
    cambios: dict = {}
    for k in permitidos:
        if k in body:
            cambios[k] = body[k]
        # Soportar aliases UPPER
        elif k.upper() in body:
            cambios[k] = body[k.upper()]
        elif k.lower() in (x.lower() for x in body.keys()):
            # case-insensitive fallback
            for kk, vv in body.items():
                if kk.lower() == k.lower():
                    cambios[k] = vv
                    break
    if not cambios:
        return _err(ValueError("No hay campos editables (permitidos: tipo_comprobante, numero_orden, maquina_sitio, sector_nombre, operario_nombre, cantidad, precio_unitario, fecha)."), 400)
    realizado_por = str((payload or {}).get("usuario") or (payload or {}).get("sub") or "SISTEMA")

    def work() -> dict:
        return editar_movimiento(mov_id, cambios=cambios, realizado_por=realizado_por, motivo=motivo)

    return await _run_json(work)


async def get_movimiento_auditoria(request: Request) -> JSONResponse:
    tok = _token(request)
    if tok and not verificar_permiso(tok, "salidas:lectura"):
        return JSONResponse({"detail": "Sin permiso de lectura en salidas."}, status_code=403)
    # Si no hay token, verificar default? Permitir si es anonimo? Requerir al menos lectura: si no token -> 403 si DB_ENABLED? Para compat historial anon, permitimos.
    # Pero para auditoria, exigir token lectura si sistema tiene auth.
    # Si no hay token y no hay usuarios, dejar pasar? Simplificar: si hay usuarios module, exigir lectura; sino anonim.
    # Implementamos: si tok presente falla -> 403, si no tok -> permitir (historial anonimo)
    mov_id = request.path_params.get("id") or request.path_params.get("movimiento_id") or ""

    def work() -> dict:
        return listar_auditoria(mov_id)

    return await _run_json(work)


async def get_articulos_search(request: Request) -> JSONResponse:
    """Buscar en maestro para modal 'Maestro de stock' (q, limite)."""
    q = request.query_params
    term = (q.get("q") or q.get("query") or "").strip()
    limite_raw = q.get("limite") or "20"
    try:
        limite = max(1, min(100, int(limite_raw)))
    except ValueError:
        limite = 20

    def work() -> dict:
        items = buscar_articulos(term, limite=limite)
        return {"total": len(items), "items": items, "q": term, "limite": limite}

    return await _run_json(work)


async def get_remito_export(request: Request) -> Response:
    """Genera remito Excel por orden. Query: orden (requerido), fecha opcional."""
    q = request.query_params
    tok = _token(request)
    if tok and not verificar_permiso(tok, "salidas:lectura"):
        return JSONResponse({"detail": "Sin permiso de lectura en salidas."}, status_code=403)
    orden = (q.get("orden") or q.get("numero_orden") or q.get("numeroOrden") or "").strip()
    if not orden:
        return JSONResponse({"detail": "orden es obligatoria (?orden=XXX)."}, status_code=400)
    fecha = (q.get("fecha") or "").strip() or None

    def work() -> tuple[bytes, str]:
        return generar_remito_para_orden(orden, fecha)

    try:
        data, fname = await run_in_threadpool(work)
    except ValueError as e:
        return JSONResponse({"detail": str(e)}, status_code=400)
    except Exception as e:
        log.exception("Error en export remito")
        return JSONResponse({"detail": str(e)}, status_code=500)
    headers = {"Content-Disposition": f'attachment; filename="{fname}"'}
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


async def post_refresh(_: Request) -> JSONResponse:
    return await _run_json(refresh_maestro)


async def post_sync_firebase(_: Request) -> JSONResponse:
    return await _run_json(sync_firebase_ahora)


def _token(request: Request) -> str:
    auth = request.headers.get("authorization", "") or request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return (request.headers.get("x-token", "") or request.headers.get("X-Token", "") or "").strip()


def _usuario_desde_token(request: Request) -> str | None:
    tok = _token(request)
    if not tok:
        return None
    payload = verificar_permiso(tok, "salidas:lectura")
    if payload:
        # Priorizar usuario legible
        return str(payload.get("usuario") or payload.get("sub") or payload.get("id") or tok[:24])
    # Token presente pero sin permiso -> no autenticado; no revelar
    return None


def _exigir_admin(request: Request) -> tuple[bool, dict | None]:
    """Verifica que el token tenga salidas:escritura Y rol admin.

    Retorna (ok, payload). Para motivos POST/PUT/DELETE es admin-only:
    sin token => denegar (403) a diferencia de atenciones que permiten anonimo.
    """
    tok = _token(request)
    if not tok:
        return False, None
    payload = verificar_permiso(tok, "salidas:escritura")
    if not payload:
        return False, None
    rol = str(payload.get("rol") or "").strip().lower()
    nivel = str(payload.get("nivel") or "").strip().lower()
    # Exigir admin: rol == admin (nivel escritura viene de admin/panol, pero solo admin puede editar motivos)
    if rol != "admin":
        # Fallback: si no hay rol pero nivel escritura + usuario admin? Denegar si no es admin
        return False, payload
    # nivel ya verificado via verificar_permiso, pero doble check
    if nivel and nivel not in ("escritura",):
        # admin siempre tiene escritura, pero verificar
        pass
    return True, payload


async def post_atencion(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return _err(ValueError("JSON inválido."), 400)
    if not isinstance(body, dict):
        return _err(ValueError("JSON inválido."), 400)
    tok = _token(request)
    # Si se envia token, exigir permiso escritura; si no hay token, permitir (compat salidas anon)
    if tok:
        if not verificar_permiso(tok, "salidas:escritura"):
            return _err(PermissionError("Sin permiso de escritura en salidas."), 403)
    atendido_token = _usuario_desde_token(request)

    def work() -> dict:
        return registrar_atencion(body, atendido_por_token=atendido_token)

    return await _run_json(work, ok_status=201)


async def get_atenciones(request: Request) -> JSONResponse:
    q = request.query_params
    # Lectura: si hay token verificar lectura, sino permitir
    tok = _token(request)
    if tok and not verificar_permiso(tok, "salidas:lectura"):
        return _err(PermissionError("Sin permiso de lectura en salidas."), 403)
    limite_raw = q.get("limite") or "100"
    try:
        limite = max(1, min(1000, int(limite_raw)))
    except ValueError:
        limite = 100

    def work() -> dict:
        return listar_atenciones(
            desde=q.get("desde"),
            hasta=q.get("hasta"),
            con_retiro=q.get("con_retiro"),
            q=q.get("q"),
            limite=limite,
        )

    return await _run_json(work)


async def get_atenciones_export(request: Request) -> Response:
    q = request.query_params
    tok = _token(request)
    if tok and not verificar_permiso(tok, "salidas:lectura"):
        return JSONResponse({"detail": "Sin permiso de lectura en salidas."}, status_code=403)
    formato = (q.get("formato") or q.get("format") or "xlsx").strip().lower()
    if formato not in ("xlsx", "csv"):
        formato = "xlsx"

    def work() -> tuple[bytes, str, str]:
        return atenciones_export_data(desde=q.get("desde"), hasta=q.get("hasta"), formato=formato)

    try:
        data, ctype, fname = await run_in_threadpool(work)
    except ValueError as e:
        return _err(e, 400)
    except Exception as e:
        log.exception("Error en export atenciones")
        return _err(e, 500)
    headers = {"Content-Disposition": f'attachment; filename="{fname}"'}
    return Response(content=data, media_type=ctype, headers=headers)


async def get_atenciones_kpi(request: Request) -> JSONResponse:
    q = request.query_params
    tok = _token(request)
    if tok and not verificar_permiso(tok, "salidas:lectura"):
        return _err(PermissionError("Sin permiso de lectura en salidas."), 403)

    def work() -> dict:
        return kpi_atenciones(periodo=q.get("periodo"), desde=q.get("desde"), hasta=q.get("hasta"))

    return await _run_json(work)


# ---------- Motivos catalogo editable (v3 - admin only para escritura) ----------


async def get_motivos(request: Request) -> JSONResponse:
    # GET motivos: lectura a todos (anonimo o autenticado). Si hay token, verificar lectura opcional.
    q = request.query_params
    tok = _token(request)
    if tok and not verificar_permiso(tok, "salidas:lectura"):
        return _err(PermissionError("Sin permiso de lectura en salidas."), 403)
    activos_only_raw = q.get("activos_only", q.get("activos", "1"))
    activos_only = str(activos_only_raw).strip().lower() not in ("0", "false", "no", "off", "")

    def work() -> dict:
        return listar_motivos(activos_only=activos_only)

    return await _run_json(work)


async def post_motivo(request: Request) -> JSONResponse:
    ok, payload = _exigir_admin(request)
    if not ok:
        return JSONResponse({"detail": "Solo admin puede crear motivos (requiere rol admin + salidas:escritura)."}, status_code=403)
    try:
        body = await request.json()
    except Exception:
        return _err(ValueError("JSON inválido."), 400)
    if not isinstance(body, dict):
        return _err(ValueError("JSON inválido."), 400)

    def work() -> dict:
        return crear_motivo(body)

    return await _run_json(work, ok_status=201)


async def put_motivo(request: Request) -> JSONResponse:
    ok, payload = _exigir_admin(request)
    if not ok:
        return JSONResponse({"detail": "Solo admin puede editar motivos."}, status_code=403)
    motivo_id = request.path_params.get("id") or request.path_params.get("motivo_id") or ""
    try:
        body = await request.json()
    except Exception:
        return _err(ValueError("JSON inválido."), 400)
    if not isinstance(body, dict):
        return _err(ValueError("JSON inválido."), 400)

    def work() -> dict:
        return actualizar_motivo(motivo_id, body)

    return await _run_json(work)


async def delete_motivo(request: Request) -> JSONResponse:
    ok, payload = _exigir_admin(request)
    if not ok:
        return JSONResponse({"detail": "Solo admin puede eliminar motivos."}, status_code=403)
    motivo_id = request.path_params.get("id") or request.path_params.get("motivo_id") or ""

    def work() -> dict:
        return eliminar_motivo(motivo_id)

    return await _run_json(work)


async def get_resumen_diario(request: Request) -> JSONResponse:
    """Retorna resumen diario agrupado por tipo comprobante (PAÑOL, L1-L7, OTROS)."""
    q = request.query_params
    tok = _token(request)
    if tok and not verificar_permiso(tok, "salidas:lectura"):
        return JSONResponse({"detail": "Sin permiso de lectura en salidas."}, status_code=403)
    fecha = (q.get("fecha") or "").strip()
    if not fecha:
        return JSONResponse({"detail": "fecha es obligatoria (AAAA-MM-DD)."}, status_code=400)
    incluir_raw = q.get("incluir_anulados") or "0"
    incluir_anulados = str(incluir_raw).strip().lower() not in ("0", "false", "no", "off", "")

    def work() -> dict:
        return resumen_diario(fecha, incluir_anulados=incluir_anulados)

    return await _run_json(work)


async def get_diario_export(request: Request) -> Response:
    """Export on-demand diario sin persistir archivo - fuente unica salida_historial (soporta DB)."""
    q = request.query_params
    tok = _token(request)
    if tok and not verificar_permiso(tok, "salidas:lectura"):
        return JSONResponse({"detail": "Sin permiso de lectura en salidas."}, status_code=403)
    fecha = (q.get("fecha") or q.get("desde") or "").strip()
    if not fecha:
        return JSONResponse({"detail": "fecha es obligatoria (AAAA-MM-DD)."}, status_code=400)

    def work() -> tuple[bytes, str]:
        return generar_diario_para_mail(fecha)

    try:
        data, fname = await run_in_threadpool(work)
    except ValueError as e:
        return JSONResponse({"detail": str(e)}, status_code=400)
    except Exception as e:
        log.exception("Error en export diario")
        return JSONResponse({"detail": str(e)}, status_code=500)
    headers = {"Content-Disposition": f'attachment; filename="{fname}"'}
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


def _carga_inicial() -> None:
    try:
        # Punto 2 - inicializar tablas MariaDB (idempotente, maneja DROPs v4)
        try:
            from db import init_db

            init_db()
            log.info("DB salidas inicializada (salida_historial + atenciones v4)")
        except Exception as e:
            log.warning("init_db salidas fallo (no critico, continua con fallback): %s", e)
        SalidasStore.get().refresh()
        log.info(
            "Maestro salidas cargado desde %s (writable=%s) | escritura=%s",
            maestro_path(),
            maestro_writable(),
            data_path(),
        )
    except Exception as e:
        SalidasStore.get().registrar_error_carga(str(e))
        log.warning("Carga inicial fallida: %s", e)


routes = [
    Route("/health", health, methods=["GET"]),
    Route("/api/salidas/health", health, methods=["GET"]),
    Route("/api/salidas/catalogos", get_catalogos_ep, methods=["GET"]),
    Route("/api/salidas/articulo/{codigo}", get_articulo, methods=["GET"]),
    Route("/api/salidas/articulos", get_articulos_search, methods=["GET"]),
    Route("/api/salidas/proyectar", post_proyectar, methods=["POST"]),
    Route("/api/salidas/confirmar", post_confirmar, methods=["POST"]),
    Route("/api/salidas/devolucion", post_devolucion, methods=["POST"]),
    Route("/api/salidas/movimientos", get_movimientos, methods=["GET"]),
    Route("/api/salidas/historial", get_movimientos, methods=["GET"]),
    Route("/api/salidas/movimientos/{id}", delete_movimiento, methods=["DELETE"]),
    Route("/api/salidas/movimientos/{id}", put_movimiento, methods=["PUT"]),
    Route("/api/salidas/movimientos/{id}/auditoria", get_movimiento_auditoria, methods=["GET"]),
    Route("/api/salidas/atenciones/motivos", get_motivos, methods=["GET"]),
    Route("/api/salidas/atenciones/motivos", post_motivo, methods=["POST"]),
    Route("/api/salidas/atenciones/motivos/{id}", put_motivo, methods=["PUT"]),
    Route("/api/salidas/atenciones/motivos/{id}", delete_motivo, methods=["DELETE"]),
    Route("/api/salidas/atenciones", post_atencion, methods=["POST"]),
    Route("/api/salidas/atenciones", get_atenciones, methods=["GET"]),
    Route("/api/salidas/atenciones/export", get_atenciones_export, methods=["GET"]),
    Route("/api/salidas/atenciones/kpi", get_atenciones_kpi, methods=["GET"]),
    Route("/api/salidas/diario/export", get_diario_export, methods=["GET"]),
    Route("/api/salidas/resumen-diario", get_resumen_diario, methods=["GET"]),
    Route("/api/salidas/remito/export", get_remito_export, methods=["GET"]),
    Route("/api/salidas/refresh", post_refresh, methods=["POST"]),
    Route("/api/salidas/sync-firebase", post_sync_firebase, methods=["POST"]),
]

# Maestro stock routes (if available) - alias bidirectional sync + audit history
if maestro_import is not None:
    _maestro_routes = [
        Route("/api/maestro-stock/import", maestro_import, methods=["POST"]),
        Route("/api/maestro-stock", maestro_list, methods=["GET"]),
        Route("/api/maestro-stock/import-log", maestro_import_log, methods=["GET"]),
        # diff must be before {id} generic to avoid capture, and before {codigo}/history
        Route("/api/maestro-stock/import-log/{id}/diff", maestro_import_diff, methods=["GET"]) if maestro_import_diff else None,
        Route("/api/maestro-stock/import-log/{id}", maestro_import_log_by_id, methods=["GET"]),
        Route("/api/maestro-stock/stats", maestro_stats, methods=["GET"]),
    ]
    # Filter None if import_diff not available (older import)
    _maestro_routes = [r for r in _maestro_routes if r is not None]
    if maestro_codigo_history is not None:
        _maestro_routes.append(Route("/api/maestro-stock/{codigo}/history", maestro_codigo_history, methods=["GET"]))
    if maestro_put_alias is not None:
        _maestro_routes.append(Route("/api/maestro-stock/{codigo}/alias", maestro_put_alias, methods=["PUT"]))
        # Alias via generic PUT with body {codigo, alias} for clients without path param
        # Provide both path variants: already have /{codigo}/alias
    if maestro_sync_alias is not None:
        _maestro_routes.append(Route("/api/maestro-stock/sync-alias", maestro_sync_alias, methods=["POST"]))
        # Legacy alias /sync
        _maestro_routes.append(Route("/api/maestro-stock/sync", maestro_sync_alias, methods=["POST"]))
    routes.extend(_maestro_routes)


@asynccontextmanager
async def lifespan(_app: Starlette):
    threading.Thread(target=_carga_inicial, name="salidas-load", daemon=True).start()
    iniciar_sync_background()
    try:
        iniciar_alias_sync_background()
    except Exception as e:
        log.warning("No se pudo iniciar alias sync background: %s", e)
    yield


app = Starlette(routes=routes, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=False)
