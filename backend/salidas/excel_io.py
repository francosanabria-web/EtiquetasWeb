# -*- coding: utf-8 -*-
"""IO Excel para maestro + historial de salidas (capa reemplazable por SQL)."""

from __future__ import annotations

import os
import shutil
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from config import (
    COLUMNAS_MOVIMIENTO,
    HOJA_ARTICULOS,
    HOJA_CONFIG,
    HOJA_MOVIMIENTOS,
    MES_NOMBRES,
    OPERARIOS_DEFAULT,
    OPERARIOS_PROYECTOS_DEFAULT,
    SECTORES_DEFAULT,
    TIPOS_COMPROBANTE_DEFAULT,
    data_path,
    diario_path,
    historial_path,
    maestro_path,
    maestro_writable,
)

# Estética alineada a diarios de escritorio (salidas_DD-MM-AAAA.xlsx de planta).
_HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
_HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
_THIN = Border(
    left=Side(style="thin", color="BFBFBF"),
    right=Side(style="thin", color="BFBFBF"),
    top=Side(style="thin", color="BFBFBF"),
    bottom=Side(style="thin", color="BFBFBF"),
)
_ANCHOS_MOV = {
    "FECHA": 12.7,
    "MES": 12.0,
    "AÑO": 8.0,
    "CODIGO": 14.0,
    "DESCRIPCION": 45.7,
    "UBICACION": 12.7,
    "CANTIDAD": 12.0,
    "TIPO_COMPROBANTE": 18.7,
    "NUMERO_ORDEN": 14.7,
    "MAQUINA_SITIO": 27.7,
    "PRECIO_UNITARIO": 17.7,
    "MONTO_TOTAL_SALIDA": 20.7,
    "OPERARIO": 18.7,
    "SECTOR": 16.7,
}
_MONEY_COLS = frozenset({"PRECIO_UNITARIO", "MONTO_TOTAL_SALIDA"})
_INT_COLS = frozenset({"AÑO", "NUMERO_ORDEN"})

_LOCK_TIMEOUT_S = 12.0
_LOCK_STALE_S = 60.0


class FileLock:
    def __init__(self, target: Path) -> None:
        self.lock_path = target.with_suffix(target.suffix + ".lock")
        self._fd: int | None = None

    def __enter__(self) -> "FileLock":
        inicio = time.time()
        while True:
            try:
                self._fd = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
                os.write(self._fd, str(os.getpid()).encode("ascii", "ignore"))
                return self
            except FileExistsError:
                try:
                    edad = time.time() - self.lock_path.stat().st_mtime
                    if edad > _LOCK_STALE_S:
                        self.lock_path.unlink(missing_ok=True)
                        continue
                except OSError:
                    pass
                if time.time() - inicio > _LOCK_TIMEOUT_S:
                    raise TimeoutError(
                        f"Archivo ocupado: {self.lock_path.name}. "
                        "Cerrá el Excel si está abierto e intentá de nuevo."
                    )
                time.sleep(0.15)

    def __exit__(self, *_) -> None:
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None
        try:
            self.lock_path.unlink(missing_ok=True)
        except OSError:
            pass


def _norm_header(c: Any) -> str:
    return str(c or "").strip().lower().replace(" ", "_").replace(".", "")


def fecha_sin_hora_str(fecha_val: Any) -> str:
    """Fecha escrita tipo 15/5/2026 (sin cero a la izquierda), como el escritorio."""
    if fecha_val is None:
        return ""
    try:
        if isinstance(fecha_val, pd.Timestamp):
            if pd.isna(fecha_val):
                return ""
            fecha_val = fecha_val.date()
        elif isinstance(fecha_val, datetime):
            fecha_val = fecha_val.date()
        if isinstance(fecha_val, date):
            return f"{fecha_val.day}/{fecha_val.month}/{fecha_val.year}"
        if isinstance(fecha_val, str):
            txt = fecha_val.strip()
            if not txt or txt.lower() in ("nan", "nat", "none"):
                return ""
            dt = pd.to_datetime(txt, dayfirst=True, errors="coerce")
            if pd.isna(dt):
                return txt
            return f"{dt.day}/{dt.month}/{dt.year}"
        if isinstance(fecha_val, (int, float)) and 20000 <= float(fecha_val) <= 120000:
            base = pd.Timestamp("1899-12-30")
            dt = base + pd.Timedelta(days=float(fecha_val))
            return f"{dt.day}/{dt.month}/{dt.year}"
    except Exception:
        pass
    return str(fecha_val).strip()


def parse_fecha(raw: str | date | datetime | None) -> date | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    txt = str(raw).strip()
    if not txt:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y"):
        try:
            return datetime.strptime(txt, fmt).date()
        except ValueError:
            continue
    dt = pd.to_datetime(txt, dayfirst=True, errors="coerce")
    if pd.isna(dt):
        return None
    return dt.date()


