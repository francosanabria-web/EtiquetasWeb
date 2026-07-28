# -*- coding: utf-8 -*-
"""Servicio KPIs — Sistemas Pañol (Starlette + pandas, solo lectura Excel)."""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.routing import Route

from starlette.concurrency import run_in_threadpool

from config import PORT, cors_origins_list
from data_loader import DataStore, RedNoDisponibleError
from router import (
    activos_export_excel,
    activos_export_pdf,
    activos_resumen,
    consumo_mensual,
    consumo_por_linea,
    consumo_por_sector,
    consumo_tendencia_anual,
    consumo_top_articulos,
    health,
    refresh,
    reposicion_resumen,
    stock_bajo_minimo,
    stock_en_cero,
    stock_resumen,
)


def _cargar_env_local() -> None:
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


_cargar_env_local()


@asynccontextmanager
async def lifespan(app: Starlette):
    """Carga Excel en segundo plano para que el puerto 8001 acepte conexiones de inmediato."""

    async def _cargar_en_fondo() -> None:
        try:
            print("[kpis] Cargando datos Excel (primera vez puede tardar 1-2 min)…")
            await run_in_threadpool(DataStore.get().refresh)
            print("[kpis] Datos listos.")
        except (RedNoDisponibleError, FileNotFoundError, OSError) as e:
            DataStore.get().registrar_error_carga(str(e))
            print(f"[kpis] Advertencia al cargar datos: {e}")

    tarea = asyncio.create_task(_cargar_en_fondo())
    yield
    if not tarea.done():
        tarea.cancel()


routes = [
    Route("/api/kpis/health", health, methods=["GET"]),
    Route("/api/kpis/refresh", refresh, methods=["GET"]),
    Route("/api/kpis/stock/resumen", stock_resumen, methods=["GET"]),
    Route("/api/kpis/stock/bajo-minimo", stock_bajo_minimo, methods=["GET"]),
    Route("/api/kpis/stock/en-cero", stock_en_cero, methods=["GET"]),
    Route("/api/kpis/consumo/mensual", consumo_mensual, methods=["GET"]),
    Route("/api/kpis/consumo/por-sector", consumo_por_sector, methods=["GET"]),
    Route("/api/kpis/consumo/por-linea", consumo_por_linea, methods=["GET"]),
    Route("/api/kpis/consumo/top-articulos", consumo_top_articulos, methods=["GET"]),
    Route("/api/kpis/consumo/tendencia-anual", consumo_tendencia_anual, methods=["GET"]),
    Route("/api/kpis/reposicion/resumen", reposicion_resumen, methods=["GET"]),
    Route("/api/kpis/activos/resumen", activos_resumen, methods=["GET"]),
    Route("/api/kpis/activos/export.xlsx", activos_export_excel, methods=["GET"]),
    Route("/api/kpis/activos/export.pdf", activos_export_pdf, methods=["GET"]),
    Route("/health", health, methods=["GET"]),
]

app = Starlette(routes=routes, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins_list(),
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)
