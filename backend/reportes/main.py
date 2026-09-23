# -*- coding: utf-8 -*-
"""API Reportes — consultas operativas de movimientos (puerto 8017).

Starlette (mismo stack que el resto del portal). Capa store/service lista
para migrar a SQL o API Salidas sin cambiar el contrato HTTP.
"""

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

from config import (
    PORT,
    REPORTES_DB_ENABLED,
    REPORTES_MAIL_DIARIO_ENABLED,
    REPORTES_MAIL_MENSUAL_ENABLED,
    cors_origins_list,
)
from mail_jobs import (
    MailNoConfiguradoError,
    dry_run_diario,
    mail_status,
    run_diario_si_habilitado,
    run_mensual_si_habilitado,
)
from service import export_csv, export_xlsx, listar_movimientos, opciones_filtros, resumen_movimientos
from store import CargandoDatosError, RedNoDisponibleError, ReportesStore

log = logging.getLogger("reportes")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def _store() -> ReportesStore:
    s = ReportesStore.get()
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
    except ValueError as e:
        return _err(e, 400)
    except Exception as e:
        log.exception("Error en endpoint")
        return _err(e, 500)
    return JSONResponse(data, status_code=ok_status)


def _qp(request: Request) -> dict[str, str]:
    return {k: str(v) for k, v in request.query_params.items()}


async def health(_: Request) -> JSONResponse:
    s = ReportesStore.get()
    try:
        s._ensure_fresh()
    except Exception:
        pass
    if s._error_carga:
        return JSONResponse(
            {
                "estado": "error",
                "detail": s._error_carga,
                "archivo": s.archivo_ok,
                "path": s.path_usado or "db:panol.salida_historial",
            },
            status_code=503,
        )
    if s.ultima_actualizacion is None:
        return JSONResponse(
            {
                "estado": "cargando",
                "archivo": s.archivo_ok,
                "path": "db:panol.salida_historial",
            },
            status_code=503,
        )
    return JSONResponse(
        {
            "estado": "ok",
            "service": "reportes",
            "archivo": s.archivo_ok,
            "path": s.path_usado,
            "filas": int(len(s.df)),
            "ultima_actualizacion": s.timestamp_iso(),
            "db_enabled": bool(REPORTES_DB_ENABLED),
            "fuente": "db",
            "nota": "Fuente exclusiva: MariaDB salida_historial [DB-ONLY, sin fallback Excel].",
        }
    )


async def get_movimientos(request: Request) -> JSONResponse:
    return await _run_json(lambda: listar_movimientos(_store(), _qp(request)))


async def get_resumen(request: Request) -> JSONResponse:
    return await _run_json(lambda: resumen_movimientos(_store(), _qp(request)))


async def get_filtros(_: Request) -> JSONResponse:
    return await _run_json(lambda: opciones_filtros(_store()))


async def post_refresh(_: Request) -> JSONResponse:
    def work() -> dict:
        s = ReportesStore.get()
        ts = s.refresh()
        return {
            "mensaje": "Datos de reportes recargados.",
            "timestamp": ts.astimezone().isoformat(),
            "filas": int(len(s.df)),
            "path": s.path_usado,
        }

    return await _run_json(work)


async def get_export_xlsx(request: Request) -> Response:
    try:
        data = await run_in_threadpool(lambda: export_xlsx(_store(), _qp(request)))
    except (CargandoDatosError, RedNoDisponibleError, FileNotFoundError) as e:
        return _err(e, 503)
    except Exception as e:
        log.exception("Error export XLSX")
        return _err(e, 500)
    return Response(
        data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="reportes_movimientos.xlsx"'},
    )


async def get_export_csv(request: Request) -> Response:
    """DEPRECATED — preferir /api/reportes/export.xlsx."""
    try:
        data = await run_in_threadpool(lambda: export_csv(_store(), _qp(request)))
    except (CargandoDatosError, RedNoDisponibleError, FileNotFoundError) as e:
        return _err(e, 503)
    except Exception as e:
        log.exception("Error export CSV")
        return _err(e, 500)
    return Response(
        data,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="reportes_movimientos.csv"',
            "X-Deprecated": "Usar /api/reportes/export.xlsx",
        },
    )