def nombre_mes(mes: int) -> str:
    return MES_NOMBRES.get(int(mes), "")


def normalizar_orden(val: Any) -> Any:
    s = str(val or "").strip()
    if not s:
        return ""
    s = s.replace(",", ".")
    try:
        f = float(s)
        if f == int(f):
            return int(f)
        return f
    except ValueError:
        return s


def col_stock(df: pd.DataFrame) -> str | None:
    for c in df.columns:
        n = _norm_header(c)
        if "stock" in n or n in ("act", "cant", "cantidad", "stkactual", "stockactual"):
            if "min" in n:
                continue
            return c
    return None


def col_precio(df: pd.DataFrame) -> str | None:
    for c in df.columns:
        n = _norm_header(c)
        if n in ("precio_unitario", "preciounitario", "costouni", "pu", "punit"):
            return c
        if "precio" in n:
            return c
    return None


def col_ubicacion(df: pd.DataFrame) -> str | None:
    for c in df.columns:
        n = _norm_header(c)
        if "ubic" in n:
            return c
    return None


def col_descripcion(df: pd.DataFrame) -> str | None:
    for c in df.columns:
        n = _norm_header(c)
        if n in ("descripcion", "descripción", "articulo", "artículo"):
            return c
    return None


def col_codigo(df: pd.DataFrame) -> str | None:
    for c in df.columns:
        if _norm_header(c) == "codigo":
            return c
    return None


def col_categoria(df: pd.DataFrame) -> str | None:
    for c in df.columns:
        n = _norm_header(c)
        if n in ("categoria", "categoría", "categoria_articulo"):
            return c
    return None


def asegurar_rutas_escritura() -> None:
    """Asegura carpeta de escritura + historial vacío.

    Nunca crea ni toca master_codes/master_salidas de producción del pañol.
    Solo genera un maestro DEMO si el destino del maestro es data_prueba y falta.
    """
    base = data_path()
    base.mkdir(parents=True, exist_ok=True)

    path = maestro_path()
    # Solo sembrar DEMO si el maestro faltante caería en data_prueba (modo local).
    if not path.is_file() and maestro_writable():
        path.parent.mkdir(parents=True, exist_ok=True)
        df_art = pd.DataFrame(
            [
                {
                    "codigo": "DEMO-001",
                    "descripcion": "TORNILLO HEX M8x20",
                    "ubicacion": "A-01",
                    "stock_actual": 100,
                    "precio_unitario": 15.5,
                    "categoria": "GENERAL",
                },
                {
                    "codigo": "DEMO-002",
                    "descripcion": "ARANDELA PLANA M8",
                    "ubicacion": "A-02",
                    "stock_actual": 250,
                    "precio_unitario": 2.0,
                    "categoria": "GENERAL",
                },
                {
                    "codigo": "DEMO-003",
                    "descripcion": "GRASA MULTIUSO 1KG",
                    "ubicacion": "B-10",
                    "stock_actual": 12,
                    "precio_unitario": 4500.0,
                    "categoria": "LUBRICANTES",
                },
            ]
        )
        n = max(
            7,
            len(TIPOS_COMPROBANTE_DEFAULT),
            len(OPERARIOS_DEFAULT),
        )
        sectores_cfg = [
            "MANTENIMIENTO",
            "MANTENIMIENTO",
            "EDILICIO",
            "PRODUCCION",
            "PROYECTOS",
            "PROYECTOS",
            "AUTOELEVADORES",
        ]
        operarios_cfg = ["AA", "AB", "AC", "AD", "MACCARONI", "VALENZUELA", "AE"]
        df_cfg = pd.DataFrame(
            {
                "sector": (sectores_cfg + [""] * n)[:n],
                "operario": (operarios_cfg + [""] * n)[:n],
                "comprobantes": (TIPOS_COMPROBANTE_DEFAULT + [""] * n)[:n],
                "operarios": (OPERARIOS_DEFAULT + [""] * n)[:n],
            }
        )
        with pd.ExcelWriter(path, engine="openpyxl") as w:
            df_art.to_excel(w, index=False, sheet_name=HOJA_ARTICULOS)
            df_cfg.to_excel(w, index=False, sheet_name=HOJA_CONFIG)

    hist = historial_path()
    if not hist.is_file():
        _escribir_excel_atomico(
            hist, pd.DataFrame(columns=COLUMNAS_MOVIMIENTO), HOJA_MOVIMIENTOS
        )


def asegurar_data_prueba() -> None:
    """Alias histórico — ahora asegura rutas de escritura (salidas_web o data_prueba)."""
    asegurar_rutas_escritura()


