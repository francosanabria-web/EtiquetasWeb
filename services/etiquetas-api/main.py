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

from contextlib import asynccontextmanager

from fastapi import FastAPI, status

import cola_repo
from models import EtiquetaCreate, Pedido, PedidoCreado


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Asegura que la tabla de la cola exista al arrancar.
    cola_repo.init_db()
    yield


app = FastAPI(
    title="etiquetas-api",
    version="0.1.0",
    description="Microservicio de etiquetas para app_web_salidas (cola SQLite + Firestore solo lectura).",
    lifespan=lifespan,
)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    """Chequeo simple de vida del servicio."""
    return {"estado": "ok", "servicio": "etiquetas-api"}


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
