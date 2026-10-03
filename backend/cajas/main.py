# -*- coding: utf-8 -*-
"""API Cajas de Herramientas — Starlette + MariaDB (puerto 8021).

Microservice dedicado a gestión de cajas y herramientas en MariaDB.
Endpoints CRUD con autenticación JWT Bearer y permisos por módulo.
"""

from __future__ import annotations

import json

from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

import db
import service
from config import PORT, cors_origins_list

db.init_db()


def _token(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.headers.get("x-token", "").strip()


async def health(_: Request) -> JSONResponse:
    return JSONResponse(service.health_payload())


async def get_cajas(request: Request) -> JSONResponse:
    result = service.get_cajas_list(_token(request), dict(request.query_params))
    if isinstance(result, tuple):
        msg, status = result
        return JSONResponse({"detail": msg}, status_code=status)
    return JSONResponse(result)


async def get_caja_by_id(request: Request) -> JSONResponse:
    pid = int(request.path_params["id"])
    result = service.get_caja_by_id(_token(request), pid)
    if isinstance(result, tuple):
        msg, status = result
        return JSONResponse({"detail": msg}, status_code=status)
    return JSONResponse(result)


async def post_caja(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"detail": "JSON inválido."}, status_code=400)
    result = service.create_caja(_token(request), body if isinstance(body, dict) else {})
    if isinstance(result, tuple):
        msg, status = result
        return JSONResponse({"detail": msg}, status_code=status)
    return JSONResponse(result, status_code=201)


async def patch_caja(request: Request) -> JSONResponse:
    pid = int(request.path_params["id"])
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"detail": "JSON inválido."}, status_code=400)
    result = service.update_caja(_token(request), pid, body if isinstance(body, dict) else {})
    if isinstance(result, tuple):
        msg, status = result
        return JSONResponse({"detail": msg}, status_code=status)
    return JSONResponse(result)


async def delete_caja(request: Request) -> JSONResponse:
    pid = int(request.path_params["id"])
    result = service.delete_caja(_token(request), pid)
    if isinstance(result, tuple):
        msg, status = result
        return JSONResponse({"detail": msg}, status_code=status)
    return JSONResponse(result)


async def get_herramientas(request: Request) -> JSONResponse:
    result = service.get_herramientas_list(_token(request), dict(request.query_params))
    if isinstance(result, tuple):
        msg, status = result
        return JSONResponse({"detail": msg}, status_code=status)
    return JSONResponse(result)


async def get_herramienta_by_id(request: Request) -> JSONResponse:
    pid = int(request.path_params["id"])
    result = service.get_herramienta_by_id(_token(request), pid)
    if isinstance(result, tuple):
        msg, status = result
        return JSONResponse({"detail": msg}, status_code=status)
    return JSONResponse(result)


async def post_herramienta(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"detail": "JSON inválido."}, status_code=400)
    result = service.create_herramienta(_token(request), body if isinstance(body, dict) else {})
    if isinstance(result, tuple):
        msg, status = result
        return JSONResponse({"detail": msg}, status_code=status)
    return JSONResponse(result, status_code=201)


async def patch_herramienta(request: Request) -> JSONResponse:
    pid = int(request.path_params["id"])
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"detail": "JSON inválido."}, status_code=400)
    result = service.update_herramienta(_token(request), pid, body if isinstance(body, dict) else {})
    if isinstance(result, tuple):
        msg, status = result
        return JSONResponse({"detail": msg}, status_code=status)
    return JSONResponse(result)


async def delete_herramienta(request: Request) -> JSONResponse:
    pid = int(request.path_params["id"])
    result = service.delete_herramienta(_token(request), pid)
    if isinstance(result, tuple):
        msg, status = result
        return JSONResponse({"detail": msg}, status_code=status)
    return JSONResponse(result)


async def get_inventarios(request: Request) -> JSONResponse:
    result = service.get_inventarios_list(_token(request), dict(request.query_params))
    if isinstance(result, tuple):
        msg, status = result
        return JSONResponse({"detail": msg}, status_code=status)
    return JSONResponse(result)


async def get_inventario_by_id(request: Request) -> JSONResponse:
    pid = int(request.path_params["id"])
    result = service.get_inventario_by_id(_token(request), pid)
    if isinstance(result, tuple):
        msg, status = result
        return JSONResponse({"detail": msg}, status_code=status)
    return JSONResponse(result)


async def post_inventario(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"detail": "JSON inválido."}, status_code=400)
    result = service.create_inventario(_token(request), body if isinstance(body, dict) else {})
    if isinstance(result, tuple):
        msg, status = result
        return JSONResponse({"detail": msg}, status_code=status)
    return JSONResponse(result, status_code=201)


