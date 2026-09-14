# -*- coding: utf-8 -*-
"""Sync Firebase de artículos para Salidas.

Estrategia (mínimas lecturas — lección etiquetas):
  1. Caché SQLite local diaria (`articulos_cache`).
  2. Pull Firestore como máximo 1× por día calendario tras HORA_SYNC (opcional).
  3. Búsquedas de stock/código usan Excel maestro en memoria (0 lecturas FS).
  4. Al confirmar salida: escritura merge del doc + bump config/catalogo
     (mismo contrato que el escritorio), y actualización de la caché local.

⚠️ Sin credenciales: el módulo sigue operando con Excel de prueba;
   las escrituras Firebase se omiten con aviso en health.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import articulos_cache
from config import (
    FIREBASE_WRITE_ENABLED,
    HORA_SYNC_FIREBASE,
    firebase_credentials_path,
)

log = logging.getLogger("salidas.firebase")

try:
    from zoneinfo import ZoneInfo

    def _tz_local():
        try:
            return ZoneInfo("America/Argentina/Buenos_Aires")
        except Exception:
            return timezone(timedelta(hours=-3))
except ImportError:

    def _tz_local():
        return timezone(timedelta(hours=-3))


TZ = _tz_local()
COLECCION = "articulos"

_db = None
_lock = threading.Lock()
_estado = "pendiente"
_ultimo_error: str | None = None
_sync_started = False


class FirebaseNoConfigurado(RuntimeError):
    pass


def _ahora() -> datetime:
    return datetime.now(TZ)


def _get_db():
    global _db, _ultimo_error
    if _db is not None:
        return _db
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
    except ImportError as e:
        raise FirebaseNoConfigurado(
            "Falta firebase-admin. Agregalo a requirements e instalá el venv."
        ) from e

    cred_path = firebase_credentials_path()
    if not cred_path.is_file():
        raise FirebaseNoConfigurado(f"Sin credenciales en {cred_path}")

    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(str(cred_path)))
    _db = firestore.client()
    _ultimo_error = None
    return _db


def _necesita_pull(ultima: Optional[datetime]) -> bool:
    if not articulos_cache.tiene_datos():
        return True
    ahora = _ahora()
    if ahora.hour < HORA_SYNC_FIREBASE:
        return False
    if ultima is None:
        return True
    ultima_local = ultima.astimezone(TZ) if ultima.tzinfo else ultima.replace(tzinfo=TZ)
    return ahora.date() > ultima_local.date()


def pull_firestore_si_corresponde(*, forzar: bool = False) -> dict[str, Any]:
    """Una recolección completa opcional. No se llama en cada request."""
    global _estado, _ultimo_error
    articulos_cache.init_db()
    ultima = articulos_cache.obtener_ultima_pull()
    if not forzar and not _necesita_pull(ultima):
        if articulos_cache.tiene_datos():
            _estado = "listo_cache"
            return {
                "accion": "cache_local",
                "articulos": len(articulos_cache.cargar_todos()),
                "ultima_pull": ultima.isoformat() if ultima else None,
            }
        return {"accion": "sin_datos", "articulos": 0}

    try:
        db = _get_db()
    except FirebaseNoConfigurado as e:
        _estado = "sin_credenciales"
        _ultimo_error = str(e)
        if articulos_cache.tiene_datos():
            _estado = "listo_cache"
        return {"accion": "omitido", "detail": str(e)}

    _estado = "sincronizando"
    items: list[dict[str, Any]] = []
    try:
        for doc in db.collection(COLECCION).stream():
            d = doc.to_dict() or {}
            try:
                stock = float(d.get("stock") or 0)
            except (TypeError, ValueError):
                stock = 0.0
            items.append(
                {
                    "doc_id": doc.id,
                    "codigo": str(d.get("codigo", doc.id) or doc.id).strip().upper(),
                    "desc": str(d.get("desc", "") or ""),
                    "stock": stock,
                    "ubicacion": str(d.get("ubicacion", "") or ""),
                    "categoria": str(d.get("categoria", "GENERAL") or "GENERAL"),
                }
            )
        ahora = _ahora()
        articulos_cache.reemplazar_todo(items, ahora)
        _estado = "listo"
        _ultimo_error = None
        log.info("Pull Firestore: %s artículos", len(items))
        return {"accion": "pull", "articulos": len(items), "ultima_pull": ahora.isoformat()}
    except Exception as e:
        _ultimo_error = str(e)
        _estado = "error"
        if articulos_cache.tiene_datos():
            _estado = "listo_cache"
        log.warning("Pull Firestore falló: %s", e)
        return {"accion": "error", "detail": str(e)}


def escribir_stock_item(
    codigo: str,
    nuevo_stock: float,
    desc: str,
    ubicacion: str,
    categoria: str = "GENERAL",
) -> bool:
    """Merge en Firestore + bump versión catálogo + caché local. No bloquea si falla."""
    codigo = str(codigo or "").strip().upper()
    if not codigo:
        return False
    articulos_cache.init_db()
    articulos_cache.upsert_item(
        codigo, codigo, desc or "", float(nuevo_stock), ubicacion or "", categoria or "GENERAL"
    )
    articulos_cache.marcar_sync(_ahora())

    if not FIREBASE_WRITE_ENABLED:
        return False
    try:
        db = _get_db()
        from firebase_admin import firestore

        db.collection(COLECCION).document(codigo).set(
            {
                "codigo": codigo,
                "stock": float(nuevo_stock),
                "desc": desc or "",
                "ubicacion": ubicacion or "",
                "categoria": categoria or "GENERAL",
            },
            merge=True,
        )
        db.collection("config").document("catalogo").set(
            {"version": int(time.time()), "updatedAt": firestore.SERVER_TIMESTAMP},
            merge=True,
        )
        return True
    except FirebaseNoConfigurado:
        return False
    except Exception as e:
        log.warning("Write Firebase %s: %s", codigo, e)
        return False


def estado_sync() -> dict[str, Any]:
    ultima = articulos_cache.obtener_ultima_sync()
    pull = articulos_cache.obtener_ultima_pull()
    with _lock:
        return {
            "estado": _estado,
            "articulos_en_cache": len(articulos_cache.cargar_todos())
            if articulos_cache.tiene_datos()
            else 0,
            "ultima_sync_local": ultima.isoformat() if ultima else None,
            "ultima_pull_firestore": pull.isoformat() if pull else None,
            "hora_sync_configurada": HORA_SYNC_FIREBASE,
            "escritura_habilitada": FIREBASE_WRITE_ENABLED,
            "credenciales": firebase_credentials_path().is_file(),
            "error": _ultimo_error,
        }


def _loop() -> None:
    articulos_cache.init_db()
    # Preferir caché local al arrancar
    if articulos_cache.tiene_datos():
        global _estado
        _estado = "listo_cache"
    try:
        pull_firestore_si_corresponde(forzar=False)
    except Exception as e:
        log.warning("Sync inicial: %s", e)
    while True:
        time.sleep(1800)
        try:
            pull_firestore_si_corresponde(forzar=False)
        except Exception:
            pass


def iniciar_sync_background() -> None:
    global _sync_started
    if _sync_started:
        return
    _sync_started = True
    threading.Thread(target=_loop, name="salidas-firebase-sync", daemon=True).start()
