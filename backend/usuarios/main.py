# -*- coding: utf-8 -*-
"""API Usuarios / accesos — Starlette + SQLite (puerto 8015).

MVP en LAN: login real, gestión de usuarios y permisos por usuario.
La gestión requiere sesión de un usuario con rol admin. Los demás servicios
(minuta, solicitudes, kpis, …) siguen confiando en la red interna por ahora.
"""

from __future__ import annotations

import json

from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

import db
from config import MODULOS, NIVELES, PLANTILLAS_ROL, PORT, ROLES, cors_origins_list

db.init_db()


def _token(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.headers.get("x-token", "").strip()


def _actor(request: Request) -> dict | None:
    return db.usuario_por_token(_token(request))


async def health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "usuarios"})


async def get_catalogo(_: Request) -> JSONResponse:
    return JSONResponse(
        {"modulos": MODULOS, "roles": ROLES, "niveles": NIVELES, "plantillas": PLANTILLAS_ROL}
    )


async def post_login(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"detail": "JSON inválido."}, status_code=400)
    usuario = str((body or {}).get("usuario") or "")
    clave = str((body or {}).get("clave") or "")
    u = db.autenticar(usuario, clave)
    if not u:
        return JSONResponse({"detail": "Usuario o contraseña incorrectos."}, status_code=401)
    token = db.crear_sesion(u["id"])
    return JSONResponse({"token": token, "usuario": u})


async def post_logout(request: Request) -> JSONResponse:
    db.borrar_sesion(_token(request))
    return JSONResponse({"ok": True})


async def get_me(request: Request) -> JSONResponse:
    u = _actor(request)
    if not u:
        return JSONResponse({"detail": "Sesión inválida o vencida."}, status_code=401)
    return JSONResponse({"usuario": u})


async def post_mi_password(request: Request) -> JSONResponse:
    u = _actor(request)
    if not u:
        return JSONResponse({"detail": "Sesión inválida o vencida."}, status_code=401)
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"detail": "JSON inválido."}, status_code=400)
    try:
        db.cambiar_mi_password(u["id"], str(body.get("actual") or ""), str(body.get("nueva") or ""))
    except ValueError as e:
        return JSONResponse({"detail": str(e)}, status_code=400)
    return JSONResponse({"ok": True})


def _require_admin(request: Request):
    u = _actor(request)
    if not u:
        return None, JSONResponse({"detail": "Sesión inválida o vencida."}, status_code=401)
    if u.get("rol") != "admin":
        return None, JSONResponse({"detail": "Requiere rol administrador."}, status_code=403)
    return u, None


async def get_usuarios(request: Request) -> JSONResponse:
    _, err = _require_admin(request)
    if err:
        return err
    return JSONResponse({"usuarios": db.listar_usuarios()})


async def post_usuarios(request: Request) -> JSONResponse:
    _, err = _require_admin(request)
    if err:
        return err
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"detail": "JSON inválido."}, status_code=400)
    try:
        u = db.crear_usuario(body if isinstance(body, dict) else {})
        return JSONResponse({"usuario": u}, status_code=201)
    except ValueError as e:
        return JSONResponse({"detail": str(e)}, status_code=400)


async def patch_usuario(request: Request) -> JSONResponse:
    _, err = _require_admin(request)
    if err:
        return err
    uid = int(request.path_params["id"])
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"detail": "JSON inválido."}, status_code=400)
    actual = db.obtener_usuario(uid)
    if not actual:
        return JSONResponse({"detail": "Usuario no encontrado."}, status_code=404)
    # No dejar al sistema sin ningún admin activo.
    if actual["rol"] == "admin":
        quita_admin = ("rol" in body and str(body["rol"]).lower() != "admin") or (
            "activo" in body and not body["activo"]
        )
        if quita_admin and db.contar_admins_activos(excluir_id=uid) == 0:
            return JSONResponse(
                {"detail": "Debe quedar al menos un administrador activo."}, status_code=400
            )
    try:
        u = db.actualizar_usuario(uid, body if isinstance(body, dict) else {})
    except ValueError as e:
        return JSONResponse({"detail": str(e)}, status_code=400)
    return JSONResponse({"usuario": u})


async def post_usuario_password(request: Request) -> JSONResponse:
    _, err = _require_admin(request)
    if err:
        return err
    uid = int(request.path_params["id"])
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"detail": "JSON inválido."}, status_code=400)
    try:
        ok = db.set_password(uid, str(body.get("nueva") or ""))
    except ValueError as e:
        return JSONResponse({"detail": str(e)}, status_code=400)
    if not ok:
        return JSONResponse({"detail": "Usuario no encontrado."}, status_code=404)
    return JSONResponse({"ok": True})


async def delete_usuario(request: Request) -> JSONResponse:
    actor, err = _require_admin(request)
    if err:
        return err
    uid = int(request.path_params["id"])
    if actor["id"] == uid:
        return JSONResponse({"detail": "No podés eliminar tu propio usuario."}, status_code=400)
    actual = db.obtener_usuario(uid)
    if not actual:
        return JSONResponse({"detail": "Usuario no encontrado."}, status_code=404)
    if actual["rol"] == "admin" and db.contar_admins_activos(excluir_id=uid) == 0:
        return JSONResponse(
            {"detail": "Debe quedar al menos un administrador activo."}, status_code=400
        )
    db.eliminar_usuario(uid)
    return JSONResponse({"ok": True})


app = Starlette(
    routes=[
        Route("/health", health, methods=["GET"]),
        Route("/api/usuarios/health", health, methods=["GET"]),
        Route("/api/usuarios/catalogo", get_catalogo, methods=["GET"]),
        Route("/api/usuarios/login", post_login, methods=["POST"]),
        Route("/api/usuarios/logout", post_logout, methods=["POST"]),
        Route("/api/usuarios/me", get_me, methods=["GET"]),
        Route("/api/usuarios/mi-password", post_mi_password, methods=["POST"]),
        Route("/api/usuarios", get_usuarios, methods=["GET"]),
        Route("/api/usuarios", post_usuarios, methods=["POST"]),
        Route("/api/usuarios/{id:int}", patch_usuario, methods=["PATCH"]),
        Route("/api/usuarios/{id:int}", delete_usuario, methods=["DELETE"]),
        Route("/api/usuarios/{id:int}/password", post_usuario_password, methods=["POST"]),
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
