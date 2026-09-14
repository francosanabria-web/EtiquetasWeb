# -*- coding: utf-8 -*-
"""API Activos fuera de planta — Starlette (puerto 8016). Independiente de KPIs."""

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

from config import PORT, cors_origins_list, excel_path
from exports import Vista, activos_excel, activos_pdf, nombre_archivo
from service import activos_resumen
from store import ActivosStore, CargandoDatosError, RedNoDisponibleError
from excel_io import reescribir_formateado
from write_ops import marcar_regreso, restablecer_fuera

log = logging.getLogger("activos")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def _store() -> ActivosStore:
    s = ActivosStore.get()
    s.ensure_loaded()
    return s


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
    s = ActivosStore.get()
    if s._error_carga:
        return JSONResponse(
            {
                "estado": "error",
                "detail": s._error_carga,
                "archivo": s.archivo_ok,
                "path": str(excel_path()),
            },
            status_code=503,
        )
    if s.ultima_actualizacion is None:
        return JSONResponse(
            {
                "estado": "cargando",
                "archivo": s.archivo_ok,
                "path": str(excel_path()),
            },
            status_code=503,
        )
    return JSONResponse(
        {
            "estado": "ok",
            "service": "activos",
            "archivo": s.archivo_ok,
            "path": str(excel_path()),
            "ultima_actualizacion": s.timestamp_iso(),
        }
    )


async def get_resumen(_: Request) -> JSONResponse:
    return await _run_json(lambda: activos_resumen(_store()))


async def post_refresh(_: Request) -> JSONResponse:
    def work() -> dict:
        s = ActivosStore.get()
        ts = s.refresh()
        return {
            "mensaje": "Datos de activos recargados.",
            "timestamp": ts.astimezone().isoformat(),
        }

    return await _run_json(work)


async def _run_bytes(
    work: Callable[[], bytes], media_type: str, filename: str
) -> Response:
    try:
        data = await run_in_threadpool(work)
    except (CargandoDatosError, RedNoDisponibleError, FileNotFoundError) as e:
        return _err(e, 503)
    except Exception as e:
        log.exception("Error export")
        return _err(e, 500)
    return Response(
        data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _vista_export(request: Request) -> Vista:
    raw = (request.query_params.get("vista") or "fuera").strip().lower()
    return "ingresados" if raw in ("ingresados", "ingresado", "ing") else "fuera"


async def export_excel(request: Request) -> Response:
    vista = _vista_export(request)
    return await _run_bytes(
        lambda: activos_excel(_store(), vista),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        nombre_archivo(vista, "xlsx"),
    )


async def export_pdf(request: Request) -> Response:
    vista = _vista_export(request)
    return await _run_bytes(
        lambda: activos_pdf(_store(), vista),
        "application/pdf",
        nombre_archivo(vista, "pdf"),
    )


async def post_marcar_regreso(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return _err(ValueError("JSON inválido."), 400)
    if not isinstance(body, dict):
        return _err(ValueError("JSON inválido."), 400)
    ids = body.get("ids") or []
    if not isinstance(ids, list):
        return _err(ValueError("ids debe ser una lista."), 400)
    fecha = str(body.get("fecha_regreso") or "").strip()
    estado = str(body.get("estado_al_ingreso") or "").strip()

    def work() -> dict:
        return marcar_regreso([str(x) for x in ids], fecha, estado)

    return await _run_json(work)


async def post_restablecer_fuera(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return _err(ValueError("JSON inválido."), 400)
    if not isinstance(body, dict):
        return _err(ValueError("JSON inválido."), 400)
    ids = body.get("ids") or []
    if not isinstance(ids, list):
        return _err(ValueError("ids debe ser una lista."), 400)

    def work() -> dict:
        return restablecer_fuera([str(x) for x in ids])

    return await _run_json(work)


async def post_reescribir_formato(_: Request) -> JSONResponse:
    """Reaplica formato de escritorio sin cambiar filas (útil tras un guardado plano)."""
    return await _run_json(reescribir_formateado)


def _carga_inicial() -> None:
    try:
        ActivosStore.get().refresh()
        log.info("Activos cargados desde %s", excel_path())
    except Exception as e:
        ActivosStore.get().registrar_error_carga(str(e))
        log.warning("Carga inicial fallida: %s", e)


routes = [
    Route("/health", health, methods=["GET"]),
    Route("/api/activos/health", health, methods=["GET"]),
    Route("/api/activos/resumen", get_resumen, methods=["GET"]),
    Route("/api/activos/refresh", post_refresh, methods=["POST"]),
    Route("/api/activos/export.xlsx", export_excel, methods=["GET"]),
    Route("/api/activos/export.pdf", export_pdf, methods=["GET"]),
    Route("/api/activos/marcar-regreso", post_marcar_regreso, methods=["POST"]),
    Route("/api/activos/restablecer-fuera", post_restablecer_fuera, methods=["POST"]),
    Route("/api/activos/reescribir-formato", post_reescribir_formato, methods=["POST"]),
]


@asynccontextmanager
async def lifespan(_app: Starlette):
    threading.Thread(target=_carga_inicial, name="activos-load", daemon=True).start()
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
