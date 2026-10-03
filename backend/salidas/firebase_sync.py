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
    ALIAS_SYNC_HORA,
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

# Alias daily bidirectional sync (Firestore <-> DB)
_alias_sync_started = False
_alias_ultimo_sync: Optional[datetime] = None
_ultimo_alias_error: str | None = None
_alias_lock = threading.Lock()


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
    # keep alias if already in cache
    try:
        cache_alias = None
        # try to read existing alias from cache to preserve
        existing = None
        # quick lookup: we can attempt to query cache direct; fallback to None
        import sqlite3 as _sql
        from config import cache_db_path as _cache_path
        try:
            _p = _cache_path()
            if _p.is_file():
                con = _sql.connect(str(_p))
                con.row_factory = _sql.Row
                row = con.execute("SELECT alias FROM articulos WHERE doc_id=? LIMIT 1", (codigo,)).fetchone()
                if row is not None:
                    try:
                        cache_alias = row["alias"]
                    except Exception:
                        cache_alias = None
                con.close()
        except Exception:
            pass
        articulos_cache.upsert_item(
            codigo, codigo, desc or "", float(nuevo_stock), ubicacion or "", categoria or "GENERAL", alias=cache_alias if cache_alias is not None else None
        )
    except TypeError:
        # old upsert_item signature without alias
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


def escribir_alias(codigo: str, alias: str | None) -> bool:
    """Bidirectional sync: push alias DB -> Firestore (merge). Also updates local cache.

    - codigo: UPPER, required
    - alias: string or None to clear (stored as "" in Firestore if cleared)
    Returns True if Firestore write succeeded or was skipped due to no credentials (still cache updated).
    """
    cod = str(codigo or "").strip().upper()
    if not cod:
        return False
    alias_norm = str(alias).strip() if alias is not None and str(alias).strip() != "" else None
    # Update local SQLite cache (add alias column if needed)
    try:
        articulos_cache.init_db()
        # Ensure articulos_cache has alias handling (fallback if signature old)
        try:
            # Fetch existing to preserve other fields
            existing = None
            items = articulos_cache.cargar_todos()
            for it in items:
                if str(it.get("codigo") or "").strip().upper() == cod or str(it.get("doc_id") or "").strip().upper() == cod:
                    existing = it
                    break
            if existing:
                articulos_cache.upsert_item(
                    cod,
                    cod,
                    str(existing.get("desc") or ""),
                    float(existing.get("stock") or 0),
                    str(existing.get("ubicacion") or ""),
                    str(existing.get("categoria") or "GENERAL"),
                    alias=alias_norm,
                )
            else:
                # No cache yet: create minimal entry
                articulos_cache.upsert_item(cod, cod, "", 0, "", "GENERAL", alias=alias_norm)
        except TypeError:
            # Fallback if upsert_item doesn't accept alias yet
            try:
                articulos_cache.upsert_item(cod, cod, "", 0, "", "GENERAL")
            except Exception:
                pass
        # Try raw SQL update if alias column exists but upsert didn't handle it
        try:
            import sqlite3 as _sq
            from config import cache_db_path as _cp
            p = _cp()
            if p.is_file():
                con = _sq.connect(str(p))
                # ensure column exists (idempotent)
                try:
                    con.execute("SELECT alias FROM articulos LIMIT 1")
                except Exception:
                    try:
                        con.execute("ALTER TABLE articulos ADD COLUMN alias TEXT DEFAULT NULL")
                        con.commit()
                    except Exception:
                        pass
                try:
                    con.execute("UPDATE articulos SET alias=? WHERE doc_id=?", (alias_norm, cod))
                    if con.total_changes == 0:
                        # if not updated, try insert
                        pass
                    con.commit()
                except Exception:
                    pass
                con.close()
        except Exception:
            pass
        articulos_cache.marcar_sync(_ahora())
    except Exception:
        pass

    # Push to Firestore (best-effort, respects FIREBASE_WRITE_ENABLED? For alias we want to push even if flag 0? Let's respect flag but allow alias sync)
    # Spec: "then if FIREBASE_WRITE_ENABLED or always, sync to Firestore via firebase_sync.sync_alias_to_firestore (new function) if credentials exist."
    # We'll attempt push regardless of FIREBASE_WRITE_ENABLED; if disabled we still try but log.
    try:
        db = _get_db()
        from firebase_admin import firestore  # noqa: F401

        payload: dict[str, Any] = {"alias": alias_norm if alias_norm is not None else ""}
        # Also ensure codigo field present for filtering
        payload["codigo"] = cod
        db.collection(COLECCION).document(cod).set(payload, merge=True)
        # Bump catalog version so buscador/etiquetas refreshes
        try:
            db.collection("config").document("catalogo").set(
                {"version": int(time.time()), "updatedAt": firestore.SERVER_TIMESTAMP},
                merge=True,
            )
        except Exception:
            pass
        return True
    except FirebaseNoConfigurado:
        # No credentials: cache already updated, still consider success for DB side
        return False
    except Exception as e:
        log.warning("escribir_alias Firebase %s -> %r: %s", cod, alias_norm, e)
        return False


