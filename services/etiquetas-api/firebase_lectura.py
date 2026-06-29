# -*- coding: utf-8 -*-
"""
firebase_lectura.py — Catálogo Firestore SOLO LECTURA vía listener + caché.

Estrategia (mínimas lecturas):
  1. Tras las 08:00 (hora local), UNA sincronización con on_snapshot al día.
  2. El listener sigue activo: solo consume lecturas si cambia un documento
     (p. ej. carga de alias); el stock no cambia en jornada.
  3. Si la API se reinicia el mismo día, carga SQLite → 0 lecturas Firestore.
  4. GET /catalogo/{codigo} NUNCA llama a get() ni where(): solo memoria.

⚠️ NUNCA escribir en Firestore desde este módulo.
"""

from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

try:
    from zoneinfo import ZoneInfo

    def _tz_local():
        key = os.environ.get("ETIQUETAS_TZ", "America/Argentina/Buenos_Aires")
        try:
            return ZoneInfo(key)
        except Exception:
            return timezone(timedelta(hours=-3))
except ImportError:
    def _tz_local():
        return timezone(timedelta(hours=-3))

import catalogo_cache

COLECCION_CATALOGO = "articulos"
CAMPO_CODIGO = "codigo"
CAMPO_DESCRIPCION = "desc"
CAMPO_UBICACION = "ubicacion"

TZ = _tz_local()
HORA_SYNC = int(os.environ.get("ETIQUETAS_SYNC_HORA", "8"))

RUTA_CREDENCIALES = os.environ.get(
    "GOOGLE_APPLICATION_CREDENTIALS",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "serviceAccountKey.json"),
)


class FirebaseNoConfigurado(RuntimeError):
    pass


class FirebaseQuotaExcedida(RuntimeError):
    pass


class CatalogoSincronizando(RuntimeError):
    pass


class CatalogoNoDisponible(RuntimeError):
    pass


_db = None
_lock = threading.Lock()
_indice: dict[str, dict[str, str]] = {}
_estado: str = "pendiente"
_watch: Any = None
_sync_thread_started = False


def _ahora_local() -> datetime:
    return datetime.now(TZ)


def _doc_a_item(doc_id: str, data: dict[str, Any]) -> dict[str, str]:
    codigo = str(data.get(CAMPO_CODIGO, doc_id) or doc_id)
    return {
        "codigo": codigo,
        "descripcion": str(data.get(CAMPO_DESCRIPCION, "") or ""),
        "ubicacion": str(data.get(CAMPO_UBICACION, "") or ""),
    }


def _claves_indice(doc_id: str, item: dict[str, str]) -> list[str]:
    claves = {doc_id.strip().upper(), item["codigo"].strip().upper()}
    return [c for c in claves if c]


def _limpiar_doc_del_indice(doc_id: str) -> None:
    for clave, val in list(_indice.items()):
        if val.get("_doc_id") == doc_id:
            del _indice[clave]


def _indexar(doc_id: str, item: dict[str, str]) -> None:
    item = {**item, "_doc_id": doc_id}
    for clave in _claves_indice(doc_id, item):
        _indice[clave] = item


def _cargar_indice_desde_lista(items: list[dict[str, str]]) -> None:
    _indice.clear()
    for row in items:
        item = {
            "codigo": row["codigo"],
            "descripcion": row["descripcion"],
            "ubicacion": row["ubicacion"],
        }
        _indexar(row["doc_id"], item)


def _cargar_desde_sqlite() -> bool:
    global _estado
    items = catalogo_cache.cargar_todos()
    if not items:
        return False
    with _lock:
        _cargar_indice_desde_lista(items)
        _estado = "listo"
    return True


def _necesita_sync_firestore(ultima: Optional[datetime]) -> bool:
    """
    Como máximo una sync Firestore por día calendario, a partir de HORA_SYNC.
    Excepción: si no hay caché local (primer arranque), sync de bootstrap.
    """
    if not catalogo_cache.tiene_datos():
        return True
    ahora = _ahora_local()
    if ahora.hour < HORA_SYNC:
        return False
    if ultima is None:
        return True
    ultima_local = ultima.astimezone(TZ) if ultima.tzinfo else ultima.replace(tzinfo=TZ)
    return ahora.date() > ultima_local.date()


def _get_db():
    global _db
    if _db is not None:
        return _db

    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
    except ImportError as exc:
        raise FirebaseNoConfigurado(
            "Falta la librería 'firebase-admin'. Instalá las dependencias del servicio."
        ) from exc

    if not os.path.exists(RUTA_CREDENCIALES):
        raise FirebaseNoConfigurado(
            f"No se encontró el archivo de credenciales en '{RUTA_CREDENCIALES}'."
        )

    if not firebase_admin._apps:
        cred = credentials.Certificate(RUTA_CREDENCIALES)
        firebase_admin.initialize_app(cred)
    _db = firestore.client()
    return _db