async def patch_inventario_estado(request: Request) -> JSONResponse:
    pid = int(request.path_params["id"])
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"detail": "JSON inválido."}, status_code=400)
    estado = body.get("estado") if isinstance(body, dict) else None
    if not estado:
        return JSONResponse({"detail": "estado es obligatorio."}, status_code=400)
    result = service.update_inventario_estado(_token(request), pid, estado)
    if isinstance(result, tuple):
        msg, status = result
        return JSONResponse({"detail": msg}, status_code=status)
    return JSONResponse(result)


async def delete_inventario(request: Request) -> JSONResponse:
    pid = int(request.path_params["id"])
    result = service.delete_inventario(_token(request), pid)
    if isinstance(result, tuple):
        msg, status = result
        return JSONResponse({"detail": msg}, status_code=status)
    return JSONResponse(result)


# -- Caja Ideal (versionado) --
async def get_ideal(request: Request) -> JSONResponse:
    result = service.get_ideal(_token(request), dict(request.query_params))
    if isinstance(result, tuple):
        msg, status = result
        return JSONResponse({"detail": msg}, status_code=status)
    return JSONResponse(result)


async def put_ideal(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"detail": "JSON inválido."}, status_code=400)
    result = service.put_ideal(_token(request), body if isinstance(body, dict) else {})
    if isinstance(result, tuple):
        msg, status = result
        return JSONResponse({"detail": msg}, status_code=status)
    return JSONResponse(result, status_code=201)


async def get_ideal_versiones(request: Request) -> JSONResponse:
    result = service.get_ideal_versiones(_token(request), dict(request.query_params))
    if isinstance(result, tuple):
        msg, status = result
        return JSONResponse({"detail": msg}, status_code=status)
    return JSONResponse(result)


# -- Tecnicos-Cards + Historial + KPIs (Slice 2) --
async def get_tecnicos_cards(request: Request) -> JSONResponse:
    result = service.get_tecnicos_cards(_token(request), dict(request.query_params))
    if isinstance(result, tuple):
        msg, status = result
        return JSONResponse({"detail": msg}, status_code=status)
    return JSONResponse(result)


async def get_inventarios_por_tecnico(request: Request) -> JSONResponse:
    pid = int(request.path_params["id"])
    result = service.get_inventarios_por_tecnico(_token(request), pid, dict(request.query_params))
    if isinstance(result, tuple):
        msg, status = result
        return JSONResponse({"detail": msg}, status_code=status)
    return JSONResponse(result)


async def get_kpis_resumen(request: Request) -> JSONResponse:
    result = service.get_kpis_resumen(_token(request), dict(request.query_params))
    if isinstance(result, tuple):
        msg, status = result
        return JSONResponse({"detail": msg}, status_code=status)
    return JSONResponse(result)


async def get_kpis_por_tecnico(request: Request) -> JSONResponse:
    pid = int(request.path_params["id"])
    result = service.get_kpis_por_tecnico(_token(request), pid)
    if isinstance(result, tuple):
        msg, status = result
        return JSONResponse({"detail": msg}, status_code=status)
    return JSONResponse(result)


# -- Limpieza Historial (Fase 2) --
async def get_limpieza(request: Request) -> JSONResponse:
    result = service.get_limpieza_list(_token(request), dict(request.query_params))
    if isinstance(result, tuple):
        msg, status = result
        return JSONResponse({"detail": msg}, status_code=status)
    return JSONResponse(result)


async def post_limpieza(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"detail": "JSON inválido."}, status_code=400)
    result = service.create_limpieza(_token(request), body if isinstance(body, dict) else {})
    if isinstance(result, tuple):
        msg, status = result
        return JSONResponse({"detail": msg}, status_code=status)
    return JSONResponse(result, status_code=201)


async def patch_limpieza_estado(request: Request) -> JSONResponse:
    pid = int(request.path_params["id"])
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"detail": "JSON inválido."}, status_code=400)
    result = service.update_limpieza_estado(_token(request), pid, body if isinstance(body, dict) else {})
    if isinstance(result, tuple):
        msg, status = result
        return JSONResponse({"detail": msg}, status_code=status)
    return JSONResponse(result)


async def delete_limpieza(request: Request) -> JSONResponse:
    pid = int(request.path_params["id"])
    result = service.delete_limpieza(_token(request), pid)
    if isinstance(result, tuple):
        msg, status = result
        return JSONResponse({"detail": msg}, status_code=status)
    return JSONResponse(result)


