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
from typing import Any, Optional

# ----------------------------------------------------------------------------
# CONFIGURACIÓN EDITABLE (sin confirmar — ajustar cuando se valide con la app real)
# ----------------------------------------------------------------------------
COLECCION_CATALOGO = "articulos"   # nombre de la colección de artículos
CAMPO_CODIGO = "codigo"            # campo que guarda el código del artículo
CAMPO_DESCRIPCION = "desc"         # campo de la descripción
CAMPO_UBICACION = "ubicacion"      # campo de la ubicación

# Ruta del archivo de credenciales de servicio (firebase-admin).
# Se puede sobreescribir con la variable de entorno GOOGLE_APPLICATION_CREDENTIALS.
RUTA_CREDENCIALES = os.environ.get(
    "GOOGLE_APPLICATION_CREDENTIALS",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "serviceAccountKey.json"),
)


class FirebaseNoConfigurado(RuntimeError):
    """Se lanza cuando faltan credenciales o la librería firebase-admin."""


_db = None  # cliente Firestore cacheado (se inicializa una sola vez)


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


def buscar_catalogo(codigo: str) -> Optional[dict[str, str]]:
    """
    Busca un código en el catálogo (SOLO LECTURA).

    Estrategia: primero intenta el documento cuyo id es el código (caso común);
    si no existe, hace una consulta por el campo de código. Devuelve un dict
    {codigo, descripcion, ubicacion} o None si no se encuentra.
    """
    codigo = str(codigo).strip()
    if not codigo:
        return None

    db = _get_db()
    col = db.collection(COLECCION_CATALOGO)

    # 1) Documento por id == código.
    doc = col.document(codigo).get()
    if doc.exists:
        return _doc_a_item(codigo, doc.to_dict() or {})

    # 2) Consulta por el campo de código.
    consulta = col.where(CAMPO_CODIGO, "==", codigo).limit(1).stream()
    for encontrado in consulta:
        return _doc_a_item(codigo, encontrado.to_dict() or {})

    return None
