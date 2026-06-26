# -*- coding: utf-8 -*-
"""
models.py — Esquemas Pydantic de entrada/salida del servicio etiquetas-api.

Acá vive TODA la validación de forma del request. La regla central es la
validación cruzada por `tipo`:
  - tipo "simple"  -> sólo se usa `texto_libre`.
  - tipo "codigo"  -> se usan `codigo`, `descripcion`, `ubicacion` y `qr_data`.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class TipoEtiqueta(str, Enum):
    SIMPLE = "simple"
    CODIGO = "codigo"


class ResultadoImpresion(str, Enum):
    IMPRESO = "impreso"
    ERROR = "error"


class EtiquetaCreate(BaseModel):
    """Body de POST /etiquetas. Valida según el tipo de etiqueta."""

    tipo: TipoEtiqueta
    texto_libre: Optional[str] = None
    codigo: Optional[str] = None
    descripcion: Optional[str] = None
    ubicacion: Optional[str] = None
    qr_data: Optional[str] = None
    cantidad: int = Field(default=1, ge=1, description="Cantidad de copias (>= 1).")
    escala_fuente: float = Field(
        default=1.0,
        ge=0.5,
        le=4.0,
        description="Multiplicador del tamaño de letra (rótulo simple). 1.0 = normal.",
    )
    solicitado_por: Optional[str] = Field(
        default=None, description="Usuario o dispositivo que pide la impresión."
    )

    @field_validator(
        "texto_libre", "codigo", "descripcion", "ubicacion", "qr_data", "solicitado_por",
        mode="before",
    )
    @classmethod
    def _vacios_a_none(cls, v: object) -> object:
        """Normaliza strings: recorta espacios y trata "" como None."""
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return v

    @model_validator(mode="after")
    def _validar_por_tipo(self) -> "EtiquetaCreate":
        if self.tipo == TipoEtiqueta.SIMPLE:
            if not self.texto_libre:
                raise ValueError(
                    "Para tipo 'simple' el campo 'texto_libre' es obligatorio."
                )
            # En 'simple' sólo vale el texto libre: descartamos lo demás.
            self.codigo = None
            self.descripcion = None
            self.ubicacion = None
            self.qr_data = None
        else:  # TipoEtiqueta.CODIGO
            faltantes = [
                nombre
                for nombre, valor in (
                    ("codigo", self.codigo),
                    ("descripcion", self.descripcion),
                    ("ubicacion", self.ubicacion),
                    ("qr_data", self.qr_data),
                )
                if not valor
            ]
            if faltantes:
                raise ValueError(
                    "Para tipo 'codigo' son obligatorios: "
                    + ", ".join(faltantes)
                    + "."
                )
            # En 'codigo' no se usa texto libre.
            self.texto_libre = None
        return self


class ConfirmarRequest(BaseModel):
    """Body de POST /etiquetas/{id}/confirmar (lo manda el print-agent)."""

    resultado: ResultadoImpresion
    error_msg: Optional[str] = None


class PedidoCreado(BaseModel):
    """Respuesta corta al crear un pedido."""

    id: int
    estado: str


class Pedido(BaseModel):
    """Representación completa de un pedido de la cola."""

    id: int
    tipo: str
    texto_libre: Optional[str] = None
    codigo: Optional[str] = None
    descripcion: Optional[str] = None
    ubicacion: Optional[str] = None
    qr_data: Optional[str] = None
    cantidad: int
    escala_fuente: float = 1.0
    solicitado_por: Optional[str] = None
    estado: str
    intentos: int
    error_msg: Optional[str] = None
    creado_en: str
    actualizado_en: str


class CatalogoItem(BaseModel):
    """Respuesta de GET /catalogo/{codigo} (lectura de Firestore)."""

    codigo: str
    descripcion: str
    ubicacion: str
