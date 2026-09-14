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
from starlette.responses import JSONResponse
from starlette.routing import Route

from config import PORT, cors_origins_list, data_path, maestro_path, maestro_writable
from firebase_sync import iniciar_sync_background
from service import (
    buscar_articulo,
    confirmar_devolucion,
    confirmar_salida,
    get_catalogos,
    health_payload,
    listar_movimientos,
    proyectar_stock,
    refresh_maestro,
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

    def work() -> dict:
        return listar_movimientos(
            desde=q.get("desde"),
            hasta=q.get("hasta"),
            limite=limite,
        )

    return await _run_json(work)


async def post_refresh(_: Request) -> JSONResponse:
    return await _run_json(refresh_maestro)


async def post_sync_firebase(_: Request) -> JSONResponse:
    return await _run_json(sync_firebase_ahora)


def _carga_inicial() -> None:
    try:
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
    Route("/api/salidas/proyectar", post_proyectar, methods=["POST"]),
    Route("/api/salidas/confirmar", post_confirmar, methods=["POST"]),
    Route("/api/salidas/devolucion", post_devolucion, methods=["POST"]),
    Route("/api/salidas/movimientos", get_movimientos, methods=["GET"]),
    Route("/api/salidas/refresh", post_refresh, methods=["POST"]),
    Route("/api/salidas/sync-firebase", post_sync_firebase, methods=["POST"]),
]


@asynccontextmanager
async def lifespan(_app: Starlette):
    threading.Thread(target=_carga_inicial, name="salidas-load", daemon=True).start()
    iniciar_sync_background()
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