def leer_maestro() -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    """Devuelve (hojas_por_nombre, config_df)."""
    asegurar_data_prueba()
    path = maestro_path()
    if not path.is_file():
        raise FileNotFoundError(f"No se encontró maestro: {path}")
    xls = pd.ExcelFile(path, engine="openpyxl")
    hojas: dict[str, pd.DataFrame] = {}
    config_df = pd.DataFrame()
    for name in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=name)
        key = str(name).strip()
        if _norm_header(key) == "config":
            config_df = df
        else:
            # Normalizar columna codigo a minúsculas internas para búsqueda
            c_cod = col_codigo(df)
            if c_cod and c_cod != "codigo":
                df = df.rename(columns={c_cod: "codigo"})
            if "codigo" in df.columns:
                df["codigo"] = df["codigo"].astype(str).str.strip().str.upper()
            hojas[key] = df
    if HOJA_ARTICULOS not in hojas and hojas:
        # Primera hoja con codigo
        for k, df in hojas.items():
            if "codigo" in df.columns:
                hojas[HOJA_ARTICULOS] = df
                break
    return hojas, config_df


def guardar_maestro(hojas: dict[str, pd.DataFrame], config_df: pd.DataFrame) -> None:
    """Persiste stock en el maestro SOLO si es writable (nunca producción)."""
    if not maestro_writable():
        return
    path = maestro_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with FileLock(path):
        try:
            with pd.ExcelWriter(tmp, engine="openpyxl") as w:
                for name, df in hojas.items():
                    df.to_excel(w, index=False, sheet_name=name[:31] or "Hoja")
                if config_df is not None and not config_df.empty:
                    config_df.to_excel(w, index=False, sheet_name=HOJA_CONFIG)
            if path.is_file():
                bak = path.with_suffix(path.suffix + ".bak")
                try:
                    shutil.copy2(path, bak)
                except OSError:
                    pass
            os.replace(tmp, path)
        except Exception:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
            raise


def leer_movimientos(path: Path | None = None) -> pd.DataFrame:
    p = path or historial_path()
    if not p.is_file():
        return pd.DataFrame(columns=COLUMNAS_MOVIMIENTO)
    df = pd.read_excel(p, engine="openpyxl")
    if "FECHA" in df.columns:
        df["FECHA"] = df["FECHA"].apply(fecha_sin_hora_str)
    return df


def _coerce_celda(col: str, val: Any) -> Any:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, pd.Timestamp):
        return fecha_sin_hora_str(val)
    if col == "FECHA":
        return fecha_sin_hora_str(val)
    if col in _MONEY_COLS or col == "CANTIDAD":
        try:
            return float(val) if str(val).strip() != "" else 0.0
        except (TypeError, ValueError):
            return val
    if col in _INT_COLS:
        try:
            f = float(val)
            return int(f) if f == int(f) else f
        except (TypeError, ValueError):
            return val
    return val


def _workbook_movimientos(df: pd.DataFrame, sheet_name: str) -> Workbook:
    """Workbook con cabecera/anchos/formatos como el Excel diario del escritorio."""
    cols = [c for c in COLUMNAS_MOVIMIENTO if c in df.columns] + [
        c for c in df.columns if c not in COLUMNAS_MOVIMIENTO
    ]
    if not cols:
        cols = list(COLUMNAS_MOVIMIENTO)

    wb = Workbook()
    ws = wb.active
    ws.title = (sheet_name or HOJA_MOVIMIENTOS)[:31]

    for col_idx, col in enumerate(cols, start=1):
        cell = ws.cell(row=1, column=col_idx, value=col)
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = _THIN
        ws.column_dimensions[get_column_letter(col_idx)].width = _ANCHOS_MOV.get(col, 14.0)

    for row_idx, row in enumerate(df.itertuples(index=False), start=2):
        for col_idx, (col, raw) in enumerate(zip(cols, row), start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=_coerce_celda(col, raw))
            cell.border = _THIN
            if col in _MONEY_COLS:
                cell.number_format = "$ #,##0.00"
                cell.alignment = Alignment(horizontal="right", vertical="center")
            elif col in _INT_COLS:
                cell.number_format = "0"
            elif col == "CANTIDAD":
                cell.alignment = Alignment(horizontal="right", vertical="center")

    last_row = max(1, len(df) + 1)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(cols))}{last_row}"
    ws.row_dimensions[1].height = 18
    return wb


