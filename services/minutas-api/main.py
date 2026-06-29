# -*- coding: utf-8 -*-
"""API REST del módulo Minutas de reunión semanal."""

from __future__ import annotations

import os
import smtplib

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

import repo
from email_service import (
    EmailNoConfigurado,
    construir_asunto,
    construir_cuerpo_html,
    construir_cuerpo_texto,
    destinatarios_default_o,
    enviar_minuta,
)
from models import (
    Actualizacion,
    ActualizacionCreate,
    EnviarMinutaRequest,
    EnviarMinutaResponse,
    EntregaParcialCreate,
    PreviewEmailResponse,
    SesionCreate,
    SesionDetalle,
    SesionResumen,
    SesionUpdate,
    Solicitud,
    SolicitudCreate,
    SolicitudUpdate,
    Tema,
    TemaCreate,
    TemaUpdate,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    repo.init_db()
    yield


app = FastAPI(
    title="minutas-api",
    version="0.1.0",
    description="Minutas de reunión semanal — seguimiento de solicitudes a compras.",
    lifespan=lifespan,
)

_origins = os.environ.get("MINUTAS_CORS_ORIGINS", "*").strip()
_allow = ["*"] if _origins == "*" else [o.strip() for o in _origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _http_from_value(e: ValueError) -> HTTPException:
    return HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))


def _http_from_lookup(e: LookupError) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "minutas-api"}


@app.get("/sesiones", response_model=list[SesionResumen], tags=["sesiones"])
def listar_sesiones(limite: int = 20) -> list[SesionResumen]:
    return repo.listar_sesiones(min(limite, 100))


@app.get("/sesiones/actual", response_model=SesionDetalle | None, tags=["sesiones"])
def sesion_actual() -> SesionDetalle | None:
    sesiones = repo.listar_sesiones(50)
    for s in sesiones:
        if s.estado.value == "abierta":
            return repo.obtener_sesion_detalle(s.id)
    return None


@app.get("/sesiones/{sesion_id}", response_model=SesionDetalle, tags=["sesiones"])
def obtener_sesion(sesion_id: int) -> SesionDetalle:
    det = repo.obtener_sesion_detalle(sesion_id)
    if not det:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Sesión no encontrada.")
    return det


@app.post("/sesiones/iniciar", response_model=SesionDetalle, tags=["sesiones"])
def iniciar_sesion(body: SesionCreate) -> SesionDetalle:
    try:
        return repo.iniciar_sesion_semana(body.notas_generales, body.responsable)
    except ValueError as e:
        raise _http_from_value(e) from e


@app.patch("/sesiones/{sesion_id}", response_model=SesionResumen, tags=["sesiones"])
def patch_sesion(sesion_id: int, body: SesionUpdate) -> SesionResumen:
    try:
        return repo.actualizar_sesion(sesion_id, body.notas_generales, body.responsable)
    except LookupError as e:
        raise _http_from_lookup(e) from e
    except ValueError as e:
        raise _http_from_value(e) from e


@app.post("/sesiones/{sesion_id}/solicitudes", response_model=Solicitud, tags=["solicitudes"])
def post_solicitud(sesion_id: int, body: SolicitudCreate) -> Solicitud:
    try:
        return repo.crear_solicitud(sesion_id, body)
    except LookupError as e:
        raise _http_from_lookup(e) from e
    except ValueError as e:
        raise _http_from_value(e) from e


@app.patch("/sesiones/{sesion_id}/solicitudes/{solicitud_id}", response_model=Solicitud, tags=["solicitudes"])
def patch_solicitud(sesion_id: int, solicitud_id: int, body: SolicitudUpdate) -> Solicitud:
    try:
        return repo.actualizar_solicitud(sesion_id, solicitud_id, body)
    except LookupError as e:
        raise _http_from_lookup(e) from e
    except ValueError as e:
        raise _http_from_value(e) from e


@app.post(
    "/sesiones/{sesion_id}/solicitudes/{solicitud_id}/entregas",
    response_model=Solicitud,
    tags=["solicitudes"],
)
def post_entrega(sesion_id: int, solicitud_id: int, body: EntregaParcialCreate) -> Solicitud:
    try:
        return repo.agregar_entrega(sesion_id, solicitud_id, body)
    except LookupError as e:
        raise _http_from_lookup(e) from e
    except ValueError as e:
        raise _http_from_value(e) from e


@app.post(
    "/sesiones/{sesion_id}/solicitudes/{solicitud_id}/actualizaciones",
    response_model=Actualizacion,
    tags=["solicitudes"],
)
def post_actualizacion(
    sesion_id: int, solicitud_id: int, body: ActualizacionCreate
) -> Actualizacion:
    try:
        return repo.agregar_actualizacion_solicitud(sesion_id, solicitud_id, body)
    except LookupError as e:
        raise _http_from_lookup(e) from e


@app.post("/sesiones/{sesion_id}/temas", response_model=Tema, tags=["temas"])
def post_tema(sesion_id: int, body: TemaCreate) -> Tema:
    try:
        return repo.crear_tema(sesion_id, body)
    except LookupError as e:
        raise _http_from_lookup(e) from e
    except ValueError as e:
        raise _http_from_value(e) from e


@app.patch("/temas/{tema_id}", response_model=Tema, tags=["temas"])
def patch_tema(tema_id: int, body: TemaUpdate) -> Tema:
    try:
        return repo.actualizar_tema(tema_id, body)
    except LookupError as e:
        raise _http_from_lookup(e) from e


@app.get("/sesiones/{sesion_id}/preview-email", response_model=PreviewEmailResponse, tags=["email"])
def preview_email(sesion_id: int, asunto: str | None = None) -> PreviewEmailResponse:
    try:
        sesion = repo.datos_para_email(sesion_id)
    except LookupError as e:
        raise _http_from_lookup(e) from e
    return PreviewEmailResponse(
        asunto=construir_asunto(sesion, asunto),
        cuerpo_texto=construir_cuerpo_texto(sesion),
        cuerpo_html=construir_cuerpo_html(sesion),
    )


@app.post("/sesiones/{sesion_id}/enviar", response_model=EnviarMinutaResponse, tags=["email"])
def enviar_minuta_endpoint(sesion_id: int, body: EnviarMinutaRequest) -> EnviarMinutaResponse:
    try:
        sesion = repo.datos_para_email(sesion_id)
        destinatarios = destinatarios_default_o([str(e) for e in body.destinatarios])
        asunto = construir_asunto(sesion, body.asunto)
        texto = construir_cuerpo_texto(sesion)
        html = construir_cuerpo_html(sesion)
        enviar_minuta(destinatarios, asunto, texto, html)
        repo.marcar_sesion_enviada(sesion_id)
    except LookupError as e:
        raise _http_from_lookup(e) from e
    except EmailNoConfigurado as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e
    except ValueError as e:
        raise _http_from_value(e) from e
    except smtplib.SMTPException as e:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=f"Error al enviar correo: {e}",
        ) from e

    return EnviarMinutaResponse(
        ok=True,
        mensaje="Minuta enviada correctamente.",
        sesion_id=sesion_id,
        destinatarios=destinatarios,
    )
