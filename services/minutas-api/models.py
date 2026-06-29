# -*- coding: utf-8 -*-
"""Esquemas Pydantic del servicio minutas-api."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


class Urgencia(str, Enum):
    BAJA = "baja"
    MEDIA = "media"
    ALTA = "alta"
    CRITICA = "critica"


class EstadoEntrega(str, Enum):
    PENDIENTE = "pendiente"
    PARCIAL = "parcial"
    COMPLETO = "completo"


class EstadoSesion(str, Enum):
    ABIERTA = "abierta"
    CERRADA = "cerrada"
    ENVIADA = "enviada"


class EntregaParcialCreate(BaseModel):
    fecha: str = Field(..., min_length=8, max_length=32)
    cantidad: int = Field(..., ge=1)
    observacion: Optional[str] = Field(default=None, max_length=500)

    @field_validator("fecha")
    @classmethod
    def _fecha_iso(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 8:
            raise ValueError("Fecha inválida.")
        return v

    @field_validator("observacion", mode="before")
    @classmethod
    def _trim(cls, v: object) -> object:
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return v


class EntregaParcial(EntregaParcialCreate):
    id: int
    solicitud_id: int
    creado_en: str


class ActualizacionCreate(BaseModel):
    texto: str = Field(..., min_length=1, max_length=4000)
    autor: Optional[str] = Field(default=None, max_length=120)

    @field_validator("texto", "autor", mode="before")
    @classmethod
    def _trim(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v


class Actualizacion(ActualizacionCreate):
    id: int
    sesion_id: int
    solicitud_id: Optional[int] = None
    creado_en: str


class SolicitudCreate(BaseModel):
    numero_referencia: str = Field(..., min_length=1, max_length=80)
    solicitante: str = Field(..., min_length=1, max_length=120)
    urgencia: Urgencia = Urgencia.MEDIA
    cantidad_items: int = Field(..., ge=1, le=99999)
    descripcion: Optional[str] = Field(default=None, max_length=500)

    @field_validator("numero_referencia", "solicitante", "descripcion", mode="before")
    @classmethod
    def _trim(cls, v: object) -> object:
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return v


class SolicitudUpdate(BaseModel):
    numero_referencia: Optional[str] = Field(default=None, min_length=1, max_length=80)
    solicitante: Optional[str] = Field(default=None, min_length=1, max_length=120)
    urgencia: Optional[Urgencia] = None
    cantidad_items: Optional[int] = Field(default=None, ge=1, le=99999)
    descripcion: Optional[str] = Field(default=None, max_length=500)
    estado_entrega: Optional[EstadoEntrega] = None
    cerrado: Optional[bool] = None

    @field_validator("numero_referencia", "solicitante", "descripcion", mode="before")
    @classmethod
    def _trim(cls, v: object) -> object:
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return v


class Solicitud(SolicitudCreate):
    id: int
    sesion_origen_id: int
    estado_entrega: EstadoEntrega
    cerrado: bool
    entregas: list[EntregaParcial] = Field(default_factory=list)
    actualizaciones: list[Actualizacion] = Field(default_factory=list)
    creado_en: str
    actualizado_en: str


class TemaCreate(BaseModel):
    titulo: str = Field(..., min_length=1, max_length=200)
    descripcion: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("titulo", "descripcion", mode="before")
    @classmethod
    def _trim(cls, v: object) -> object:
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return v


class TemaUpdate(BaseModel):
    titulo: Optional[str] = Field(default=None, min_length=1, max_length=200)
    descripcion: Optional[str] = Field(default=None, max_length=2000)
    resuelto: Optional[bool] = None

    @field_validator("titulo", "descripcion", mode="before")
    @classmethod
    def _trim(cls, v: object) -> object:
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return v


class Tema(TemaCreate):
    id: int
    sesion_origen_id: int
    resuelto: bool
    creado_en: str
    actualizado_en: str


class SesionCreate(BaseModel):
    notas_generales: Optional[str] = Field(default=None, max_length=8000)
    responsable: Optional[str] = Field(default=None, max_length=120)

    @field_validator("notas_generales", "responsable", mode="before")
    @classmethod
    def _trim(cls, v: object) -> object:
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return v


class SesionUpdate(BaseModel):
    notas_generales: Optional[str] = Field(default=None, max_length=8000)
    responsable: Optional[str] = Field(default=None, max_length=120)

    @field_validator("notas_generales", "responsable", mode="before")
    @classmethod
    def _trim(cls, v: object) -> object:
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return v


class SesionResumen(BaseModel):
    id: int
    fecha: str
    semana_iso: str
    estado: EstadoSesion
    responsable: Optional[str] = None
    notas_generales: Optional[str] = None
    email_enviado_en: Optional[str] = None
    creado_en: str
    actualizado_en: str


class SesionDetalle(SesionResumen):
    solicitudes: list[Solicitud] = Field(default_factory=list)
    temas: list[Tema] = Field(default_factory=list)
    actualizaciones: list[Actualizacion] = Field(default_factory=list)


class EnviarMinutaRequest(BaseModel):
    destinatarios: list[EmailStr] = Field(default_factory=list)
    asunto: Optional[str] = Field(default=None, max_length=200)
    incluir_cerradas: bool = False

    @field_validator("asunto", mode="before")
    @classmethod
    def _trim_asunto(cls, v: object) -> object:
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return v


class EnviarMinutaResponse(BaseModel):
    ok: bool
    mensaje: str
    sesion_id: int
    destinatarios: list[str]


class PreviewEmailResponse(BaseModel):
    asunto: str
    cuerpo_texto: str
    cuerpo_html: str
