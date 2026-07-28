# -*- coding: utf-8 -*-
"""Router de endpoints KPIs."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from data_loader import CargandoDatosError, DataStore, RedNoDisponibleError
import kpis_activos
import kpis_consumo
import kpis_reposicion
import kpis_stock


def _err(exc: Exception, status: int = 500) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=status)


def _store() -> DataStore:
    s = DataStore.get()
    s.require_loaded()
    return s


async def _run_json(work: Callable[[], dict[str, Any]]) -> JSONResponse:
    """Excel/pandas bloquean — ejecutar en hilo para no congelar uvicorn."""
    try:
        data = await run_in_threadpool(work)
        return JSONResponse(data)
    except CargandoDatosError as e:
        return _err(e, 503)
    except RedNoDisponibleError as e:
        return _err(e, 503)
    except Exception as e:
        return _err(e, 500)


async def health(_: Request) -> JSONResponse:
    try:

        def work() -> dict[str, Any]:
            store = DataStore.get()
            if store.ultima_actualizacion is None:
                return {
                    "estado": "cargando",
                    "archivos": store.archivos_ok,
                    "sectores": store.sectores_oficiales,
                    "ultima_actualizacion": "",
                    "mensaje": "Cargando Excel del pañol (puede tardar 1-2 min la primera vez)…",
                }
            estado = "ok" if store.archivos_ok.get("master_codes") else "error"
            return {
                "estado": estado,
                "archivos": store.archivos_ok,
                "sectores": store.sectores_oficiales,
                "ultima_actualizacion": store.timestamp_iso(),
            }

        return JSONResponse(await run_in_threadpool(work))
    except RedNoDisponibleError as e:
        return JSONResponse({"estado": "error", "detail": str(e), "archivos": {}}, status_code=503)
    except Exception as e:
        return JSONResponse({"estado": "error", "detail": str(e), "archivos": {}}, status_code=503)


async def refresh(_: Request) -> JSONResponse:
    try:
        ts = await run_in_threadpool(DataStore.get().refresh)
        return JSONResponse(
            {
                "mensaje": "Datos actualizados",
                "timestamp": ts.astimezone().isoformat(),
            }
        )
    except RedNoDisponibleError as e:
        return _err(e, 503)
    except Exception as e:
        return _err(e, 500)


async def stock_resumen(_: Request) -> JSONResponse:
    return await _run_json(lambda: kpis_stock.stock_resumen(_store()))


async def stock_bajo_minimo(request: Request) -> JSONResponse:
    crit = request.query_params.get("criticidad")
    return await _run_json(lambda: kpis_stock.stock_bajo_minimo(_store(), crit))


async def stock_en_cero(request: Request) -> JSONResponse:
    top = int(request.query_params.get("top", "20"))
    return await _run_json(lambda: kpis_stock.stock_en_cero(_store(), top))


async def consumo_mensual(request: Request) -> JSONResponse:
    meses = int(request.query_params.get("meses", "12"))
    return await _run_json(lambda: kpis_consumo.consumo_mensual(_store(), meses))


async def consumo_por_sector(request: Request) -> JSONResponse:
    mes = request.query_params.get("mes")
    return await _run_json(lambda: kpis_consumo.consumo_por_sector(_store(), mes))


async def consumo_por_linea(request: Request) -> JSONResponse:
    mes = request.query_params.get("mes")
    return await _run_json(lambda: kpis_consumo.consumo_por_linea(_store(), mes))


async def consumo_top_articulos(request: Request) -> JSONResponse:
    mes = request.query_params.get("mes")
    top = int(request.query_params.get("top", "10"))
    return await _run_json(lambda: kpis_consumo.consumo_top_articulos(_store(), mes, top))


async def consumo_tendencia_anual(_: Request) -> JSONResponse:
    return await _run_json(lambda: kpis_consumo.consumo_tendencia_anual(_store()))


async def reposicion_resumen(_: Request) -> JSONResponse:
    return await _run_json(lambda: kpis_reposicion.reposicion_resumen(_store()))


async def activos_resumen(_: Request) -> JSONResponse:
    return await _run_json(lambda: kpis_activos.activos_resumen(_store()))


async def _run_bytes(
    work: Callable[[], bytes], media_type: str, filename: str
) -> Response:
    try:
        data = await run_in_threadpool(work)
    except (CargandoDatosError, RedNoDisponibleError) as e:
        return _err(e, 503)
    except Exception as e:
        return _err(e, 500)
    return Response(
        data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


async def activos_export_excel(_: Request) -> Response:
    return await _run_bytes(
        lambda: kpis_activos.activos_excel(_store()),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "activos_fuera_de_planta.xlsx",
    )


async def activos_export_pdf(_: Request) -> Response:
    return await _run_bytes(
        lambda: kpis_activos.activos_pdf(_store()),
        "application/pdf",
        "activos_fuera_de_planta.pdf",
    )
