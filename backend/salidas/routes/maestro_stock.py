# -*- coding: utf-8 -*-
"""Maestro stock import and query routes for Salidas service.

Purpose: Migrates master_codes Excel (ARTICULOS) into maestro_stock MariaDB
         and exposes import endpoint with business-rule-aware merge.
Endpoints:
  POST /api/maestro-stock/import   multipart files (1..N xlsx) classified by
                                   filename (detallado/valorizado/general).
  GET  /api/maestro-stock           paginated list with filters.
  GET  /api/maestro-stock/import-log last 20 imports.
  GET  /api/maestro-stock/stats     total, sin_precio, criticos.
Business rules: empty never overwrites; price 0 never overwrites price >0.
File-type merge: detallado -> only minimo+ubicacion; valorizado -> stock+resto
                 (no minimo); general -> resto without stock/minimo.
Propagation: on price change, update salida_historial for current month.
Created: 2026-09-18 for migration master_codes -> maestro_stock.
"""

from __future__ import annotations

import io
import re
import time
import unicodedata
import logging
from datetime import date, datetime
from typing import Any

import pandas as pd
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse

from config import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER
from db import get_connection, verificar_permiso

import pymysql
from pymysql.cursors import DictCursor

log = logging.getLogger("salidas.maestro_stock")

# ---------------------------------------------------------------------------
# Helpers: normalization & column detection (simplified scoring like desktop)
# ---------------------------------------------------------------------------

def _norm_header(name: Any) -> str:
    s = str(name or "").strip().lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return s.strip()

def _norm_nospace(name: Any) -> str:
    return _norm_header(name).replace(" ", "").replace("_", "").replace("-", "").replace(".", "")

def _limpiar_codigo(val: Any) -> str:
    if val is None:
        return ""
    try:
        if pd.isna(val):
            return ""
    except Exception:
        pass
    s = str(val).strip().upper()
    if not s or s in ("NAN", "NONE", "NULL"):
        return ""
    if s.endswith(".0"):
        base = s[:-2]
        if base and (base.isdigit() or (base.startswith("-") and base[1:].isdigit())):
            s = base
    s = re.sub(r"\.0$", "", s)
    s = s.strip()
    if s in ("NAN", "NONE", ""):
        return ""
    return s

def _parse_decimal(val: Any) -> float | None:
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except Exception:
        pass
    if isinstance(val, (int, float)):
        try:
            f = float(val)
            if pd.isna(f):
                return None
            return f
        except Exception:
            return None
    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", "-", ""):
        return None
    s = s.replace("$", "").replace(" ", "").replace("\u00a0", "")
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        parts = s.split(",")
        if len(parts[-1]) <= 2:
            s = ",".join(parts[:-1]).replace(".", "") + "." + parts[-1]
        else:
            s = s.replace(",", "")
    try:
        return round(float(s), 2)
    except ValueError:
        try:
            v = pd.to_numeric(s, errors="coerce")
            if pd.isna(v):
                return None
            return round(float(v), 2)
        except Exception:
            return None

def _normalize_importancia(val: Any) -> str:
    s = str(val or "").strip().upper()
    if not s or s in ("NAN", "NONE"):
        return "BASE"
    sn = _norm_header(s).replace("_", " ").replace("-", " ")
    if "crit" in sn:
        return "CRITICO"
    if "alta" in sn and ("freq" in sn.replace(" ", "") or "frecuencia" in sn):
        return "ALTA FRECUENCIA"
    if s in ("CRITICO", "ALTA FRECUENCIA", "BASE"):
        return s
    return "BASE"

def _valor_util(val: Any) -> bool:
    if val is None:
        return False
    try:
        if pd.isna(val):
            return False
    except Exception:
        pass
    if isinstance(val, str):
        if not val.strip():
            return False
        if val.strip().lower() in ("nan", "#n/a"):
            return False
    return True

def _detectar_columnas(df: pd.DataFrame) -> dict[str, str]:
    cols = list(df.columns)
    norm_map = {_norm_header(c): c for c in cols}
    nospace_map = {_norm_nospace(c): c for c in cols}
    result: dict[str, str] = {}
    for cand in ("codigo", "cod", "sku", "code", "codigoproducto", "articulocodigo"):
        if cand in nospace_map:
            result["codigo"] = nospace_map[cand]
            break
    if "codigo" not in result:
        for c in cols:
            nh = _norm_header(c)
            if nh in ("codigo", "cod", "sku") or nh.startswith("codigo"):
                result["codigo"] = c
                break
    # descripcion
    for c in cols:
        nh = _norm_header(c)
        if nh in ("descripcion", "articulo", "detalle", "nombre", "desc"):
            result["descripcion"] = c
            break
    if "descripcion" not in result:
        for c in cols:
            nh = _norm_header(c)
            if "desc" in nh or "detalle" in nh or "nombre" in nh:
                if "precio" not in nh and "costo" not in nh:
                    result["descripcion"] = c
                    break
    # stock actual scoring
    scored: list[tuple[int, str]] = []
    for c in cols:
        nhr = _norm_nospace(c)
        if "precio" in nhr or nhr == "codigo":
            continue
        if "importancia" in nhr:
            continue
        if ("min" in nhr or "minimo" in nhr) and "act" not in nhr and "actual" not in nhr and "cant" not in nhr and "disp" not in nhr:
            continue
        score = 0
        if "actual" in nhr or nhr.endswith("act"):
            score += 100
        if "dispon" in nhr:
            score += 90
        if "stock" in nhr and "min" not in nhr:
            score += 70
        if "cant" in nhr or "qty" in nhr:
            score += 65
        if "minimo" in nhr or (nhr.startswith("min") and "stock" not in nhr):
            score -= 100
        if score > 0:
            scored.append((score, c))
    if scored:
        scored.sort(key=lambda x: -x[0])
        result["stock"] = scored[0][1]
    else:
        for c in cols:
            nh = _norm_nospace(c)
            if "minimo" in nh or nh == "min" or (nh.endswith("min") and "act" not in nh and "cant" not in nh):
                continue
            sl = str(c).lower()
            if "stock" in sl or "act" in sl or "cant" in sl:
                result["stock"] = c
                break
    # stock minimo
    for c in cols:
        nh = _norm_nospace(c)
        if nh in ("min", "minimo") or "minimo" in nh or nh.endswith("min"):
            result["stock_minimo"] = c
            break
    if "stock_minimo" not in result:
        for c in cols:
            nh = _norm_header(c)
            if "min" in nh:
                result["stock_minimo"] = c
                break
    # precio
    for c in cols:
        nh = _norm_nospace(c)
        if nh in ("preciounitario", "pu", "punit", "costouni"):
            result["precio_unitario"] = c
            break
    if "precio_unitario" not in result:
        for c in cols:
            nh = _norm_header(c)
            if "precio" in nh:
                result["precio_unitario"] = c
                break
            if "costo" in nh and "uni" in nh:
                result["precio_unitario"] = c
                break
    # ubicacion
    for c in cols:
        nh = _norm_header(c)
        if "ubic" in nh:
            result["ubicacion"] = c
            break
    if "ubicacion" not in result:
        for c in cols:
            nh = _norm_header(c)
            if "estant" in nh or "almacen" in nh:
                result["ubicacion"] = c
                break
    # importancia
    for c in cols:
        nh = _norm_header(c)
        if "importancia" in nh or "criticidad" in nh or "crit" in nh:
            # avoid picking descripcion
            if c != result.get("descripcion") and c != result.get("precio_unitario"):
                result["importancia"] = c
                break
    # categoria
    for c in cols:
        nh = _norm_header(c)
        if nh in ("categoria", "familia", "rubro", "grupo"):
            result["categoria"] = c
            break
    if "categoria" not in result:
        for c in cols:
            nh = _norm_header(c)
            if "categoria" in nh or "familia" in nh:
                result["categoria"] = c
                break
    return result

def _tipo_archivo(nombre: str) -> str:
    n = str(nombre or "").lower()
    if "detallado" in n:
        return "detallado"
    if "valorizado" in n:
        return "valorizado"
    return "general"