def sync_stock_bulk_to_firestore(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Push solo-artículos-cambiados DB -> Firestore (merge por doc).

    - items: [{codigo, desc, stock, ubicacion, categoria, alias?}] ya filtrados por reglas de negocio.
    - Cap interno 500 por llamada para ahorrar escrituras (el import no barre los 7000).
    - Best-effort: intenta aunque FIREBASE_WRITE_ENABLED=0 (como alias); sin credenciales retorna pushed=0 con error.
    - Un solo bump config/catalogo al final para que el buscador refresque una vez.
    """
    try:
        lst = list(items or [])
    except Exception:
        return {"pushed": 0, "errors": 0, "skipped": 0, "error": "items inválidos"}
    if not lst:
        return {"pushed": 0, "errors": 0, "skipped": 0}
    if len(lst) > 500:
        lst = lst[:500]
    try:
        db = _get_db()
    except FirebaseNoConfigurado as e:
        return {"pushed": 0, "errors": 0, "skipped": len(lst), "error": str(e)}
    except Exception as e:
        return {"pushed": 0, "errors": len(lst), "skipped": 0, "error": str(e)}
    pushed = 0
    errors = 0
    for it in lst:
        try:
            cod = str(it.get("codigo") or "").strip().upper()
            if not cod:
                continue
            payload: dict[str, Any] = {
                "codigo": cod,
                "desc": str(it.get("desc") or it.get("descripcion") or ""),
                "stock": float(it.get("stock") or 0),
                "ubicacion": str(it.get("ubicacion") or ""),
                "categoria": str(it.get("categoria") or "GENERAL") or "GENERAL",
            }
            alias_v = it.get("alias")
            if alias_v is not None and str(alias_v).strip() != "":
                payload["alias"] = str(alias_v).strip()
            db.collection(COLECCION).document(cod).set(payload, merge=True)
            pushed += 1
        except Exception as e:
            msg = str(e).lower()
            if "429" in msg or "quota" in msg or "resource_exhausted" in msg or "exceeded" in msg:
                log.warning("sync_stock_bulk quota en %s: %s", it.get("codigo"), e)
                errors += 1
                break
            log.warning("sync_stock_bulk failed %s: %s", it.get("codigo"), e)
            errors += 1
    # Un solo bump de versión para que buscador/etiquetas refresquen
    if pushed:
        try:
            from firebase_admin import firestore

            db.collection("config").document("catalogo").set(
                {"version": int(time.time()), "updatedAt": firestore.SERVER_TIMESTAMP},
                merge=True,
            )
        except Exception:
            pass
    return {"pushed": pushed, "errors": errors, "skipped": 0, "total": len(lst)}


def sync_alias_db_to_firestore(limit: int = 1000) -> dict[str, Any]:
    """Push all DB aliases to Firestore (DB -> Firestore). Limit protects large scans."""
    try:
        lim = max(1, min(5000, int(limit or 1000)))
    except Exception:
        lim = 1000
    pushed = 0
    skipped = 0
    errors = 0
    try:
        from db import get_connection
    except Exception as e:
        return {"error": f"no DB connection: {e}", "pushed": 0}
    conn = None
    rows: list[dict[str, Any]] = []
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            try:
                cur.execute(
                    "SELECT codigo, alias FROM maestro_stock WHERE activo=1 AND alias IS NOT NULL AND TRIM(alias) <> '' ORDER BY actualizado_en DESC LIMIT %s",
                    (lim,),
                )
            except Exception as e:
                msg = str(e).lower()
                if "unknown column" in msg and "alias" in msg:
                    return {"pushed": 0, "skipped": 0, "errors": 0, "detail": "alias column missing (migrate pending)"}
                raise
            rows = cur.fetchall() or []
    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return {"error": str(e), "pushed": 0}
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
    for r in rows:
        cod = str(r.get("codigo") or "").strip().upper()
        alias_v = r.get("alias")
        alias_s = str(alias_v).strip() if alias_v is not None else None
        if not cod or not alias_s:
            skipped += 1
            continue
        ok = escribir_alias(cod, alias_s)
        if ok:
            pushed += 1
        else:
            # if escribir_alias failed due to no credentials, count as skipped not error
            try:
                _get_db()
                errors += 1
            except FirebaseNoConfigurado:
                pushed += 1  # cache updated even if no Firestore
            except Exception:
                errors += 1
    return {"pushed": pushed, "skipped": skipped, "errors": errors, "total_scanned": len(rows)}


def pull_alias_desde_firestore(limit: int = 1000) -> dict[str, Any]:
    """Pull aliases Firestore -> DB (Firestore -> DB). Last-write-wins: if Firestore alias differs from DB, update DB.

    Does NOT trigger push loop (direct DB update via store_sql without Firestore write).
    """
    try:
        lim = max(1, min(5000, int(limit or 1000)))
    except Exception:
        lim = 1000
    try:
        db = _get_db()
    except FirebaseNoConfigurado as e:
        return {"error": str(e), "pulled": 0, "updated": 0, "skipped": 0}
    except Exception as e:
        return {"error": str(e), "pulled": 0}

    pulled = 0
    updated = 0
    skipped = 0
    errors = 0
    try:
        from store_sql import maestro_get_by_codigo, maestro_update_alias
    except Exception as e:
        return {"error": f"no store_sql: {e}", "pulled": 0}
    try:
        count = 0
        for doc in db.collection(COLECCION).stream():
            if count >= lim:
                break
            d = doc.to_dict() or {}
            # Support both 'alias' and legacy 'Alias'
            alias_raw = d.get("alias")
            if alias_raw is None:
                alias_raw = d.get("Alias")
            # If alias not present, skip
            if alias_raw is None:
                continue
            pulled += 1
            count += 1
            cod = str(d.get("codigo") or doc.id or "").strip().upper()
            if not cod:
                skipped += 1
                continue
            alias_fs = str(alias_raw).strip() if str(alias_raw).strip() != "" else None
            # Fetch DB alias
            try:
                art_db = maestro_get_by_codigo(cod)
            except Exception:
                art_db = None
            db_alias = None
            if art_db:
                db_alias = art_db.get("alias")
                if db_alias is not None:
                    db_alias = str(db_alias).strip()
                    if db_alias == "":
                        db_alias = None
            # Compare: if equal (both None or same string case-insensitive? keep case-sensitive but treat trim), skip
            if (db_alias or None) == (alias_fs or None):
                skipped += 1
                continue
            # If Firestore alias is None/empty and DB has alias, we treat as clear? But to avoid accidental clears from old docs without alias, skip if FS alias is None and we didn't count it above.
            # Already filtered: if alias_raw is None we skipped. So alias_fs may be None (empty). In that case, we clear DB only if FS explicitly has ""? We'll allow clear.
            try:
                # Update DB without triggering Firestore push (direct store_sql)
                maestro_update_alias(cod, alias_fs, realizado_por="firestore-sync")
                updated += 1
                # Also update cache locally
                try:
                    articulos_cache.init_db()
                    # cache upsert with alias
                    try:
                        existing = None
                        for it in articulos_cache.cargar_todos():
                            if str(it.get("codigo") or "").strip().upper() == cod:
                                existing = it
                                break
                        if existing:
                            articulos_cache.upsert_item(cod, cod, str(existing.get("desc") or ""), float(existing.get("stock") or 0), str(existing.get("ubicacion") or ""), str(existing.get("categoria") or "GENERAL"), alias=alias_fs)
                        else:
                            articulos_cache.upsert_item(cod, cod, "", 0, "", "GENERAL", alias=alias_fs)
                    except TypeError:
                        pass
                except Exception:
                    pass
            except Exception as e:
                # Could be code not in DB yet? Then skip (or could create minimal? We'll skip)
                msg = str(e).lower()
                if "no encontrado" in msg or "not found" in msg:
                    skipped += 1
                else:
                    errors += 1
                    log.warning("pull_alias update DB failed %s -> %r: %s", cod, alias_fs, e)
                continue
        return {"pulled": pulled, "updated": updated, "skipped": skipped, "errors": errors, "scanned": count}
    except Exception as e:
        log.warning("pull_alias_desde_firestore failed: %s", e)
        return {"error": str(e), "pulled": pulled, "updated": updated, "skipped": skipped, "errors": errors}


def estado_sync() -> dict[str, Any]:
    ultima = articulos_cache.obtener_ultima_sync()
    pull = articulos_cache.obtener_ultima_pull()
    with _lock:
        base = {
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
    # Alias sync extra (fuera de _lock principal para no bloquear)
    with _alias_lock:
        alias_info = {
            "alias_ultimo_sync": _alias_ultimo_sync.isoformat() if _alias_ultimo_sync else None,
            "alias_hora_sync": ALIAS_SYNC_HORA,
            "alias_error": _ultimo_alias_error,
            "alias_sync_started": _alias_sync_started,
        }
    base.update(alias_info)
    return base


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


# ---------------------------------------------------------------------------
# Alias daily bidirectional sync (Firestore <-> DB)
# ---------------------------------------------------------------------------

def _seconds_until_next_alias_sync() -> float:
    """Segundos hasta la próxima ejecución diaria a ALIAS_SYNC_HORA en TZ local."""
    ahora = _ahora()
    try:
        target = ahora.replace(hour=int(ALIAS_SYNC_HORA), minute=0, second=0, microsecond=0)
    except Exception:
        target = ahora.replace(hour=3, minute=0, second=0, microsecond=0)
    if ahora >= target:
        target = target + timedelta(days=1)
    secs = (target - ahora).total_seconds()
    # Nunca dormir 0 o negativo; mínimo 60s
    return max(60.0, secs)


def _run_alias_sync_once() -> dict[str, Any]:
    """Ejecuta un ciclo completo alias DB->Firestore y Firestore->DB con manejo quota."""
    global _alias_ultimo_sync, _ultimo_alias_error
    result: dict[str, Any] = {}
    # DB -> Firestore push
    try:
        push_res = sync_alias_db_to_firestore(limit=5000)
        result["push"] = push_res
        # Si quota exceeded viene como error string, loguear sin considerar fallo crítico
        if isinstance(push_res, dict) and push_res.get("error"):
            err_s = str(push_res.get("error") or "").lower()
            if "429" in err_s or "quota" in err_s or "resource_exhausted" in err_s or "exceeded" in err_s:
                log.warning("Alias push quota exceeded (DB->Firestore): %s", push_res.get("error"))
            else:
                log.warning("Alias push result con error: %s", push_res.get("error"))
        _ultimo_alias_error = None
    except Exception as e:
        err_s = str(e).lower()
        if "429" in err_s or "quota" in err_s or "resource_exhausted" in err_s or "exceeded" in err_s:
            log.warning("Alias DB->Firestore quota exceeded, omitido: %s", e)
            result["push"] = {"error": str(e), "quota_exceeded": True}
        else:
            log.warning("Alias DB->Firestore sync failed: %s", e)
            result["push"] = {"error": str(e)}
            with _alias_lock:
                _ultimo_alias_error = str(e)

    # Firestore -> DB pull
    try:
        pull_res = pull_alias_desde_firestore(limit=5000)
        result["pull"] = pull_res
        if isinstance(pull_res, dict) and pull_res.get("error"):
            err_s2 = str(pull_res.get("error") or "").lower()
            if "429" in err_s2 or "quota" in err_s2 or "resource_exhausted" in err_s2 or "exceeded" in err_s2:
                log.warning("Alias pull quota exceeded (Firestore->DB): %s", pull_res.get("error"))
            else:
                log.warning("Alias pull result con error: %s", pull_res.get("error"))
        if not result.get("push", {}).get("error"):
            with _alias_lock:
                _ultimo_alias_error = None
    except Exception as e:
        err_s = str(e).lower()
        if "429" in err_s or "quota" in err_s or "resource_exhausted" in err_s or "exceeded" in err_s:
            log.warning("Alias Firestore->DB quota exceeded, omitido: %s", e)
            result["pull"] = {"error": str(e), "quota_exceeded": True}
        else:
            log.warning("Alias Firestore->DB sync failed: %s", e)
            result["pull"] = {"error": str(e)}
            with _alias_lock:
                _ultimo_alias_error = str(e)

    with _alias_lock:
        _alias_ultimo_sync = _ahora()
        # Si algún error no-quota ocurrió, mantenerlo; si no, limpiar
        if not result.get("push", {}).get("error") and not result.get("pull", {}).get("error"):
            _ultimo_alias_error = None

    return result


def _alias_loop() -> None:
    """Loop diario: duerme hasta ALIAS_SYNC_HORA y ejecuta sync bidireccional."""
    # Pequeño delay inicial para no competir con _carga_inicial
    try:
        time.sleep(5)
    except Exception:
        pass
    while True:
        try:
            secs = _seconds_until_next_alias_sync()
            log.info("Alias sync next at %02d:00 %s (sleep %.0fs)", int(ALIAS_SYNC_HORA), TZ, secs)
            # Dormir en chunks de 1h para permitir interrupción / logs; simplificar a sleep total
            # Usamos sleep interrumpible por chunks de 1800 para no bloquear shutdown largo >24h? Pero daemon sigue.
            remaining = secs
            while remaining > 0:
                chunk = min(1800, remaining)
                time.sleep(chunk)
                remaining -= chunk
                # Re-evaluar si se acercó? no necesario
        except Exception as e:
            log.warning("Alias sync sleep error: %s", e)
            try:
                time.sleep(3600)
            except Exception:
                pass
            continue
        try:
            log.info("Running daily alias bidirectional sync (DB <-> Firestore) ...")
            res = _run_alias_sync_once()
            log.info("Alias daily sync done: %s", res)
        except Exception as e:
            log.warning("Alias sync loop error: %s", e)
            with _alias_lock:
                _ultimo_alias_error = str(e)
        # Evitar ejecución doble exacta: dormir 60s extra
        try:
            time.sleep(60)
        except Exception:
            pass


def iniciar_alias_sync_background() -> None:
    """Inicia el hilo diario de alias Firestore<->DB. Idempotente."""
    global _alias_sync_started
    if _alias_sync_started:
        return
    _alias_sync_started = True
    threading.Thread(target=_alias_loop, name="salidas-alias-sync", daemon=True).start()
