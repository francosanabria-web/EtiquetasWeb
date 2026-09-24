# -*- coding: utf-8 -*-
"""API Personal / áreas — Starlette + MariaDB (puerto 8019).

Microservice dedicado a gestión de personal y áreas en MariaDB.
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


async def get_areas(request: Request) -> JSONResponse:
    result = service.get_areas(_token(request))
    if isinstance(result, tuple):
        msg, status = result
        return JSONResponse({"detail": msg}, status_code=status)
    return JSONResponse(result)


async def get_personal_list(request: Request) -> JSONResponse:
    result = service.get_personal_list(_token(request), dict(request.query_params))
    if isinstance(result, tuple):
        msg, status = result
        return JSONResponse({"detail": msg}, status_code=status)
    return JSONResponse(result)


async def get_personal_by_id(request: Request) -> JSONResponse:
    pid = int(request.path_params["id"])
    result = service.get_personal_by_id(_token(request), pid)
    if isinstance(result, tuple):
        msg, status = result
        return JSONResponse({"detail": msg}, status_code=status)
    return JSONResponse(result)


async def get_personal_mail_prefs(request: Request) -> JSONResponse:
    pid = int(request.path_params["id"])
    result = service.get_personal_mail_prefs(_token(request), pid)
    if isinstance(result, tuple):
        msg, status = result
        return JSONResponse({"detail": msg}, status_code=status)
    return JSONResponse(result)


async def put_personal_mail_prefs(request: Request) -> JSONResponse:
    pid = int(request.path_params["id"])
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"detail": "JSON inválido."}, status_code=400)
    if not isinstance(body, dict):
        return JSONResponse({"detail": "Body debe ser un objeto."}, status_code=400)
    prefs = {k: bool(v) for k, v in body.items()}
    result = service.set_personal_mail_prefs(_token(request), pid, prefs)
    if isinstance(result, tuple):
        msg, status = result
        return JSONResponse({"detail": msg}, status_code=status)
    return JSONResponse(result)


async def get_all_personal_mail_prefs(request: Request) -> JSONResponse:
    result = service.list_all_personal_mail_prefs(_token(request))
    if isinstance(result, tuple):
        msg, status = result
        return JSONResponse({"detail": msg}, status_code=status)
    return JSONResponse(result)


async def post_personal(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"detail": "JSON inválido."}, status_code=400)
    result = service.create_personal(_token(request), body if isinstance(body, dict) else {})
    if isinstance(result, tuple):
        msg, status = result
        return JSONResponse({"detail": msg}, status_code=status)
    return JSONResponse(result, status_code=201)


async def patch_personal(request: Request) -> JSONResponse:
    pid = int(request.path_params["id"])
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"detail": "JSON inválido."}, status_code=400)
    result = service.update_personal(_token(request), pid, body if isinstance(body, dict) else {})
    if isinstance(result, tuple):
        msg, status = result
        return JSONResponse({"detail": msg}, status_code=status)
    return JSONResponse(result)


async def delete_personal(request: Request) -> JSONResponse:
    pid = int(request.path_params["id"])
    result = service.delete_personal(_token(request), pid)
    if isinstance(result, tuple):
        msg, status = result
        return JSONResponse({"detail": msg}, status_code=status)
    return JSONResponse(result)


app = Starlette(
    routes=[
        Route("/health", health, methods=["GET"]),
        Route("/api/areas", get_areas, methods=["GET"]),
        Route("/api/personal", get_personal_list, methods=["GET"]),
        Route("/api/personal/{id:int}", get_personal_by_id, methods=["GET"]),
        Route("/api/personal/{id:int}/mail-prefs", get_personal_mail_prefs, methods=["GET"]),
        Route("/api/personal/{id:int}/mail-prefs", put_personal_mail_prefs, methods=["PUT"]),
        Route("/api/personal/mail-prefs", get_all_personal_mail_prefs, methods=["GET"]),
        Route("/api/personal", post_personal, methods=["POST"]),
        Route("/api/personal/{id:int}", patch_personal, methods=["PATCH"]),
        Route("/api/personal/{id:int}", delete_personal, methods=["DELETE"]),
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