def _ensure_tables(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS `maestro_stock` (
              `codigo` VARCHAR(40) COLLATE utf8mb4_unicode_ci NOT NULL,
              `descripcion` TEXT COLLATE utf8mb4_unicode_ci NOT NULL,
              `alias` VARCHAR(300) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Alias de busqueda, ej T10 para tornillo 10mm',
              `stock` DECIMAL(10,2) NOT NULL DEFAULT 0.00,
              `stock_minimo` DECIMAL(10,2) NOT NULL DEFAULT 0.00,
              `ubicacion` VARCHAR(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
              `precio_unitario` DECIMAL(12,2) NOT NULL DEFAULT 0.00,
              `importancia` ENUM('CRITICO','ALTA FRECUENCIA','BASE') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'BASE',
              `categoria` VARCHAR(80) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
              `activo` TINYINT(1) NOT NULL DEFAULT 1,
              `creado_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              `actualizado_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
              PRIMARY KEY (`codigo`),
              KEY `idx_maestro_stock_ubicacion` (`ubicacion`),
              KEY `idx_maestro_stock_importancia` (`importancia`),
              KEY `idx_maestro_stock_categoria` (`categoria`),
              KEY `idx_maestro_stock_alias` (`alias`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        )
        # Idempotent migration for existing DBs without alias column/index
        try:
            cur.execute(
                """
                SELECT COUNT(*) AS c FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME='maestro_stock' AND COLUMN_NAME='alias'
                """
            )
            _r = cur.fetchone()
            if _r and int(_r.get("c", 0)) == 0:
                try:
                    cur.execute(
                        "ALTER TABLE `maestro_stock` ADD COLUMN `alias` VARCHAR(300) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Alias de busqueda, ej T10 para tornillo 10mm' AFTER `descripcion`"
                    )
                except Exception:
                    try:
                        cur.execute(
                            "ALTER TABLE `maestro_stock` ADD COLUMN `alias` VARCHAR(300) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Alias de busqueda, ej T10 para tornillo 10mm'"
                        )
                    except Exception:
                        pass
        except Exception:
            pass
        try:
            cur.execute(
                "SELECT COUNT(*) AS c FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME='maestro_stock' AND INDEX_NAME='idx_maestro_stock_alias'"
            )
            _rx = cur.fetchone()
            if _rx and int(_rx.get("c", 0)) == 0:
                try:
                    cur.execute("ALTER TABLE `maestro_stock` ADD INDEX `idx_maestro_stock_alias` (`alias`)")
                except Exception:
                    pass
        except Exception:
            pass
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS `maestro_stock_import_log` (
              `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
              `archivo_origen` VARCHAR(255) COLLATE utf8mb4_unicode_ci NOT NULL,
              `tipo_archivo` ENUM('detallado','valorizado','general') COLLATE utf8mb4_unicode_ci NOT NULL,
              `codigos_nuevos` INT NOT NULL DEFAULT 0,
              `codigos_sin_precio` INT NOT NULL DEFAULT 0,
              `duracion_ms` INT NOT NULL DEFAULT 0,
              `reporte` TEXT COLLATE utf8mb4_unicode_ci DEFAULT NULL,
              `creado_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY (`id`),
              KEY `idx_import_log_tipo` (`tipo_archivo`),
              KEY `idx_import_log_creado` (`creado_en`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        )
        # --- compat: ensure codigos_modificados exists (older installs) ---
        try:
            cur.execute(
                "SELECT COUNT(*) AS c FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='maestro_stock_import_log' AND COLUMN_NAME='codigos_modificados'"
            )
            _r2 = cur.fetchone()
            if _r2 and int(_r2.get("c", 0)) == 0:
                try:
                    cur.execute("ALTER TABLE `maestro_stock_import_log` ADD COLUMN `codigos_modificados` INT NOT NULL DEFAULT 0 AFTER `codigos_nuevos`")
                except Exception:
                    pass
        except Exception:
            pass
        # --- enriched counters for diff/persisted history (B) ---
        for _col in ("precios_modificados", "stock_altas", "stock_bajas", "stock_min_mod", "ubic_mod", "otros_mod", "precios_propagados", "propagated_rows"):
            try:
                cur.execute(
                    "SELECT COUNT(*) AS c FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='maestro_stock_import_log' AND COLUMN_NAME=%s",
                    (_col,),
                )
                _rc = cur.fetchone()
                if _rc and int(_rc.get("c", 0)) == 0:
                    try:
                        cur.execute(f"ALTER TABLE `maestro_stock_import_log` ADD COLUMN `{_col}` INT NOT NULL DEFAULT 0")
                    except Exception:
                        pass
            except Exception:
                pass
        # --- audit trail table (per-field history) ---
        try:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS `maestro_stock_audit` (
                  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                  `codigo` VARCHAR(40) COLLATE utf8mb4_unicode_ci NOT NULL,
                  `campo` VARCHAR(40) COLLATE utf8mb4_unicode_ci NOT NULL,
                  `valor_antes` TEXT COLLATE utf8mb4_unicode_ci NULL,
                  `valor_despues` TEXT COLLATE utf8mb4_unicode_ci NOT NULL,
                  `archivo_origen` VARCHAR(255) COLLATE utf8mb4_unicode_ci NOT NULL,
                  `tipo_archivo` ENUM('detallado','valorizado','general') COLLATE utf8mb4_unicode_ci NOT NULL,
                  `import_log_id` INT UNSIGNED NOT NULL,
                  `creado_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY (`id`),
                  KEY `idx_audit_codigo` (`codigo`),
                  KEY `idx_audit_import` (`import_log_id`),
                  KEY `idx_audit_creado` (`creado_en`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
        except Exception as _e:
            # Fallback without FK if the CREATE failed due to engine quirks
            try:
                log.warning("maestro_stock_audit CREATE fallback: %s", _e)
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS `maestro_stock_audit` (
                      `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                      `codigo` VARCHAR(40) COLLATE utf8mb4_unicode_ci NOT NULL,
                      `campo` VARCHAR(40) COLLATE utf8mb4_unicode_ci NOT NULL,
                      `valor_antes` TEXT COLLATE utf8mb4_unicode_ci NULL,
                      `valor_despues` TEXT COLLATE utf8mb4_unicode_ci NULL,
                      `archivo_origen` VARCHAR(255) COLLATE utf8mb4_unicode_ci NOT NULL,
                      `tipo_archivo` VARCHAR(20) COLLATE utf8mb4_unicode_ci NOT NULL,
                      `import_log_id` INT UNSIGNED NOT NULL,
                      `creado_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                      PRIMARY KEY (`id`),
                      KEY `idx_audit_codigo` (`codigo`),
                      KEY `idx_audit_import` (`import_log_id`),
                      KEY `idx_audit_creado` (`creado_en`)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                )
            except Exception:
                pass
    conn.commit()

def _propagar_precio(conn, codigo: str, precio: float) -> int:
    """Update salida_historial current month prices for codigo. Returns rows affected."""
    try:
        today = date.today()
        inicio = date(today.year, today.month, 1)
        # last day
        if today.month == 12:
            fin = date(today.year + 1, 1, 1)
        else:
            fin = date(today.year, today.month + 1, 1)
        # Use BETWEEN inclusive of inicio, exclusive of next month start
        with conn.cursor() as cur:
            # Check table exists
            cur.execute(
                "SELECT COUNT(*) AS c FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='salida_historial'"
            )
            row = cur.fetchone()
            if not row or int(row.get("c", 0)) == 0:
                log.warning("salida_historial not exists, skip propagation for %s", codigo)
                return 0
            cur.execute(
                """
                UPDATE salida_historial
                SET precio_unitario=%s, monto_total=ABS(cantidad)*%s
                WHERE codigo=%s AND fecha >= %s AND fecha < %s
                """,
                (precio, abs(float(precio)), codigo, inicio.isoformat(), fin.isoformat()),
            )
            return int(cur.rowcount or 0)
    except Exception as e:
        log.warning("Price propagation failed for %s: %s", codigo, e)
        return 0

def _token(request: Request) -> str:
    auth = request.headers.get("authorization", "") or request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return (request.headers.get("x-token", "") or request.headers.get("X-Token", "") or "").strip()

# ---------------------------------------------------------------------------
# Core import logic (blocking, run in threadpool)
# ---------------------------------------------------------------------------

def _process_single_file(filename: str, content: bytes) -> dict[str, Any]:
    tipo = _tipo_archivo(filename)
    t0 = time.time()
    reporte_lines: list[str] = []
    reporte_lines.append(f"File: {filename} ({tipo})")
    codigos_nuevos = 0
    codigos_modificados = 0
    precios_modificados = 0
    stock_altas = 0
    stock_bajas = 0
    stock_min_mod = 0
    ubic_mod = 0
    otros_mod = 0
    precios_propagados = 0
    precios_map: dict[str, float] = {}
    # Audit rows pending until import_log_id is known (codigo, campo, antes, despues)
    pending_audits: list[tuple[str, str, str | None, str]] = []
    # Códigos efectivamente cambiados (NEW + MOD) para push Firestore (solo cambiados, no barrer 7000)
    changed_codigos: set[str] = set()

    conn = get_connection()
    # ensure autocommit False (get_connection already)
    try:
        _ensure_tables(conn)
        # Load Excel
        try:
            bio = io.BytesIO(content)
            xls = pd.ExcelFile(bio, engine="openpyxl")
        except Exception as e:
            raise ValueError(f"Cannot open Excel {filename}: {e}")

        # For each sheet
        for sheet_name in xls.sheet_names:
            try:
                df_raw = pd.read_excel(xls, sheet_name=sheet_name, dtype=object)
            except Exception as e:
                reporte_lines.append(f"  Sheet {sheet_name} error: {e}")
                continue
            if df_raw is None or df_raw.empty:
                continue
            df_raw = df_raw.dropna(axis=1, how="all")
            df_raw = df_raw.dropna(axis=0, how="all")
            if df_raw.empty:
                continue
            # Normalize column names for detection: strip
            # Keep original for mapping
            col_map = _detectar_columnas(df_raw)
            if "codigo" not in col_map:
                reporte_lines.append(f"  Sheet {sheet_name}: no codigo column, skipped ({list(df_raw.columns)[:5]})")
                continue
            col_codigo = col_map["codigo"]
            # Iterate rows
            for _, fila in df_raw.iterrows():
                cod = _limpiar_codigo(fila.get(col_codigo))
                if not cod:
                    continue
                # Prepare incoming values (only if util)
                inc: dict[str, Any] = {}
                # Descripcion
                if "descripcion" in col_map:
                    v = fila.get(col_map["descripcion"])
                    if _valor_util(v):
                        s = str(v).strip()
                        if s:
                            inc["descripcion"] = s.upper() if s.isupper() or len(s) < 200 else s
                            # Keep original casing? Upper like desktop
                            inc["descripcion"] = s.upper()
                # Stock actual
                if "stock" in col_map:
                    v = fila.get(col_map["stock"])
                    if _valor_util(v):
                        pv = _parse_decimal(v)
                        if pv is not None:
                            inc["stock"] = float(pv)
                # Stock minimo
                if "stock_minimo" in col_map:
                    v = fila.get(col_map["stock_minimo"])
                    if _valor_util(v):
                        pv = _parse_decimal(v)
                        if pv is not None:
                            inc["stock_minimo"] = float(pv)
                # Ubicacion
                if "ubicacion" in col_map:
                    v = fila.get(col_map["ubicacion"])
                    if _valor_util(v):
                        s = str(v).strip()
                        if s:
                            inc["ubicacion"] = s
                # Precio
                if "precio_unitario" in col_map:
                    v = fila.get(col_map["precio_unitario"])
                    if _valor_util(v):
                        pv = _parse_decimal(v)
                        if pv is not None:
                            inc["precio_unitario"] = float(pv)
                # Importancia
                if "importancia" in col_map:
                    v = fila.get(col_map["importancia"])
                    if _valor_util(v):
                        inc["importancia"] = _normalize_importancia(v)
                # Categoria
                if "categoria" in col_map:
                    v = fila.get(col_map["categoria"])
                    if _valor_util(v):
                        s = str(v).strip()
                        if s:
                            inc["categoria"] = s

                # Apply file-type filtering:
                # detallado: only stock_minimo + ubicacion
                # valorizado: stock + resto (exclude stock_minimo)
                # general: resto without stock/stock_minimo
                filtered: dict[str, Any] = {}
                if tipo == "detallado":
                    for k in ("stock_minimo", "ubicacion"):
                        if k in inc:
                            filtered[k] = inc[k]
                elif tipo == "valorizado":
                    # stock + resto, but not stock_minimo
                    for k, v in inc.items():
                        if k == "stock_minimo":
                            continue
                        filtered[k] = v
                else:  # general
                    for k, v in inc.items():
                        if k in ("stock", "stock_minimo"):
                            continue
                        filtered[k] = v

                if not filtered and cod:
                    # No useful data for this code per rules; skip
                    continue

                # Fetch existing
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM maestro_stock WHERE codigo=%s", (cod,))
                    existing = cur.fetchone()

                # Guard EL vs ELE: detectar M1622EL cuando ya existe M1622ELE misma descripción (typo truncado)
                if cod.endswith("EL") and not cod.endswith("ELE"):
                    _ele = cod + "E"
                    try:
                        with conn.cursor() as _ck:
                            _ck.execute("SELECT codigo, descripcion FROM maestro_stock WHERE codigo=%s", (_ele,))
                            _row_ele = _ck.fetchone()
                            if _row_ele:
                                _desc_new = (filtered.get("descripcion") or (existing.get("descripcion") if existing else "") or "")
                                _desc_ele = str(_row_ele.get("descripcion") or "")
                                if _desc_new and _desc_ele and _desc_new.strip().upper() == _desc_ele.strip().upper():
                                    reporte_lines.append(
                                        f"  ! WARN {cod} -> posible duplicado truncado de {_ele} (EL vs ELE) misma descr '{_desc_new[:45]}' — verificar Excel origen y corregir a ELE"
                                    )
                                    log.warning("EL/ELE duplicate guard: %s vs %s same desc", cod, _ele)
                                else:
                                    reporte_lines.append(f"  ! WARN {cod} termina en EL y existe {_ele} — verificar sufijo EL vs ELE")
                    except Exception:
                        pass

                if existing is None:
                    # Insert new: use filtered + defaults
                    # Need descripcion NOT NULL
                    desc = filtered.get("descripcion") or cod
                    stock = filtered.get("stock", 0)
                    stock_min = filtered.get("stock_minimo", 0)
                    ubic = filtered.get("ubicacion")
                    precio = filtered.get("precio_unitario", 0)
                    # Price 0 is fine for new (no existing to preserve)
                    imp = filtered.get("importancia", "BASE")
                    cat = filtered.get("categoria")
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO maestro_stock
                              (codigo, descripcion, stock, stock_minimo, ubicacion, precio_unitario, importancia, categoria, activo)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,1)
                            """,
                            (cod, desc, stock, stock_min, ubic, precio, imp, cat),
                        )
                    codigos_nuevos += 1
                    reporte_lines.append(f"  + NEW {cod} ({tipo}): {', '.join(f'{k}={v}' for k,v in filtered.items())}")
                    changed_codigos.add(cod)
                    # Audit NEW as creation (valor_antes NULL)
                    for _ak, _av in filtered.items():
                        if len(pending_audits) < 5000:
                            pending_audits.append((cod, _ak, None, str(_av)))
                    if "precio_unitario" in filtered and float(filtered["precio_unitario"]) > 0:
                        precios_map[cod] = float(filtered["precio_unitario"])
                else:
                    # Update existing with business rules
                    updates: dict[str, Any] = {}
                    changed = False
                    # For each filtered key, check rules
                    for k, v_new in filtered.items():
                        v_old = existing.get(k)
                        # Empty handled already via _valor_util
                        # Price rule: 0 does not overwrite >0
                        if k == "precio_unitario":
                            try:
                                old_price = round(float(v_old or 0), 2)
                            except Exception:
                                old_price = 0
                            try:
                                new_price = round(float(v_new or 0), 2)
                            except Exception:
                                new_price = 0
                            if new_price == 0 and old_price > 0:
                                continue
                            if round(old_price, 2) == round(new_price, 2):
                                continue
                            updates[k] = new_price
                            changed = True
                            precios_map[cod] = new_price
                        else:
                            # Generic: if values differ, update
                            # Normalize comparison
                            if v_old is None:
                                v_old_cmp = ""
                            else:
                                v_old_cmp = str(v_old).strip()
                            v_new_cmp = str(v_new).strip()
                            # For numeric stock fields, compare as float
                            if k in ("stock", "stock_minimo"):
                                try:
                                    if round(float(v_old or 0), 2) == round(float(v_new), 2):
                                        continue
                                    updates[k] = round(float(v_new), 2)
                                    changed = True
                                except Exception:
                                    if v_old_cmp == v_new_cmp:
                                        continue
                                    updates[k] = v_new
                                    changed = True
                            else:
                                # For IMPORTANCIA etc, compare upper
                                if k == "importancia":
                                    if str(v_old or "").strip().upper() == str(v_new).strip().upper():
                                        continue
                                elif v_old_cmp == v_new_cmp:
                                    continue
                                updates[k] = v_new
                                changed = True
                    if changed and updates:
                        set_clause = ", ".join(f"`{k}`=%s" for k in updates.keys())
                        params = list(updates.values()) + [cod]
                        with conn.cursor() as cur:
                            cur.execute(f"UPDATE maestro_stock SET {set_clause} WHERE codigo=%s", params)
                        codigos_modificados += 1
                        # Clasificar tipo de modificación para log distinguido
                        if "precio_unitario" in updates:
                            precios_modificados += 1
                        if "stock" in updates:
                            try:
                                old_s = float(existing.get("stock") or 0)
                                new_s = float(updates["stock"])
                                if new_s > old_s:
                                    stock_altas += 1
                                elif new_s < old_s:
                                    stock_bajas += 1
                            except Exception:
                                otros_mod += 1
                        if "stock_minimo" in updates:
                            stock_min_mod += 1
                        if "ubicacion" in updates:
                            ubic_mod += 1
                        # otros campos (descripcion, categoria, importancia) -> otros
                        if any(k in updates for k in ("descripcion", "categoria", "importancia")):
                            # contar solo si no fue solo precio/stock ya contado
                            if not any(k in updates for k in ("precio_unitario", "stock", "stock_minimo", "ubicacion")):
                                otros_mod += 1
                        reporte_lines.append(f"  ~ MOD {cod}: {', '.join(f'{k} {existing.get(k)}->{v}' for k,v in updates.items())}")
                        changed_codigos.add(cod)
                        # Collect audit rows per field for this modification
                        for _ak, _av in updates.items():
                            if len(pending_audits) < 5000:
                                _antes = existing.get(_ak)
                                _antes_s = None if _antes is None else str(_antes)
                                pending_audits.append((cod, _ak, _antes_s, str(_av)))

        # Resumen distinguido antes de propagación
        reporte_lines.append(
            f"  >> RESUMEN: {codigos_nuevos} nuevos | {codigos_modificados} mod "
            f"({precios_modificados} precios, {stock_altas} altas stock, {stock_bajas} bajas stock, {stock_min_mod} stock_min, {ubic_mod} ubic, {otros_mod} otros)"
        )
        # After processing rows, handle price propagation to salida_historial
        prop_total = 0
        for c, p in precios_map.items():
            cnt = _propagar_precio(conn, c, p)
            prop_total += cnt
            if cnt:
                reporte_lines.append(f"  $ PROP {c} @ {p:.2f} -> {cnt} movimientos mes curso")
        precios_propagados = len(precios_map)  # codes with price change, not rowcount
        if prop_total:
            reporte_lines.append(f"  >> PROPAGADOS: {precios_propagados} codigos con cambio precio -> {prop_total} movimientos actualizados mes curso")
        # Actually count propagation successes
        # We'll keep precios_propagados as count of codes propagated with >0 rows
        # For simplicity return len(precios_map)

        # Push Firestore solo-cambiados (best-effort, cap 500 para ahorrar escrituras)
        firestore_pushed = 0
        firestore_errors = 0
        if changed_codigos:
            try:
                _capped = sorted(changed_codigos)[:500]
                _fs_items: list[dict[str, Any]] = []
                with conn.cursor() as _fc:
                    for _cc in _capped:
                        try:
                            _fc.execute(
                                "SELECT codigo, descripcion, stock, ubicacion, categoria, alias FROM maestro_stock WHERE codigo=%s LIMIT 1",
                                (_cc,),
                            )
                            _fr = _fc.fetchone()
                        except Exception:
                            # Fallback sin alias si la columna aún no existe
                            try:
                                _fc.execute(
                                    "SELECT codigo, descripcion, stock, ubicacion, categoria FROM maestro_stock WHERE codigo=%s LIMIT 1",
                                    (_cc,),
                                )
                                _fr = _fc.fetchone()
                                if _fr is not None:
                                    _fr["alias"] = None
                            except Exception:
                                continue
                        if not _fr:
                            continue
                        _fs_items.append(
                            {
                                "codigo": str(_fr.get("codigo") or _cc).strip().upper(),
                                "desc": str(_fr.get("descripcion") or ""),
                                "stock": float(_fr.get("stock") or 0),
                                "ubicacion": str(_fr.get("ubicacion") or ""),
                                "categoria": str(_fr.get("categoria") or "GENERAL") or "GENERAL",
                                "alias": _fr.get("alias"),
                            }
                        )
                if _fs_items:
                    try:
                        import firebase_sync as _fb

                        _fs_res = _fb.sync_stock_bulk_to_firestore(_fs_items)
                        firestore_pushed = int(_fs_res.get("pushed") or 0)
                        firestore_errors = int(_fs_res.get("errors") or 0)
                        if _fs_res.get("error"):
                            reporte_lines.append(f"  >> FIRESTORE: {firestore_pushed} pusheados, {firestore_errors} errores ({len(_fs_items)} cambiados) — {_fs_res.get('error')}")
                        else:
                            reporte_lines.append(f"  >> FIRESTORE: {firestore_pushed} artículos sincronizados al buscador ({len(_fs_items)} cambiados)")
                    except Exception as _fe:
                        log.warning("Firestore bulk push failed for %s: %s", filename, _fe)
                        reporte_lines.append(f"  >> FIRESTORE: omitido ({len(_fs_items)} cambiados) — {str(_fe)[:120]}")
                        firestore_errors = len(_fs_items)
                if len(changed_codigos) > 500:
                    reporte_lines.append(f"  >> FIRESTORE: cap 500 de {len(changed_codigos)} cambiados (resto en próximo import)")
            except Exception as _fe2:
                log.warning("Firestore changed-codes collect failed for %s: %s", filename, _fe2)

        # Compute sin_precio global excluding K/U (artículos sin precio por diseño)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM maestro_stock WHERE (precio_unitario IS NULL OR precio_unitario <= 0) AND codigo NOT LIKE 'K%' AND codigo NOT LIKE 'U%'"
            )
            row = cur.fetchone()
            sin_precio = int(row["cnt"]) if row else 0
            # For debugging, also compute total inc K/U for log
            try:
                cur.execute("SELECT COUNT(*) AS cnt FROM maestro_stock WHERE LEFT(codigo,1) IN ('K','U')")
                _ku = cur.fetchone()
                if _ku:
                    reporte_lines.append(f"  >> NOTA: {int(_ku['cnt'])} códigos K/U excluidos del cómputo sin precio (total sin precio con K/U sería {_ku['cnt'] + sin_precio})")
            except Exception:
                pass

        duracion_ms = int((time.time() - t0) * 1000)
        reporte = "\n".join(reporte_lines)
        # Truncate reporte if too long (TEXT limit ok but keep 64k)
        if len(reporte) > 60000:
            reporte = reporte[:60000] + "\n... truncated"

        # Insert log with enriched counters (best-effort, fallback if columns missing)
        import_log_id: int | None = None
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO maestro_stock_import_log
                      (archivo_origen, tipo_archivo, codigos_nuevos, codigos_modificados, codigos_sin_precio, duracion_ms, reporte,
                       precios_modificados, stock_altas, stock_bajas, stock_min_mod, ubic_mod, otros_mod, precios_propagados, propagated_rows)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (filename, tipo, codigos_nuevos, codigos_modificados, sin_precio, duracion_ms, reporte,
                     precios_modificados, stock_altas, stock_bajas, stock_min_mod, ubic_mod, otros_mod, precios_propagados, prop_total),
                )
                try:
                    import_log_id = int(cur.lastrowid) if cur.lastrowid else None
                except Exception:
                    import_log_id = None
        except Exception as _e:
            # Fallback if enriched columns don't exist (older DB): insert base columns
            log.warning("Enriched import_log insert failed, fallback to base: %s", _e)
            try:
                conn.rollback()
            except Exception:
                pass
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO maestro_stock_import_log
                      (archivo_origen, tipo_archivo, codigos_nuevos, codigos_modificados, codigos_sin_precio, duracion_ms, reporte)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (filename, tipo, codigos_nuevos, codigos_modificados, sin_precio, duracion_ms, reporte),
                )
                try:
                    import_log_id = int(cur.lastrowid) if cur.lastrowid else None
                except Exception:
                    import_log_id = None
        # Insert audit rows if we have an import_log_id
        if import_log_id is not None and pending_audits:
            try:
                with conn.cursor() as cur:
                    # Cap already enforced at 5000, insert in chunks
                    for i in range(0, len(pending_audits), 500):
                        chunk = pending_audits[i:i+500]
                        cur.executemany(
                            """
                            INSERT INTO maestro_stock_audit
                              (codigo, campo, valor_antes, valor_despues, archivo_origen, tipo_archivo, import_log_id)
                            VALUES (%s,%s,%s,%s,%s,%s,%s)
                            """,
                            [(c, k, a, d, filename, tipo, import_log_id) for (c, k, a, d) in chunk],
                        )
                    if len(pending_audits) >= 5000:
                        log.warning("Audit capped at 5000 rows for %s (import_log_id=%s)", filename, import_log_id)
            except Exception as _ae:
                log.warning("Failed to insert audit rows for %s: %s", filename, _ae)
                # Do not rollback entire import for audit failure; keep log and maestro updates
                pass
        conn.commit()
        return {
            "archivo": filename,
            "tipo": tipo,
            "codigos_nuevos": codigos_nuevos,
            "codigos_modificados": codigos_modificados,
            "codigos_sin_precio": sin_precio,
            "precios_modificados": precios_modificados,
            "stock_altas": stock_altas,
            "stock_bajas": stock_bajas,
            "stock_min_mod": stock_min_mod,
            "ubic_mod": ubic_mod,
            "otros_mod": otros_mod,
            "precios_propagados": precios_propagados,
            "propagated_rows": prop_total,
            "firestore_pushed": firestore_pushed,
            "firestore_errors": firestore_errors,
            "duracion_ms": duracion_ms,
            "reporte": reporte,
        }
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass

# ---------------------------------------------------------------------------
# Starlette handlers
# ---------------------------------------------------------------------------

async def post_import(request: Request) -> JSONResponse:
    # Optional auth: if token present, require escritura; else allow for demo
    tok = _token(request)
    if tok:
        payload = verificar_permiso(tok, "salidas:escritura")
        if not payload:
            return JSONResponse({"detail": "Sin permiso de escritura en salidas."}, status_code=403)

    # Parse multipart
    try:
        form = await request.form()
    except Exception as e:
        return JSONResponse({"detail": f"Error parsing multipart: {e}"}, status_code=400)

    files: list[Any] = []
    # Starlette FormData: getlist for 'files'
    if hasattr(form, "getlist"):
        files = form.getlist("files")  # type: ignore
        if not files:
            # Fallback single 'file' or 'archivo'
            for key in ("file", "archivo", "archivo_origen"):
                v = form.get(key)
                if v:
                    files = [v]
                    break
    else:
        # Manual fallback
        for k, v in form.items():
            if hasattr(v, "filename"):
                files.append(v)

    # Also check if files is still empty but form has UploadFile entries
    if not files:
        for v in form.values():  # type: ignore
            if hasattr(v, "filename") and getattr(v, "filename"):
                files.append(v)

    if not files:
        return JSONResponse({"detail": "No files provided. Use multipart field 'files' with 1..N .xlsx"}, status_code=400)

    # Validate .xlsx and read bytes
    file_payloads: list[tuple[str, bytes]] = []
    for f in files:
        fname = getattr(f, "filename", "") or "unknown.xlsx"
        if not fname.lower().endswith(".xlsx"):
            return JSONResponse({"detail": f"File {fname} must be .xlsx"}, status_code=400)
        try:
            content = await f.read()  # type: ignore
        except Exception as e:
            return JSONResponse({"detail": f"Error reading {fname}: {e}"}, status_code=400)
        if not content or len(content) < 100:
            return JSONResponse({"detail": f"File {fname} empty or too small"}, status_code=400)
        file_payloads.append((fname, content))

    if len(file_payloads) > 20:
        return JSONResponse({"detail": "Too many files (max 20)"}, status_code=400)

    # Process each file in threadpool sequentially (transaction per file)
    results: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        for fname, content in file_payloads:
            res = await run_in_threadpool(_process_single_file, fname, content)
            results.append(res)
    except ValueError as e:
        return JSONResponse({"detail": str(e)}, status_code=400)
    except Exception as e:
        log.exception("Import failed")
        return JSONResponse({"detail": f"Import failed: {e}"}, status_code=500)

    # Aggregate summary
    total_nuevos = sum(r["codigos_nuevos"] for r in results)
    total_mod = sum(r["codigos_modificados"] for r in results)
    total_sin_precio = results[-1]["codigos_sin_precio"] if results else 0
    total_propagados = sum(r.get("precios_propagados", 0) for r in results)
    total_firestore = sum(r.get("firestore_pushed", 0) for r in results)
    total_firestore_err = sum(r.get("firestore_errors", 0) for r in results)

    return JSONResponse(
        {
            "archivos": len(results),
            "codigos_nuevos": total_nuevos,
            "codigos_modificados": total_mod,
            "codigos_sin_precio": total_sin_precio,
            "precios_propagados": total_propagados,
            "firestore_pushed": total_firestore,
            "firestore_errors": total_firestore_err,
            "detalle": results,
        },
        status_code=200,
    )

async def get_list(request: Request) -> JSONResponse:
    tok = _token(request)
    if tok and not verificar_permiso(tok, "salidas:lectura"):
        return JSONResponse({"detail": "Sin permiso de lectura en salidas."}, status_code=403)

    q = request.query_params
    try:
        page = max(1, int(q.get("page") or "1"))
    except ValueError:
        page = 1
    try:
        limit = int(q.get("limit") or "20")
        limit = max(1, min(100, limit))
    except ValueError:
        limit = 20
    offset = (page - 1) * limit

    filtro_q = (q.get("q") or "").strip()
    filtro_imp = (q.get("importancia") or "").strip().upper()
    filtro_cat = (q.get("categoria") or "").strip()
    filtro_ubic = (q.get("ubicacion") or "").strip()

    # Build WHERE with alias for F3 search - tokenized AND (mirrors Externas/AppPanolWeb filterArticulos)
    # Each word must be present in codigo/desc/alias/ubicacion (OR per field, AND per word)
    where_alias: list[str] = ["activo=1"]
    params_alias: list[Any] = []
    where_no_alias: list[str] = ["activo=1"]
    params_no_alias: list[Any] = []
    if filtro_q:
        words = [w for w in re.split(r"\s+", filtro_q.strip()) if w]
        for w in words:
            # Use UPPER for case-insensitive match (collation is ci but explicit UPPER guarantees buscador parity)
            where_alias.append("(UPPER(codigo) LIKE %s OR UPPER(COALESCE(descripcion,'')) LIKE %s OR UPPER(COALESCE(alias,'')) LIKE %s OR UPPER(COALESCE(ubicacion,'')) LIKE %s)")
            params_alias.extend([f"%{w.upper()}%", f"%{w.upper()}%", f"%{w.upper()}%", f"%{w.upper()}%"])
            where_no_alias.append("(UPPER(codigo) LIKE %s OR UPPER(COALESCE(descripcion,'')) LIKE %s OR UPPER(COALESCE(ubicacion,'')) LIKE %s)")
            params_no_alias.extend([f"%{w.upper()}%", f"%{w.upper()}%", f"%{w.upper()}%"])
    for target_where, target_params in ((where_alias, params_alias), (where_no_alias, params_no_alias)):
        if filtro_imp and filtro_imp in ("CRITICO", "ALTA FRECUENCIA", "BASE"):
            target_where.append("importancia=%s")
            target_params.append(filtro_imp)
        if filtro_cat:
            target_where.append("categoria=%s")
            target_params.append(filtro_cat)
        if filtro_ubic:
            target_where.append("ubicacion LIKE %s")
            target_params.append(f"%{filtro_ubic}%")

    where_sql = " AND ".join(where_alias)
    where_sql_no_alias = " AND ".join(where_no_alias)

    def _work() -> dict[str, Any]:
        conn = get_connection()
        try:
            _ensure_tables(conn)
            with conn.cursor() as cur:
                # Try with alias first, fallback to no-alias if column missing
                try:
                    cur.execute(f"SELECT COUNT(*) AS cnt FROM maestro_stock WHERE {where_sql}", params_alias)
                    row = cur.fetchone()
                    total = int(row["cnt"]) if row else 0
                    cur.execute(
                        f"""
                        SELECT codigo, descripcion, alias, stock, stock_minimo, ubicacion, precio_unitario, importancia, categoria, activo, actualizado_en
                        FROM maestro_stock
                        WHERE {where_sql}
                        ORDER BY codigo
                        LIMIT %s OFFSET %s
                        """,
                        params_alias + [limit, offset],
                    )
                    items = cur.fetchall()
                except Exception as e:
                    if "unknown column" in str(e).lower() and "alias" in str(e).lower():
                        cur.execute(f"SELECT COUNT(*) AS cnt FROM maestro_stock WHERE {where_sql_no_alias}", params_no_alias)
                        row = cur.fetchone()
                        total = int(row["cnt"]) if row else 0
                        cur.execute(
                            f"""
                            SELECT codigo, descripcion, stock, stock_minimo, ubicacion, precio_unitario, importancia, categoria, activo, actualizado_en
                            FROM maestro_stock
                            WHERE {where_sql_no_alias}
                            ORDER BY codigo
                            LIMIT %s OFFSET %s
                            """,
                            params_no_alias + [limit, offset],
                        )
                        items = cur.fetchall()
                        for it in items:
                            it["alias"] = None
                    else:
                        raise
                # Normalize types
                for it in items:
                    for k in ("stock", "stock_minimo", "precio_unitario"):
                        if k in it and it[k] is not None:
                            try:
                                it[k] = float(it[k])
                            except Exception:
                                pass
                    if "actualizado_en" in it and it["actualizado_en"]:
                        try:
                            it["actualizado_en"] = it["actualizado_en"].isoformat()  # type: ignore
                        except Exception:
                            it["actualizado_en"] = str(it["actualizado_en"])
                    if "alias" not in it:
                        it["alias"] = None
                return {"total": total, "page": page, "limit": limit, "items": items}
        finally:
            try:
                conn.close()
            except Exception:
                pass

    try:
        data = await run_in_threadpool(_work)
    except Exception as e:
        log.exception("List maestro_stock failed")
        return JSONResponse({"detail": str(e)}, status_code=500)
    return JSONResponse(data)
def _parse_reporte_to_diff(reporte: str, archivo_origen: str, tipo_archivo: str, import_log_id: int, creado_en_str: str | None) -> list[dict[str, Any]]:
    """Fallback: parse reporte TEXT lines like '~ MOD COD: campo old->new, ...' into structured rows."""
    if not reporte:
        return []
    rows: list[dict[str, Any]] = []
    for line in reporte.splitlines():
        s = line.strip()
        if not s:
            continue
        # Match + NEW or ~ MOD
        m_new = re.match(r"^\+\s*NEW\s+(\S+)\s*\(.*?\):\s*(.*)$", s)
        if m_new:
            cod = m_new.group(1).strip()
            rest = m_new.group(2).strip()
            # rest is k=v, k=v ...
            for part in re.split(r",\s*", rest):
                part = part.strip()
                if not part or "=" not in part:
                    continue
                k, v = part.split("=", 1)
                k = k.strip()
                v = v.strip()
                if not k:
                    continue
                rows.append({
                    "codigo": cod,
                    "campo": k,
                    "valor_antes": None,
                    "valor_despues": v,
                    "archivo_origen": archivo_origen,
                    "tipo_archivo": tipo_archivo,
                    "import_log_id": import_log_id,
                    "creado_en": creado_en_str,
                })
            continue
        m_mod = re.match(r"^\~\s*MOD\s+(\S+):\s*(.*)$", s)
        if m_mod:
            cod = m_mod.group(1).strip()
            rest = m_mod.group(2).strip()
            # rest is "k old->new, k old->new" - split carefully
            for part in re.split(r",\s*", rest):
                part = part.strip()
                if not part:
                    continue
                # part like "stock_minimo 0.00->2.0" or "ubicacion 2009D->200846"
                # or "descripcion OLD -> NEW" but OLD/NEW may contain spaces; remaining heuristic:
                # find first space then split by "->"
                # For price/stock, it's "k val->val"
                # For descripcion, could be "descripcion OLD->NEW" with spaces inside -> take "descripcion " prefix then rest split
                # Use approach: first token is campo, remainder is "old->new"
                if "->" not in part:
                    continue
                # campo is first word
                first_space = part.find(" ")
                if first_space == -1:
                    continue
                k = part[:first_space].strip()
                arrow_vals = part[first_space:].strip()
                # arrow_vals is "old->new"
                if "->" not in arrow_vals:
                    continue
                old, new = arrow_vals.split("->", 1)
                rows.append({
                    "codigo": cod,
                    "campo": k,
                    "valor_antes": old.strip(),
                    "valor_despues": new.strip(),
                    "archivo_origen": archivo_origen,
                    "tipo_archivo": tipo_archivo,
                    "import_log_id": import_log_id,
                    "creado_en": creado_en_str,
                })
    return rows


async def get_import_log(request: Request) -> JSONResponse:
    tok = _token(request)
    if tok and not verificar_permiso(tok, "salidas:lectura"):
        return JSONResponse({"detail": "Sin permiso de lectura en salidas."}, status_code=403)

    def _work() -> dict[str, Any]:
        conn = get_connection()
        try:
            _ensure_tables(conn)
            # Try enriched columns, fallback to base if missing
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, archivo_origen, tipo_archivo, codigos_nuevos, codigos_modificados, codigos_sin_precio, duracion_ms, reporte, creado_en, "
                        "precios_modificados, stock_altas, stock_bajas, stock_min_mod, ubic_mod, otros_mod, precios_propagados, propagated_rows "
                        "FROM maestro_stock_import_log ORDER BY id DESC LIMIT 20"
                    )
                    rows = cur.fetchall()
            except Exception as e:
                if "unknown column" in str(e).lower():
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT id, archivo_origen, tipo_archivo, codigos_nuevos, codigos_modificados, codigos_sin_precio, duracion_ms, reporte, creado_en FROM maestro_stock_import_log ORDER BY id DESC LIMIT 20"
                        )
                        rows = cur.fetchall()
                        for r in rows:
                            r["precios_modificados"] = 0
                            r["stock_altas"] = 0
                            r["stock_bajas"] = 0
                            r["stock_min_mod"] = 0
                            r["ubic_mod"] = 0
                            r["otros_mod"] = 0
                            r["precios_propagados"] = 0
                            r["propagated_rows"] = 0
                else:
                    raise
            for r in rows:
                if r.get("creado_en"):
                    try:
                        r["creado_en"] = r["creado_en"].isoformat()  # type: ignore
                    except Exception:
                        r["creado_en"] = str(r["creado_en"])
                for k in ("precios_modificados", "stock_altas", "stock_bajas", "stock_min_mod", "ubic_mod", "otros_mod", "precios_propagados", "propagated_rows"):
                    if k not in r or r[k] is None:
                        r[k] = 0
                    else:
                        try:
                            r[k] = int(r[k])
                        except Exception:
                            pass
                # Truncate reporte for list view only
                if r.get("reporte") and len(str(r["reporte"])) > 2000:
                    r["reporte"] = str(r["reporte"])[:2000] + "... truncated"
            return {"items": rows}
        finally:
            try:
                conn.close()
            except Exception:
                pass

    try:
        data = await run_in_threadpool(_work)
    except Exception as e:
        log.exception("Import log failed")
        return JSONResponse({"detail": str(e)}, status_code=500)
    return JSONResponse(data)


async def get_import_log_by_id(request: Request) -> JSONResponse:
    tok = _token(request)
    if tok and not verificar_permiso(tok, "salidas:lectura"):
        return JSONResponse({"detail": "Sin permiso de lectura en salidas."}, status_code=403)

    log_id = request.path_params.get("id")
    if not log_id:
        return JSONResponse({"detail": "id requerido en path."}, status_code=400)

    def _work() -> dict[str, Any]:
        conn = get_connection()
        try:
            _ensure_tables(conn)
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, archivo_origen, tipo_archivo, codigos_nuevos, codigos_modificados, codigos_sin_precio, duracion_ms, reporte, creado_en, "
                        "precios_modificados, stock_altas, stock_bajas, stock_min_mod, ubic_mod, otros_mod, precios_propagados, propagated_rows "
                        "FROM maestro_stock_import_log WHERE id=%s",
                        (int(log_id),),
                    )
                    row = cur.fetchone()
            except Exception as e:
                if "unknown column" in str(e).lower():
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT id, archivo_origen, tipo_archivo, codigos_nuevos, codigos_modificados, codigos_sin_precio, duracion_ms, reporte, creado_en FROM maestro_stock_import_log WHERE id=%s",
                            (int(log_id),),
                        )
                        row = cur.fetchone()
                        if row:
                            for k in ("precios_modificados", "stock_altas", "stock_bajas", "stock_min_mod", "ubic_mod", "otros_mod", "precios_propagados", "propagated_rows"):
                                row[k] = 0
                else:
                    raise
            if not row:
                return {"detail": "Log no encontrado"}
            if row.get("creado_en"):
                try:
                    row["creado_en"] = row["creado_en"].isoformat()  # type: ignore
                except Exception:
                    row["creado_en"] = str(row["creado_en"])
            return row
        finally:
            try:
                conn.close()
            except Exception:
                pass

    try:
        data = await run_in_threadpool(_work)
    except Exception as e:
        log.exception("Import log by id failed")
        return JSONResponse({"detail": str(e)}, status_code=500)
    return JSONResponse(data)


async def get_import_diff(request: Request) -> JSONResponse:
    tok = _token(request)
    if tok and not verificar_permiso(tok, "salidas:lectura"):
        return JSONResponse({"detail": "Sin permiso de lectura en salidas."}, status_code=403)
    raw_id = request.path_params.get("id")
    if not raw_id:
        return JSONResponse({"detail": "id requerido en path."}, status_code=400)
    try:
        log_id = int(str(raw_id).strip())
    except Exception:
        return JSONResponse({"detail": "id debe ser entero."}, status_code=400)

    def _work() -> dict[str, Any]:
        conn = get_connection()
        try:
            _ensure_tables(conn)
            with conn.cursor() as cur:
                # Fetch log metadata for fallback
                cur.execute("SELECT id, archivo_origen, tipo_archivo, reporte, creado_en FROM maestro_stock_import_log WHERE id=%s", (log_id,))
                meta = cur.fetchone()
                if not meta:
                    return {"detail": "Log no encontrado"}
                creado_en_str: str | None = None
                if meta.get("creado_en"):
                    try:
                        creado_en_str = meta["creado_en"].isoformat()  # type: ignore
                    except Exception:
                        creado_en_str = str(meta["creado_en"])
                # Try audit table first
                try:
                    cur.execute(
                        "SELECT id, codigo, campo, valor_antes, valor_despues, archivo_origen, tipo_archivo, import_log_id, creado_en "
                        "FROM maestro_stock_audit WHERE import_log_id=%s ORDER BY id ASC LIMIT 5000",
                        (log_id,),
                    )
                    rows = cur.fetchall()
                    if rows:
                        for r in rows:
                            if r.get("creado_en"):
                                try:
                                    r["creado_en"] = r["creado_en"].isoformat()  # type: ignore
                                except Exception:
                                    r["creado_en"] = str(r["creado_en"])
                        return {"import_log_id": log_id, "archivo_origen": meta["archivo_origen"], "tipo_archivo": meta["tipo_archivo"], "creado_en": creado_en_str, "items": rows}
                except Exception as e:
                    # If table missing, fallback to parse
                    if "doesn't exist" not in str(e).lower() and "unknown" not in str(e).lower():
                        log.warning("Audit diff query failed for %s: %s", log_id, e)
                # Fallback parse reporte
                reporte = str(meta.get("reporte") or "")
                parsed = _parse_reporte_to_diff(reporte, str(meta.get("archivo_origen") or ""), str(meta.get("tipo_archivo") or "general"), log_id, creado_en_str)
                return {"import_log_id": log_id, "archivo_origen": meta["archivo_origen"], "tipo_archivo": meta["tipo_archivo"], "creado_en": creado_en_str, "items": parsed}
        finally:
            try:
                conn.close()
            except Exception:
                pass

    try:
        data = await run_in_threadpool(_work)
        if isinstance(data, dict) and "detail" in data and len(data) == 1:
            return JSONResponse(data, status_code=404)
    except Exception as e:
        log.exception("Import diff failed")
        return JSONResponse({"detail": str(e)}, status_code=500)
    return JSONResponse(data)


async def get_codigo_history(request: Request) -> JSONResponse:
    tok = _token(request)
    if tok and not verificar_permiso(tok, "salidas:lectura"):
        return JSONResponse({"detail": "Sin permiso de lectura en salidas."}, status_code=403)
    codigo = (request.path_params.get("codigo") or "").strip()
    if not codigo:
        return JSONResponse({"detail": "codigo requerido en path."}, status_code=400)
    codigo = _limpiar_codigo(codigo)
    if not codigo:
        return JSONResponse({"detail": "codigo inválido."}, status_code=400)
    q = request.query_params
    try:
        page = max(1, int(q.get("page") or "1"))
    except ValueError:
        page = 1
    try:
        limit = int(q.get("limit") or "20")
        limit = max(1, min(100, limit))
    except ValueError:
        limit = 20
    offset = (page - 1) * limit

    def _work() -> dict[str, Any]:
        conn = get_connection()
        try:
            _ensure_tables(conn)
            with conn.cursor() as cur:
                try:
                    cur.execute("SELECT COUNT(*) AS cnt FROM maestro_stock_audit WHERE codigo=%s", (codigo,))
                    row = cur.fetchone()
                    total = int(row["cnt"]) if row else 0
                    cur.execute(
                        "SELECT id, codigo, campo, valor_antes, valor_despues, archivo_origen, tipo_archivo, import_log_id, creado_en "
                        "FROM maestro_stock_audit WHERE codigo=%s ORDER BY creado_en DESC, id DESC LIMIT %s OFFSET %s",
                        (codigo, limit, offset),
                    )
                    items = cur.fetchall()
                    for r in items:
                        if r.get("creado_en"):
                            try:
                                r["creado_en"] = r["creado_en"].isoformat()  # type: ignore
                            except Exception:
                                r["creado_en"] = str(r["creado_en"])
                    return {"codigo": codigo, "total": total, "page": page, "limit": limit, "items": items}
                except Exception as e:
                    if "doesn't exist" in str(e).lower() or "unknown" in str(e).lower():
                        return {"codigo": codigo, "total": 0, "page": page, "limit": limit, "items": []}
                    raise
        finally:
            try:
                conn.close()
            except Exception:
                pass

    try:
        data = await run_in_threadpool(_work)
    except Exception as e:
        log.exception("Codigo history failed for %s", codigo)
        return JSONResponse({"detail": str(e)}, status_code=500)
    return JSONResponse(data)

async def get_stats(request: Request) -> JSONResponse:
    tok = _token(request)
    if tok and not verificar_permiso(tok, "salidas:lectura"):
        return JSONResponse({"detail": "Sin permiso de lectura en salidas."}, status_code=403)

    def _work() -> dict[str, Any]:
        conn = get_connection()
        try:
            _ensure_tables(conn)
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS cnt FROM maestro_stock WHERE activo=1")
                total = int((cur.fetchone() or {}).get("cnt", 0))
                cur.execute("SELECT COUNT(*) AS cnt FROM maestro_stock WHERE activo=1 AND (precio_unitario IS NULL OR precio_unitario <= 0) AND codigo NOT LIKE 'K%' AND codigo NOT LIKE 'U%'")
                sin_precio = int((cur.fetchone() or {}).get("cnt", 0))
                # Also compute total sin precio incl K/U for transparency
                try:
                    cur.execute("SELECT COUNT(*) AS cnt FROM maestro_stock WHERE activo=1 AND (precio_unitario IS NULL OR precio_unitario <= 0)")
                    sin_precio_total = int((cur.fetchone() or {}).get("cnt", 0))
                    cur.execute("SELECT COUNT(*) AS cnt FROM maestro_stock WHERE activo=1 AND LEFT(codigo,1) IN ('K','U')")
                    ku_total = int((cur.fetchone() or {}).get("cnt", 0))
                except Exception:
                    sin_precio_total = sin_precio
                    ku_total = 0
                cur.execute("SELECT COUNT(*) AS cnt FROM maestro_stock WHERE activo=1 AND stock <= stock_minimo")
                criticos = int((cur.fetchone() or {}).get("cnt", 0))
                # Also breakdown by importancia
                cur.execute("SELECT importancia, COUNT(*) AS cnt FROM maestro_stock WHERE activo=1 GROUP BY importancia")
                by_imp = {row["importancia"]: int(row["cnt"]) for row in cur.fetchall()}
                return {"total": total, "sin_precio": sin_precio, "sin_precio_total": sin_precio_total, "sin_precio_ku_excluidos": ku_total, "criticos": criticos, "por_importancia": by_imp}
        finally:
            try:
                conn.close()
            except Exception:
                pass

    try:
        data = await run_in_threadpool(_work)
    except Exception as e:
        log.exception("Stats failed")
        return JSONResponse({"detail": str(e)}, status_code=500)
    return JSONResponse(data)


# ---------------------------------------------------------------------------
# Alias: bidirectional sync DB <-> Firestore
# PUT /api/maestro-stock/{codigo}/alias  {alias: string|null, motivo?: string}
# POST /api/maestro-stock/sync-alias     batch push/pull
# ---------------------------------------------------------------------------

async def put_alias(request: Request) -> JSONResponse:
    tok = _token(request)
    # Require escritura; if no token but service in open mode, allow? Keep compat: if token present require escritura else allow
    if tok:
        payload = verificar_permiso(tok, "salidas:escritura")
        if not payload:
            return JSONResponse({"detail": "Sin permiso de escritura en salidas."}, status_code=403)
        realizado_por = str(payload.get("usuario") or payload.get("sub") or "SISTEMA")
    else:
        # No token: allow for local/demo but mark as SISTEMA
        realizado_por = "SISTEMA"
        # Optionally allow anonymous? Keep open for tests; can be tightened to 403 if anonymous not allowed
        # For now allow anonymous to not break existing demo without auth

    codigo = (request.path_params.get("codigo") or "").strip()
    if not codigo:
        return JSONResponse({"detail": "codigo requerido en path."}, status_code=400)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"detail": "JSON inválido."}, status_code=400)
    if not isinstance(body, dict):
        return JSONResponse({"detail": "JSON debe ser objeto con campo alias."}, status_code=400)
    if "alias" not in body:
        return JSONResponse({"detail": "Campo alias requerido (string o null para limpiar)."}, status_code=400)
    alias_raw = body.get("alias")
    # Normalize: None or empty -> clear
    alias_val: str | None
    if alias_raw is None:
        alias_val = None
    else:
        s = str(alias_raw).strip()
        if s == "":
            alias_val = None
        else:
            if len(s) > 300:
                return JSONResponse({"detail": "alias max 300 caracteres."}, status_code=400)
            alias_val = s

    def _work() -> dict[str, Any]:
        # Import here to avoid circular
        try:
            from store_sql import maestro_update_alias
        except Exception as e:
            raise RuntimeError(f"No se pudo cargar maestro_update_alias: {e}") from e
        row = maestro_update_alias(codigo, alias_val, realizado_por=realizado_por)
        # Firestore sync (bidirectional): push alias to Firestore articulos doc
        try:
            import firebase_sync as _fb
            # Always attempt to push to Firestore if possible; respetar credenciales; FIREBASE_WRITE_ENABLED may be 0 but alias push should still work?
            # Use escribir_alias which handles FIREBASE_WRITE_ENABLED + cache internally
            _fb.escribir_alias(codigo, alias_val)
        except Exception as e:
            log.warning("Firestore alias sync push failed for %s: %s", codigo, e)
        return row

    try:
        data = await run_in_threadpool(_work)
    except ValueError as e:
        return JSONResponse({"detail": str(e)}, status_code=400)
    except RuntimeError as e:
        return JSONResponse({"detail": str(e)}, status_code=500)
    except Exception as e:
        log.exception("put_alias failed for %s", codigo)
        return JSONResponse({"detail": str(e)}, status_code=500)
    return JSONResponse(data)


async def post_sync_alias(request: Request) -> JSONResponse:
    tok = _token(request)
    if tok and not verificar_permiso(tok, "salidas:escritura"):
        return JSONResponse({"detail": "Sin permiso de escritura en salidas."}, status_code=403)
    # Optional query params: direction=push|pull|both (default both), limit
    q = request.query_params
    direction = (q.get("direction") or q.get("dir") or "both").strip().lower()
    if direction not in ("push", "pull", "both", "bidirectional"):
        direction = "both"
    try:
        limit = int(q.get("limit") or "1000")
        limit = max(1, min(5000, limit))
    except ValueError:
        limit = 1000

    def _work() -> dict[str, Any]:
        result: dict[str, Any] = {"direction": direction, "push": None, "pull": None}
        try:
            import firebase_sync as _fb
            if direction in ("push", "both", "bidirectional"):
                try:
                    pushed = _fb.sync_alias_db_to_firestore(limit=limit)
                    result["push"] = pushed
                except Exception as e:
                    result["push"] = {"error": str(e)}
            if direction in ("pull", "both", "bidirectional"):
                try:
                    pulled = _fb.pull_alias_desde_firestore(limit=limit)
                    result["pull"] = pulled
                except Exception as e:
                    result["pull"] = {"error": str(e)}
        except Exception as e:
            raise RuntimeError(f"sync alias failed: {e}") from e
        return result

    try:
        data = await run_in_threadpool(_work)
    except RuntimeError as e:
        return JSONResponse({"detail": str(e)}, status_code=500)
    except Exception as e:
        log.exception("post_sync_alias failed")
        return JSONResponse({"detail": str(e)}, status_code=500)
    return JSONResponse(data)