async def get_mail_status(_: Request) -> JSONResponse:
    return JSONResponse(mail_status())


async def post_mail_diario_dry(_: Request) -> JSONResponse:
    return await _run_json(lambda: dry_run_diario())


async def post_mail_diario(request: Request) -> JSONResponse:
    """Envía diario solo si REPORTES_MAIL_DIARIO_ENABLED=1 (sin forzar)."""
    if not REPORTES_MAIL_DIARIO_ENABLED:
        return JSONResponse(
            {
                "enviado": False,
                "detail": "Mail diario desactivado (REPORTES_MAIL_DIARIO_ENABLED=0).",
                **mail_status(),
            },
            status_code=403,
        )

    def work() -> dict:
        try:
            return run_diario_si_habilitado()
        except MailNoConfiguradoError as e:
            raise ValueError(str(e)) from e

    return await _run_json(work)


async def post_mail_mensual(request: Request) -> JSONResponse:
    if not REPORTES_MAIL_MENSUAL_ENABLED:
        return JSONResponse(
            {
                "enviado": False,
                "detail": "Mail mensual desactivado (REPORTES_MAIL_MENSUAL_ENABLED=0).",
                **mail_status(),
            },
            status_code=403,
        )

    def work() -> dict:
        try:
            return run_mensual_si_habilitado()
        except MailNoConfiguradoError as e:
            raise ValueError(str(e)) from e

    return await _run_json(work)


def _carga_inicial() -> None:
    try:
        ReportesStore.get().refresh()
        log.info("Reportes cargados desde DB (salida_historial) [DB-ONLY]")
    except Exception as e:
        ReportesStore.get().registrar_error_carga(str(e))
        log.warning("Carga inicial fallida: %s", e)


def _poll_mtime_loop() -> None:
    """Poll cada 60s por si el Excel cambió y nadie hizo request (robustez).

    Complementa el check perezoso de store._ensure_fresh() que ya se ejecuta
    en cada request. Este hilo asegura que el dato se refresque incluso
    durante períodos sin tráfico, sin necesidad de POST /refresh manual.
    Si el poll falla, no tumba el servicio: solo loguea.
    """
    import time

    log.info("Reportes: watcher mtime iniciado (poll 60s)")
    while True:
        try:
            time.sleep(60)
            s = ReportesStore.get()
            if s.ultima_actualizacion is None:
                continue
            # Reutiliza el check perezoso (ya compara mtime + tolerancia 1s y hace refresh)
            s._ensure_fresh()
        except Exception as e:
            log.debug("Poll mtime reportes ignorado: %s", e)


routes = [
    Route("/health", health, methods=["GET"]),
    Route("/api/reportes/health", health, methods=["GET"]),
    Route("/api/reportes/movimientos", get_movimientos, methods=["GET"]),
    Route("/api/reportes/resumen", get_resumen, methods=["GET"]),
    Route("/api/reportes/filtros", get_filtros, methods=["GET"]),
    Route("/api/reportes/refresh", post_refresh, methods=["POST"]),
    Route("/api/reportes/export.xlsx", get_export_xlsx, methods=["GET"]),
    Route("/api/reportes/export.csv", get_export_csv, methods=["GET"]),  # deprecated
    Route("/api/reportes/mail/status", get_mail_status, methods=["GET"]),
    Route("/api/reportes/mail/diario/dry-run", post_mail_diario_dry, methods=["POST"]),
    Route("/api/reportes/mail/diario", post_mail_diario, methods=["POST"]),
    Route("/api/reportes/mail/mensual", post_mail_mensual, methods=["POST"]),
]


@asynccontextmanager
async def lifespan(_app: Starlette):
    threading.Thread(target=_carga_inicial, name="reportes-load", daemon=True).start()
    threading.Thread(target=_poll_mtime_loop, name="reportes-mtime-poll", daemon=True).start()
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