# -- Asignaciones (Fase 2) --
async def get_asignaciones(request: Request) -> JSONResponse:
    result = service.get_asignaciones_list(_token(request), dict(request.query_params))
    if isinstance(result, tuple):
        msg, status = result
        return JSONResponse({"detail": msg}, status_code=status)
    return JSONResponse(result)


async def post_asignacion(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"detail": "JSON inválido."}, status_code=400)
    result = service.create_asignacion(_token(request), body if isinstance(body, dict) else {})
    if isinstance(result, tuple):
        msg, status = result
        return JSONResponse({"detail": msg}, status_code=status)
    return JSONResponse(result, status_code=201)


async def patch_asignacion_cerrar(request: Request) -> JSONResponse:
    pid = int(request.path_params["id"])
    result = service.cerrar_asignacion(_token(request), pid)
    if isinstance(result, tuple):
        msg, status = result
        return JSONResponse({"detail": msg}, status_code=status)
    return JSONResponse(result)


async def get_recomendar_codigo(request: Request) -> JSONResponse:
    result = service.get_recomendacion_codigo(_token(request), dict(request.query_params))
    if isinstance(result, tuple):
        msg, status = result
        # msg puede ser dict con detail
        if isinstance(msg, dict):
            return JSONResponse(msg, status_code=status)
        return JSONResponse({"detail": msg}, status_code=status)
    return JSONResponse(result)


app = Starlette(
    routes=[
        Route("/health", health, methods=["GET"]),
        Route("/api/cajas/cajas", get_cajas, methods=["GET"]),
        Route("/api/cajas/cajas/{id:int}", get_caja_by_id, methods=["GET"]),
        Route("/api/cajas/cajas", post_caja, methods=["POST"]),
        Route("/api/cajas/cajas/{id:int}", patch_caja, methods=["PATCH"]),
        Route("/api/cajas/cajas/{id:int}", delete_caja, methods=["DELETE"]),
        Route("/api/cajas/herramientas/recomendar-codigo", get_recomendar_codigo, methods=["GET"]),
        Route("/api/cajas/herramientas", get_herramientas, methods=["GET"]),
        Route("/api/cajas/herramientas/{id:int}", get_herramienta_by_id, methods=["GET"]),
        Route("/api/cajas/herramientas", post_herramienta, methods=["POST"]),
        Route("/api/cajas/herramientas/{id:int}", patch_herramienta, methods=["PATCH"]),
        Route("/api/cajas/herramientas/{id:int}", delete_herramienta, methods=["DELETE"]),
        Route("/api/cajas/inventarios", get_inventarios, methods=["GET"]),
        Route("/api/cajas/inventarios/{id:int}", get_inventario_by_id, methods=["GET"]),
        Route("/api/cajas/inventarios", post_inventario, methods=["POST"]),
        Route("/api/cajas/inventarios/{id:int}/estado", patch_inventario_estado, methods=["PATCH"]),
        Route("/api/cajas/inventarios/{id:int}", delete_inventario, methods=["DELETE"]),
        Route("/api/cajas/ideal", get_ideal, methods=["GET"]),
        Route("/api/cajas/ideal", put_ideal, methods=["PUT"]),
        Route("/api/cajas/ideal/versiones", get_ideal_versiones, methods=["GET"]),
        Route("/api/cajas/tecnicos-cards", get_tecnicos_cards, methods=["GET"]),
        Route("/api/cajas/tecnicos/{id:int}/inventarios", get_inventarios_por_tecnico, methods=["GET"]),
        Route("/api/cajas/kpis/resumen", get_kpis_resumen, methods=["GET"]),
        Route("/api/cajas/kpis/tecnico/{id:int}", get_kpis_por_tecnico, methods=["GET"]),
        Route("/api/cajas/limpieza", get_limpieza, methods=["GET"]),
        Route("/api/cajas/limpieza", post_limpieza, methods=["POST"]),
        Route("/api/cajas/limpieza/{id:int}/estado", patch_limpieza_estado, methods=["PATCH"]),
        Route("/api/cajas/limpieza/{id:int}", delete_limpieza, methods=["DELETE"]),
        Route("/api/cajas/asignaciones", get_asignaciones, methods=["GET"]),
        Route("/api/cajas/asignaciones", post_asignacion, methods=["POST"]),
        Route("/api/cajas/asignaciones/{id:int}/cerrar", patch_asignacion_cerrar, methods=["PATCH"]),
    ],
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins_list(),
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)
