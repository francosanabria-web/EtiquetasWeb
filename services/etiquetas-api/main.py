# -*- coding: utf-8 -*-
"""
main.py — API del servicio de etiquetas (app_web_salidas).

Responsabilidades:
  - Leer el catálogo desde Firestore (SOLO LECTURA) para resolver un código.
  - Recibir pedidos de impresión y encolarlos en SQLite.
  - Exponer la cola al print-agent (polling) y recibir la confirmación de cada
    impresión.

El print-agent NO recibe push: pregunta por los pendientes (GET) y confirma
(POST). Así sólo necesita salida de red, sin IP fija ni puertos expuestos en la
PC de la impresora.
"""

from __future__ import annotations

import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

import cola_repo
from firebase_lectura import (
    CatalogoNoDisponible,
    CatalogoSincronizando,
    FirebaseNoConfigurado,
    FirebaseQuotaExcedida,
    buscar_catalogo,
    estado_catalogo,
    iniciar_sincronizacion_catalogo,
)
from models import (
    CatalogoItem,
    ConfirmarRequest,
    EtiquetaCreate,
    Pedido,
    PedidoCreado,
)


def _arrancar_catalogo() -> None:
    try:
        iniciar_sincronizacion_catalogo()
    except Exception:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    cola_repo.init_db()
    threading.Thread(target=_arrancar_catalogo, daemon=True).start()
    yield


app = FastAPI(
    title="etiquetas-api",
    version="0.1.0",
    description="Microservicio de etiquetas para app_web_salidas (cola SQLite + Firestore solo lectura).",
    lifespan=lifespan,
)

# CORS: el frontend (Vite) corre en otro origen y/o en otra PC de la red local.
# Por defecto se permite todo (herramienta interna de red local); se puede acotar
# con la variable de entorno ETIQUETAS_CORS_ORIGINS (lista separada por comas).
_origins_env = os.environ.get("ETIQUETAS_CORS_ORIGINS", "*").strip()
_allow_origins = ["*"] if _origins_env == "*" else [o.strip() for o in _origins_env.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    """Chequeo simple de vida del servicio."""
    return {"estado": "ok", "servicio": "etiquetas-api"}


@app.get("/catalogo/estado", tags=["catalogo"])
def get_catalogo_estado() -> dict:
    """Estado de la caché del catálogo (sync, cantidad indexada)."""
    return estado_catalogo()


@app.get("/catalogo/{codigo}", response_model=CatalogoItem, tags=["catalogo"])
def get_catalogo(codigo: str) -> CatalogoItem:
    """Resuelve un código contra la caché local del catálogo (sin get() por request)."""
    try:
        item = buscar_catalogo(codigo)
    except FirebaseNoConfigurado as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except FirebaseQuotaExcedida as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except CatalogoSincronizando as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except CatalogoNoDisponible as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró el código '{codigo}' en el catálogo.",
        )
    return CatalogoItem(**item)


@app.post(
    "/etiquetas",
    response_model=PedidoCreado,
    status_code=status.HTTP_201_CREATED,
    tags=["etiquetas"],
)
def crear_etiqueta(pedido: EtiquetaCreate) -> PedidoCreado:
    """Encola un pedido de impresión (estado inicial 'pendiente')."""
    creado = cola_repo.crear_pedido(pedido.model_dump(mode="json"))
    return PedidoCreado(id=creado["id"], estado=creado["estado"])


@app.get("/etiquetas/pendientes", response_model=list[Pedido], tags=["etiquetas"])
def listar_pendientes() -> list[Pedido]:
    """Devuelve los pedidos pendientes (para el polling del print-agent)."""
    return [Pedido(**p) for p in cola_repo.listar_pendientes()]


@app.post(
    "/etiquetas/{pedido_id}/confirmar",
    response_model=Pedido,
    tags=["etiquetas"],
)
def confirmar_etiqueta(pedido_id: int, confirmacion: ConfirmarRequest) -> Pedido:
    """Aplica el resultado de impresión reportado por el print-agent."""
    try:
        actualizado = cola_repo.confirmar_pedido(
            pedido_id,
            confirmacion.resultado.value,
            confirmacion.error_msg,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    if actualizado is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el pedido {pedido_id}.",
        )
    return Pedido(**actualizado)