def _on_snapshot(col_snapshot, changes, read_time) -> None:
    global _estado
    from google.api_core import exceptions as gax

    if not changes:
        return

    try:
        upserts: list[tuple[str, dict[str, str]]] = []
        deletes: list[str] = []

        for change in changes:
            doc = change.document
            doc_id = doc.id
            if change.type.name in ("ADDED", "MODIFIED"):
                upserts.append((doc_id, _doc_a_item(doc_id, doc.to_dict() or {})))
            elif change.type.name == "REMOVED":
                deletes.append(doc_id)

        with _lock:
            for doc_id, item in upserts:
                _limpiar_doc_del_indice(doc_id)
                _indexar(doc_id, item)
            for doc_id in deletes:
                _limpiar_doc_del_indice(doc_id)
            _estado = "listo"

        for doc_id, item in upserts:
            catalogo_cache.upsert_item(
                doc_id, item["codigo"], item["descripcion"], item["ubicacion"]
            )
        for doc_id in deletes:
            catalogo_cache.eliminar_item(doc_id)

        catalogo_cache.marcar_sync(_ahora_local())
    except gax.ResourceExhausted as exc:
        raise FirebaseQuotaExcedida(
            "Cuota de lecturas de Firebase agotada. Las etiquetas simples siguen funcionando."
        ) from exc


def _detener_listener() -> None:
    global _watch
    if _watch is not None:
        try:
            _watch.unsubscribe()
        except Exception:
            pass
        _watch = None


def _iniciar_listener() -> None:
    global _estado, _watch
    _detener_listener()
    db = _get_db()
    col = db.collection(COLECCION_CATALOGO)
    with _lock:
        _estado = "sincronizando"
    _watch = col.on_snapshot(_on_snapshot)


def _intentar_cargar_o_sincronizar() -> None:
    global _estado

    if not os.path.exists(RUTA_CREDENCIALES):
        if _cargar_desde_sqlite():
            return
        with _lock:
            _estado = "sin_credenciales"
        return

    ultima = catalogo_cache.obtener_ultima_sync()
    if catalogo_cache.tiene_datos() and ultima is None:
        catalogo_cache.marcar_sync(_ahora_local())
        ultima = catalogo_cache.obtener_ultima_sync()

    if not _necesita_sync_firestore(ultima):
        if _cargar_desde_sqlite():
            return
        ahora = _ahora_local()
        if ahora.hour < HORA_SYNC:
            with _lock:
                _estado = "pendiente"
            return
        # Pasó la hora pero no hay SQLite (primer arranque del día).
        _iniciar_listener()
        return

    _iniciar_listener()


def _loop_sincronizacion() -> None:
    global _estado, _sync_thread_started

    try:
        catalogo_cache.init_db()
        _intentar_cargar_o_sincronizar()
    except FirebaseNoConfigurado:
        if not _cargar_desde_sqlite():
            with _lock:
                _estado = "sin_credenciales"
    except FirebaseQuotaExcedida:
        if _cargar_desde_sqlite():
            with _lock:
                _estado = "listo"
        else:
            with _lock:
                _estado = "cuota_excedida"
    except Exception:
        if not _cargar_desde_sqlite():
            with _lock:
                _estado = "error"

    while True:
        time.sleep(1800)
        try:
            if _necesita_sync_firestore(catalogo_cache.obtener_ultima_sync()):
                _iniciar_listener()
            elif _estado == "pendiente" and _ahora_local().hour >= HORA_SYNC:
                _intentar_cargar_o_sincronizar()
        except Exception:
            pass


def iniciar_sincronizacion_catalogo() -> None:
    global _sync_thread_started
    if _sync_thread_started:
        return
    _sync_thread_started = True
    threading.Thread(target=_loop_sincronizacion, daemon=True, name="catalogo-sync").start()


def inicializar_firebase() -> None:
    iniciar_sincronizacion_catalogo()


def estado_catalogo() -> dict[str, Any]:
    ultima = catalogo_cache.obtener_ultima_sync()
    with _lock:
        return {
            "estado": _estado,
            "articulos_indexados": len(_indice),
            "ultima_sync": ultima.isoformat() if ultima else None,
            "hora_sync_configurada": HORA_SYNC,
            "zona_horaria": str(TZ),
        }


def _variantes(codigo: str) -> list[str]:
    base = codigo.strip()
    upper = base.upper()
    out: list[str] = []
    for c in (upper, base):
        if c and c not in out:
            out.append(c)
    return out


def _item_publico(item: dict[str, str]) -> dict[str, str]:
    return {k: v for k, v in item.items() if not k.startswith("_")}


def buscar_catalogo(codigo: str) -> Optional[dict[str, str]]:
    """Busca SOLO en caché en memoria (0 lecturas Firestore por request)."""
    codigo = str(codigo).strip()
    if not codigo:
        return None

    with _lock:
        estado = _estado
        if estado == "sincronizando" and not _indice:
            raise CatalogoSincronizando(
                "El catálogo se está sincronizando. Reintentá en unos segundos."
            )
        if estado == "pendiente" and not _indice:
            raise CatalogoSincronizando(
                f"El catálogo se sincroniza a partir de las {HORA_SYNC}:00."
            )
        if estado == "cuota_excedida" and not _indice:
            raise FirebaseQuotaExcedida(
                "Cuota de Firebase agotada y sin caché local disponible."
            )
        if estado in ("sin_credenciales", "error") and not _indice:
            raise CatalogoNoDisponible("Catálogo no disponible.")

        for variante in _variantes(codigo):
            item = _indice.get(variante.upper())
            if item:
                return _item_publico(item)

    return None
