# -*- coding: utf-8 -*-
"""API de minutas por sector — pedidos, novedades e historial (Starlette)."""

from __future__ import annotations

import json
import os

from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

import db

db.init_db()


async def health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "minuta-reunion"})


async def get_sectores(_: Request) -> JSONResponse:
    return JSONResponse({"sectores": db.listar_sectores()})


async def get_pedidos(request: Request) -> JSONResponse:
    reunion_id = (request.query_params.get("reunion_id") or "").strip()
    sector = (request.query_params.get("sector") or "").strip()
    solo_activos = request.query_params.get("activos", "1") != "0"
    try:
        if reunion_id:
            pedidos = db.listar_pedidos_reunion(int(reunion_id), solo_activos=solo_activos)
        elif sector:
            pedidos = db.listar_pedidos_sector(sector, solo_activos=solo_activos)
        else:
            return JSONResponse(
                {"detail": "reunion_id o sector requerido."}, status_code=400
            )
        return JSONResponse({"pedidos": pedidos})
    except Exception as e:
        return JSONResponse({"detail": str(e)}, status_code=400)


async def get_pedido(request: Request) -> JSONResponse:
    pedido_id = int(request.path_params["id"])
    pedido = db.obtener_pedido(pedido_id)
    if not pedido:
        return JSONResponse({"detail": "Pedido no encontrado."}, status_code=404)
    return JSONResponse({"pedido": pedido})


async def post_pedido(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"detail": "JSON inválido."}, status_code=400)
    try:
        pedido = db.crear_pedido(body)
        return JSONResponse({"pedido": pedido}, status_code=201)
    except ValueError as e:
        return JSONResponse({"detail": str(e)}, status_code=400)


async def patch_pedido(request: Request) -> JSONResponse:
    pedido_id = int(request.path_params["id"])
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"detail": "JSON inválido."}, status_code=400)
    pedido = db.actualizar_pedido(pedido_id, body)
    if not pedido:
        return JSONResponse({"detail": "Pedido no encontrado."}, status_code=404)
    return JSONResponse({"pedido": pedido})


async def delete_pedido(request: Request) -> JSONResponse:
    pedido_id = int(request.path_params["id"])
    ok = db.eliminar_pedido(pedido_id)
    if not ok:
        return JSONResponse({"detail": "Pedido no encontrado."}, status_code=404)
    return JSONResponse({"ok": True})


async def post_novedad(request: Request) -> JSONResponse:
    pedido_id = int(request.path_params["id"])
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"detail": "JSON inválido."}, status_code=400)
    try:
        pedido = db.agregar_novedad(pedido_id, body)
    except ValueError as e:
        return JSONResponse({"detail": str(e)}, status_code=400)
    if not pedido:
        return JSONResponse({"detail": "Pedido no encontrado."}, status_code=404)
    return JSONResponse({"pedido": pedido}, status_code=201)


async def post_reordenar(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"detail": "JSON inválido."}, status_code=400)
    reunion_id = body.get("reunion_id")
    ids = body.get("ids")
    if not reunion_id or not isinstance(ids, list):
        return JSONResponse(
            {"detail": "reunion_id e ids (lista) requeridos."}, status_code=400
        )
    try:
        pedidos = db.reordenar_pedidos(int(reunion_id), [int(i) for i in ids])
        return JSONResponse({"pedidos": pedidos})
    except (ValueError, TypeError) as e:
        return JSONResponse({"detail": str(e)}, status_code=400)


async def post_limpiar_consultas(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"detail": "JSON inválido."}, status_code=400)
    reunion_id = body.get("reunion_id")
    sector = str(body.get("sector") or "").strip()
    if reunion_id:
        afectados = db.limpiar_consultas_reunion(int(reunion_id))
        return JSONResponse({"afectados": afectados})
    if not sector:
        return JSONResponse({"detail": "reunion_id o sector requerido."}, status_code=400)
    afectados = db.limpiar_consultas_sector(sector)
    return JSONResponse({"afectados": afectados})


async def post_finalizar(request: Request) -> JSONResponse:
    pedido_id = int(request.path_params["id"])
    try:
        body = await request.json()
    except json.JSONDecodeError:
        body = {}
    try:
        pedido = db.finalizar_pedido(pedido_id, body if isinstance(body, dict) else {})
    except ValueError as e:
        return JSONResponse({"detail": str(e)}, status_code=400)
    if not pedido:
        return JSONResponse({"detail": "Pedido no encontrado."}, status_code=404)
    return JSONResponse({"pedido": pedido})


async def post_reactivar(request: Request) -> JSONResponse:
    pedido_id = int(request.path_params["id"])
    pedido = db.reactivar_pedido(pedido_id)
    if not pedido:
        return JSONResponse({"detail": "Pedido no encontrado."}, status_code=404)
    return JSONResponse({"pedido": pedido})


async def get_reuniones(request: Request) -> JSONResponse:
    sector = (request.query_params.get("sector") or "").strip() or None
    owner = (request.query_params.get("owner") or "").strip() or None
    solo_enviadas = request.query_params.get("enviadas", "0") == "1"
    arch = (request.query_params.get("archivadas") or "0").strip().lower()
    if arch in ("1", "true", "yes"):
        archivadas: bool | None = True
    elif arch in ("all", "todas", "*"):
        archivadas = None
    else:
        archivadas = False
    limite = int(request.query_params.get("limite") or "50")
    reuniones = db.listar_reuniones(
        sector=sector,
        owner_email=owner,
        solo_enviadas=solo_enviadas,
        archivadas=archivadas,
        limite=limite,
    )
    return JSONResponse({"reuniones": reuniones})


