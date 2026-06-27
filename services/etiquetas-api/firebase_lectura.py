# -*- coding: utf-8 -*-
"""
firebase_lectura.py — Lectura del catálogo desde Firebase Firestore.

⚠️ SOLO LECTURA. Este módulo NUNCA debe escribir, actualizar ni borrar nada en
Firestore. No hay (ni debe haber) funciones que llamen a .set(), .update(),
.add() o .delete() sobre las colecciones de catálogo/stock. Si en el futuro
hiciera falta escribir, hay que DETENERSE y avisar: no es parte de este servicio.

Los nombres de colección y de campos del catálogo TODAVÍA NO están confirmados
contra el proyecto real de la app móvil. Se dejan como constantes editables acá
arriba para ajustarlos en otra tarea sin tocar el resto del código.
"""

from __future__ import annotations

import os
import time
from typing import Any, Optional

# ----------------------------------------------------------------------------
# CONFIGURACIÓN EDITABLE (sin confirmar — ajustar cuando se valide con la app real)
# ----------------------------------------------------------------------------
COLECCION_CATALOGO = "articulos"   # nombre de la colección de artículos
CAMPO_CODIGO = "codigo"            # campo que guarda el código del artículo
CAMPO_DESCRIPCION = "desc"         # campo de la descripción
CAMPO_UBICACION = "ubicacion"      # campo de la ubicación

# Caché en memoria para no agotar la cuota diaria de lecturas de Firestore.
# TTL en segundos (por defecto 10 min). 0 = desactivar caché.
CACHE_TTL_SEG = int(os.environ.get("ETIQUETAS_CACHE_TTL", "600"))

# Ruta del archivo de credenciales de servicio (firebase-admin).
# Se puede sobreescribir con la variable de entorno GOOGLE_APPLICATION_CREDENTIALS.
RUTA_CREDENCIALES = os.environ.get(
    "GOOGLE_APPLICATION_CREDENTIALS",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "serviceAccountKey.json"),
)


class FirebaseNoConfigurado(RuntimeError):
    """Se lanza cuando faltan credenciales o la librería firebase-admin."""


class FirebaseQuotaExcedida(RuntimeError):
    """Firestore rechazó la lectura (429 / cuota diaria o rate limit)."""


_db = None  # cliente Firestore cacheado (se inicializa una sola vez)
_cache: dict[str, tuple[float, Optional[dict[str, str]]]] = {}


def inicializar_firebase() -> None:
    """Conecta el cliente Firestore sin hacer lecturas (warmup seguro)."""
    _get_db()


def _get_db():
    """
    Inicializa firebase-admin una sola vez y devuelve el cliente Firestore.

    El import de firebase_admin es perezoso a propósito: así el resto del
    servicio (la cola SQLite) funciona aunque la librería no esté instalada o
    falten credenciales.
    """
    global _db
    if _db is not None:
        return _db

    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
    except ImportError as exc:  # firebase-admin no instalado
        raise FirebaseNoConfigurado(
            "Falta la librería 'firebase-admin'. Instalá las dependencias del servicio."
        ) from exc

    if not os.path.exists(RUTA_CREDENCIALES):
        raise FirebaseNoConfigurado(
            f"No se encontró el archivo de credenciales en '{RUTA_CREDENCIALES}'. "
            "Configurá GOOGLE_APPLICATION_CREDENTIALS o dejá serviceAccountKey.json."
        )

    if not firebase_admin._apps:
        cred = credentials.Certificate(RUTA_CREDENCIALES)
        firebase_admin.initialize_app(cred)
    _db = firestore.client()
    return _db


def _doc_a_item(codigo_consultado: str, data: dict[str, Any]) -> dict[str, str]:
    """Mapea un documento de Firestore al formato de salida del servicio."""
    return {
        "codigo": str(data.get(CAMPO_CODIGO, codigo_consultado) or codigo_consultado),
        "descripcion": str(data.get(CAMPO_DESCRIPCION, "") or ""),
        "ubicacion": str(data.get(CAMPO_UBICACION, "") or ""),
    }


def _variantes(codigo: str) -> list[str]:
    """Máximo 2 variantes (mayúsculas primero) para minimizar lecturas."""
    base = codigo.strip()
    upper = base.upper()
    vistos: list[str] = []
    for c in (upper, base):
        if c and c not in vistos:
            vistos.append(c)
    return vistos


def _leer_cache(clave: str) -> Optional[dict[str, str]] | object:
    """Devuelve el item cacheado, None si no está, o _SIN_CACHE si TTL=0."""
    if CACHE_TTL_SEG <= 0:
        return _SIN_CACHE
    entry = _cache.get(clave)
    if not entry:
        return _SIN_CACHE
    expira, valor = entry
    if time.time() >= expira:
        del _cache[clave]
        return _SIN_CACHE
    return valor


_SIN_CACHE = object()


def _guardar_cache(clave: str, valor: Optional[dict[str, str]]) -> None:
    if CACHE_TTL_SEG <= 0:
        return
    _cache[clave] = (time.time() + CACHE_TTL_SEG, valor)


def _buscar_variante(col, variante: str) -> Optional[dict[str, str]]:
    """Una variante: primero doc por id (1 lectura); query solo si no existe."""
    from firebase_admin import firestore
    from google.api_core import exceptions as gax

    try:
        doc = col.document(variante).get()
        if doc.exists:
            return _doc_a_item(variante, doc.to_dict() or {})

        consulta = (
            col.where(filter=firestore.FieldFilter(CAMPO_CODIGO, "==", variante))
            .limit(1)
            .stream()
        )
        for encontrado in consulta:
            return _doc_a_item(variante, encontrado.to_dict() or {})
    except gax.ResourceExhausted as exc:
        raise FirebaseQuotaExcedida(
            "Cuota de lecturas de Firebase agotada temporalmente. "
            "Esperá unos minutos o revisá el plan de Firestore. "
            "Las etiquetas simples siguen funcionando."
        ) from exc

    return None


def buscar_catalogo(codigo: str) -> Optional[dict[str, str]]:
    """
    Busca un código en el catálogo (SOLO LECTURA).

    Usa caché en memoria y pocas lecturas por búsqueda (doc id primero).
    """
    codigo = str(codigo).strip()
    if not codigo:
        return None

    clave_cache = codigo.upper()
    cached = _leer_cache(clave_cache)
    if cached is not _SIN_CACHE:
        return cached

    db = _get_db()
    col = db.collection(COLECCION_CATALOGO)

    resultado: Optional[dict[str, str]] = None
    for variante in _variantes(codigo):
        resultado = _buscar_variante(col, variante)
        if resultado is not None:
            break

    _guardar_cache(clave_cache, resultado)
    return resultado