def _escribir_excel_atomico(path: Path, df: pd.DataFrame, sheet_name: str) -> None:
    """Escribe a .tmp y reemplaza — evita dejar el xlsx en 0 bytes si Drive/Excel interrumpe.

    Aplica formato profesional (cabecera azul, anchos, $ / enteros, freeze, filtro)
    alineado a los diarios de salidas del escritorio.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        wb = _workbook_movimientos(df, sheet_name)
        wb.save(tmp)
        if path.is_file():
            bak = path.with_suffix(path.suffix + ".bak")
            try:
                shutil.copy2(path, bak)
            except OSError:
                pass
        os.replace(tmp, path)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def append_movimientos(filas: list[dict[str, Any]], fechas: list[date]) -> list[str]:
    """Escribe en master_salidas + Excel diario por fecha. Devuelve paths tocados."""
    if not filas:
        return []
    asegurar_data_prueba()
    tocados: list[str] = []
    por_archivo: dict[Path, list[dict[str, Any]]] = {}
    hist = historial_path()
    por_archivo.setdefault(hist, []).extend(filas)
    for fila, f in zip(filas, fechas):
        por_archivo.setdefault(diario_path(f), []).append(fila)

    for path, batch in por_archivo.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        with FileLock(path):
            if path.is_file() and path.stat().st_size >= 64:
                try:
                    df_p = pd.read_excel(path, engine="openpyxl")
                except Exception as e:
                    raise RuntimeError(
                        f"No se pudo leer {path.name} (archivo corrupto o vacío). "
                        f"Restaurá desde .bak o diarios antes de registrar salidas. Detalle: {e}"
                    ) from e
            else:
                df_p = pd.DataFrame(columns=COLUMNAS_MOVIMIENTO)
            if "FECHA" in df_p.columns:
                df_p["FECHA"] = df_p["FECHA"].apply(fecha_sin_hora_str)
            df_p = pd.concat([df_p, pd.DataFrame(batch)], ignore_index=True)
            if "FECHA" in df_p.columns:
                df_p["FECHA"] = df_p["FECHA"].apply(fecha_sin_hora_str)
            # Orden de columnas preferido
            cols = [c for c in COLUMNAS_MOVIMIENTO if c in df_p.columns] + [
                c for c in df_p.columns if c not in COLUMNAS_MOVIMIENTO
            ]
            df_p = df_p[cols]
            _escribir_excel_atomico(path, df_p, HOJA_MOVIMIENTOS)
        tocados.append(str(path))
    return tocados


def catalogos_desde_config(config_df: pd.DataFrame) -> dict[str, Any]:
    """Lee hoja `config` de master_codes (comprobantes / sector / operario).

    Misma fuente que el escritorio: columnas `comprobantes`, `operarios`,
    y pares `sector`+`operario`. Solo lectura — no modifica el Excel.
    """
    tipos = list(TIPOS_COMPROBANTE_DEFAULT)
    sectores = list(SECTORES_DEFAULT)
    operarios = list(OPERARIOS_DEFAULT)
    operarios_proyectos = list(OPERARIOS_PROYECTOS_DEFAULT)
    sector_map: dict[str, list[str]] = {}

    if config_df is not None and not config_df.empty:
        cols = {_norm_header(c): c for c in config_df.columns}
        if "comprobantes" in cols:
            tipos = [
                str(x).strip().upper()
                for x in config_df[cols["comprobantes"]].dropna().tolist()
                if str(x).strip() and str(x).strip().lower() not in ("nan", "none")
            ] or tipos
        if "operarios" in cols:
            operarios = [
                str(x).strip().upper()
                for x in config_df[cols["operarios"]].dropna().tolist()
                if str(x).strip() and str(x).strip().lower() not in ("nan", "none")
            ] or operarios
        # Pares sector → operario (columna singular; no mezclar con lista `operarios`)
        col_sec = cols.get("sector")
        col_ope = cols.get("operario")
        if col_sec and col_ope:
            for _, row in config_df.iterrows():
                s = str(row.get(col_sec, "")).strip().upper()
                o = str(row.get(col_ope, "")).strip().upper()
                if not s or s in ("NAN", "NONE"):
                    continue
                sector_map.setdefault(s, [])
                if o and o not in ("NAN", "NONE") and o not in sector_map[s]:
                    sector_map[s].append(o)
            if sector_map:
                sectores = sorted(sector_map.keys())

    for s in SECTORES_DEFAULT:
        sector_map.setdefault(s, [])
    if "PROYECTOS" in sector_map and not sector_map["PROYECTOS"]:
        sector_map["PROYECTOS"] = list(operarios_proyectos)
    # Operarios de proyectos desde el mapa real si existen
    if sector_map.get("PROYECTOS"):
        operarios_proyectos = list(sector_map["PROYECTOS"])

    return {
        "tipos_comprobante": tipos,
        "sectores": sectores,
        "operarios": operarios,
        "operarios_proyectos": operarios_proyectos,
        "sector_operarios": sector_map,
    }