async def get_reunion(request: Request) -> JSONResponse:
    reunion_id = int(request.path_params["id"])
    reunion = db.obtener_reunion(reunion_id)
    if not reunion:
        return JSONResponse({"detail": "Reunión no encontrada."}, status_code=404)
    return JSONResponse({"reunion": reunion})


async def post_reunion(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"detail": "JSON inválido."}, status_code=400)
    # Si vienen campos de reunión tipada → crear; si solo sector+fecha → obtener/crear legacy
    if body.get("titulo") or body.get("tipo") or body.get("visibilidad") or body.get("owner_email"):
        try:
            reunion = db.crear_reunion(body)
            return JSONResponse({"reunion": reunion}, status_code=201)
        except ValueError as e:
            return JSONResponse({"detail": str(e)}, status_code=400)
    sector = str(body.get("sector") or "").strip()
    fecha = str(body.get("fecha") or "").strip()
    if not sector or not fecha:
        return JSONResponse({"detail": "sector y fecha requeridos."}, status_code=400)
    try:
        reunion = db.obtener_o_crear_reunion(sector, fecha)
        return JSONResponse({"reunion": reunion})
    except Exception as e:
        return JSONResponse({"detail": str(e)}, status_code=400)


async def patch_reunion(request: Request) -> JSONResponse:
    reunion_id = int(request.path_params["id"])
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"detail": "JSON inválido."}, status_code=400)
    try:
        reunion = db.actualizar_reunion(reunion_id, body)
    except ValueError as e:
        return JSONResponse({"detail": str(e)}, status_code=400)
    if not reunion:
        return JSONResponse({"detail": "Reunión no encontrada."}, status_code=404)
    return JSONResponse({"reunion": reunion})


async def delete_reunion(request: Request) -> JSONResponse:
    reunion_id = int(request.path_params["id"])
    if not db.eliminar_reunion(reunion_id):
        return JSONResponse({"detail": "Reunión no encontrada."}, status_code=404)
    return JSONResponse({"ok": True})


async def post_mover_pedidos(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"detail": "JSON inválido."}, status_code=400)
    try:
        origen = int(body.get("origen_id") or 0)
        destino = int(body.get("destino_id") or 0)
    except (TypeError, ValueError):
        return JSONResponse({"detail": "origen_id y destino_id requeridos."}, status_code=400)
    try:
        n = db.mover_pedidos_reunion(origen, destino)
        return JSONResponse({"movidos": n})
    except ValueError as e:
        return JSONResponse({"detail": str(e)}, status_code=400)


async def reunion_por_id(request: Request) -> JSONResponse:
    """GET / PATCH / DELETE sobre /api/minuta/reuniones/{id}."""
    if request.method == "GET":
        return await get_reunion(request)
    if request.method == "PATCH":
        return await patch_reunion(request)
    if request.method == "DELETE":
        return await delete_reunion(request)
    return JSONResponse({"detail": "Método no permitido."}, status_code=405)


async def get_novedades_reunion(request: Request) -> JSONResponse:
    sector = (request.query_params.get("sector") or "").strip()
    fecha = (request.query_params.get("fecha") or "").strip()
    if not sector or not fecha:
        return JSONResponse({"detail": "sector y fecha requeridos."}, status_code=400)
    novedades = db.novedades_reunion_sector(sector, fecha)
    return JSONResponse({"novedades": novedades})


_origins = os.environ.get("MINUTA_CORS_ORIGINS", "*").strip()
_allow = ["*"] if _origins == "*" else [o.strip() for o in _origins.split(",") if o.strip()]

app = Starlette(
    routes=[
        Route("/health", health, methods=["GET"]),
        Route("/api/minuta/sectores", get_sectores, methods=["GET"]),
        Route("/api/minuta/pedidos", get_pedidos, methods=["GET"]),
        Route("/api/minuta/pedidos", post_pedido, methods=["POST"]),
        Route("/api/minuta/pedidos/reordenar", post_reordenar, methods=["POST"]),
        Route("/api/minuta/pedidos/limpiar-consultas", post_limpiar_consultas, methods=["POST"]),
        Route("/api/minuta/pedidos/{id:int}", get_pedido, methods=["GET"]),
        Route("/api/minuta/pedidos/{id:int}", patch_pedido, methods=["PATCH"]),
        Route("/api/minuta/pedidos/{id:int}", delete_pedido, methods=["DELETE"]),
        Route("/api/minuta/pedidos/{id:int}/novedades", post_novedad, methods=["POST"]),
        Route("/api/minuta/pedidos/{id:int}/finalizar", post_finalizar, methods=["POST"]),
        Route("/api/minuta/pedidos/{id:int}/reactivar", post_reactivar, methods=["POST"]),
        Route("/api/minuta/reuniones", get_reuniones, methods=["GET"]),
        Route("/api/minuta/reuniones", post_reunion, methods=["POST"]),
        Route("/api/minuta/reuniones/mover-pedidos", post_mover_pedidos, methods=["POST"]),
        Route(
            "/api/minuta/reuniones/{id:int}",
            reunion_por_id,
            methods=["GET", "PATCH", "DELETE"],
        ),
        Route("/api/minuta/novedades-reunion", get_novedades_reunion, methods=["GET"]),
    ],
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow,
    allow_methods=["*"],
    allow_headers=["*"],
)
