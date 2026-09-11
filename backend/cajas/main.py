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


app = Starlette(
    routes=[
        Route("/health", health, methods=["GET"]),
        Route("/api/cajas/cajas", get_cajas, methods=["GET"]),
        Route("/api/cajas/cajas/{id:int}", get_caja_by_id, methods=["GET"]),
        Route("/api/cajas/cajas", post_caja, methods=["POST"]),
        Route("/api/cajas/cajas/{id:int}", patch_caja, methods=["PATCH"]),
        Route("/api/cajas/cajas/{id:int}", delete_caja, methods=["DELETE"]),
        Route("/api/cajas/herramientas", get_herramientas, methods=["GET"]),
        Route("/api/cajas/herramientas/{id:int}", get_herramienta_by_id, methods=["GET"]),
        Route("/api/cajas/herramientas", post_herramienta, methods=["POST"]),
        Route("/api/cajas/herramientas/{id:int}", patch_herramienta, methods=["PATCH"]),
        Route("/api/cajas/herramientas/{id:int}", delete_herramienta, methods=["DELETE"]),
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
