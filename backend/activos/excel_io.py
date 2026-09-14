# -*- coding: utf-8 -*-
"""Lectura/escritura de salida_activos.xlsx con lock + .bak (patrón Solicitudes)."""

from __future__ import annotations

import os
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from config import SHEET_FUERA, SHEET_INGRESADOS, excel_path

_LOCK_TIMEOUT_S = 12.0
_LOCK_STALE_S = 60.0

# Orden canónico (interno). Excel usa encabezados con espacio.
COLUMNAS = [
    "NUMERO_PEDIDO",
    "NUMERO_OC",
    "NUMERO_REMITO",
    "SECTOR",
    "CODIGO",
    "EQUIPO_REPUESTO",
    "CANTIDAD",
    "NRO_SERIE",
    "FECHA_SALIDA",
    "PROVEEDOR",
    "FECHA_REGRESO",
    "ESTADO_AL_INGRESO",
    "OBSERVACIONES",
    "DIAS_FUERA",
    "ESTADO",
]

_HEADER_OUT = {
    "NUMERO_PEDIDO": "NUMERO PEDIDO",
    "NUMERO_OC": "NUMERO OC",
    "NUMERO_REMITO": "NUMERO REMITO",
    "SECTOR": "SECTOR",
    "CODIGO": "CODIGO",
    "EQUIPO_REPUESTO": "EQUIPO REPUESTO",
    "CANTIDAD": "CANTIDAD",
    "NRO_SERIE": "NRO SERIE",
    "FECHA_SALIDA": "FECHA SALIDA",
    "PROVEEDOR": "PROVEEDOR",
    "FECHA_REGRESO": "FECHA REGRESO",
    "ESTADO_AL_INGRESO": "ESTADO AL INGRESO",
    "OBSERVACIONES": "OBSERVACIONES",
    "DIAS_FUERA": "DIAS FUERA",
    "ESTADO": "ESTADO",
}


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
                        "El archivo de activos está ocupado. "
                        "Revisá: 1) cerrá salida_activos.xlsx en Excel; "
                        "2) que nadie más esté guardando desde el escritorio o otra PC; "
                        "3) esperá unos segundos y volvé a intentar."
                    )
                time.sleep(0.15)

    def __exit__(self, *_exc: object) -> None:
        try:
            if self._fd is not None:
                os.close(self._fd)
        finally:
            self.lock_path.unlink(missing_ok=True)


def _resolver_hoja(xls: pd.ExcelFile, nombre: str) -> str | None:
    target = nombre.strip().upper()
    for s in xls.sheet_names:
        if str(s).strip().upper() == target:
            return s
    return None


def _mapear_columnas(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    alias = {
        "NUMERO PEDIDO": "NUMERO_PEDIDO",
        "NUMERO OC": "NUMERO_OC",
        "NUMERO REMITO": "NUMERO_REMITO",
        "EQUIPO REPUESTO": "EQUIPO_REPUESTO",
        "NRO SERIE": "NRO_SERIE",
        "FECHA SALIDA": "FECHA_SALIDA",
        "FECHA REGRESO": "FECHA_REGRESO",
        "ESTADO AL INGRESO": "ESTADO_AL_INGRESO",
        "DIAS FUERA": "DIAS_FUERA",
    }
    ren: dict[str, str] = {}
    for c in df.columns:
        key = str(c).strip().upper()
        ren[c] = alias.get(key, key.replace(" ", "_"))
    return df.rename(columns=ren)


def parse_fecha(val: object) -> date | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    s = str(val).strip()
    if not s or s.lower() in ("nan", "nat", "none", "-", "0", "0.0"):
        return None
    # ISO yyyy-mm-dd
    try:
        if len(s) >= 10 and s[4] == "-":
            return date.fromisoformat(s[:10])
    except ValueError:
        pass
    ts = pd.to_datetime(s, errors="coerce", dayfirst=True)
    if pd.isna(ts):
        return None
    d = ts.date()
    return d if d.year >= 1990 else None


def fecha_str(d: date | None) -> str:
    if d is None:
        return ""
    return d.strftime("%d/%m/%Y")


def calcular_dias_fuera(fecha_salida: object, fecha_regreso: object | None = None) -> int:
    fs = parse_fecha(fecha_salida)
    if not fs:
        return 0
    fr = parse_fecha(fecha_regreso) if fecha_regreso is not None else None
    fin = fr if fr else date.today()
    return max(0, (fin - fs).days)


def fila_pendiente(row: pd.Series) -> bool:
    est = str(row.get("ESTADO", "")).strip().upper().replace(" ", "_")
    if est == "INGRESADO_A_PLANTA":
        return False
    if est == "FUERA_DE_PLANTA":
        return True
    return parse_fecha(row.get("FECHA_REGRESO")) is None


def _normalizar_hoja(df: pd.DataFrame) -> pd.DataFrame:
    df = _mapear_columnas(df.copy())
    for col in COLUMNAS:
        if col not in df.columns:
            df[col] = "" if col not in ("DIAS_FUERA", "CANTIDAD") else 0
    df = df[COLUMNAS].copy()
    if "DIAS_FUERA" in df.columns:
        df["DIAS_FUERA"] = pd.to_numeric(df["DIAS_FUERA"], errors="coerce").fillna(0).astype(int)
    return df.reset_index(drop=True)


def leer_ambas_hojas(path: Path | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    path = path or excel_path()
    if not path.is_file():
        raise FileNotFoundError(f"No se encontró {path}")
    xls = pd.ExcelFile(path, engine="openpyxl")
    try:
        hoja_f = _resolver_hoja(xls, SHEET_FUERA) or xls.sheet_names[0]
        df_fuera = _normalizar_hoja(pd.read_excel(xls, sheet_name=hoja_f))
        hoja_i = _resolver_hoja(xls, SHEET_INGRESADOS)
        if hoja_i:
            df_ing = _normalizar_hoja(pd.read_excel(xls, sheet_name=hoja_i))
        else:
            df_ing = _normalizar_hoja(pd.DataFrame(columns=COLUMNAS))
    finally:
        xls.close()
    return df_fuera, df_ing


def _texto_celda(val: object, vacio: str = "") -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return vacio
    s = str(val).strip()
    if not s or s.lower() in ("nan", "nat", "none", "<na>"):
        return vacio
    return s


def _cantidad(val: object) -> int:
    try:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return 1
        s = str(val).strip().replace(",", ".")
        if not s or s.lower() in ("nan", "-"):
            return 1
        return max(1, int(float(s)))
    except (TypeError, ValueError):
        return 1


def _color_dias(dias: object) -> str:
    try:
        d = int(float(dias))
    except (TypeError, ValueError):
        d = 0
    if d > 30:
        return "#FFC7CE"
    if d > 21:
        return "#FFEB9C"
    return "#C6EFCE"


def _preparar_df_escritura(df: pd.DataFrame, *, ordenar_por_dias: bool) -> pd.DataFrame:
    out = df.copy() if df is not None else pd.DataFrame(columns=COLUMNAS)
    for col in COLUMNAS:
        if col not in out.columns:
            out[col] = "" if col not in ("DIAS_FUERA", "CANTIDAD") else 0
    out = out[COLUMNAS].copy()
    # Mayúsculas en texto (igual que escritorio)
    for col in out.columns:
        if col in ("DIAS_FUERA", "CANTIDAD"):
            continue
        if col in ("FECHA_SALIDA", "FECHA_REGRESO"):
            continue
        out[col] = out[col].map(
            lambda v: _texto_celda(v).upper() if _texto_celda(v) else ""
        )
    if ordenar_por_dias and not out.empty:
        out["__orden"] = pd.to_numeric(out["DIAS_FUERA"], errors="coerce").fillna(0)
        out = out.sort_values("__orden", ascending=False).drop(columns=["__orden"]).reset_index(drop=True)
    return out


def _escribir_hoja_formateada(
    ws: Any,
    wb: Any,
    df: pd.DataFrame,
    *,
    ordenar_por_dias: bool,
    colorear_por_dias: bool,
) -> None:
    """Formato alineado a almacen_gui._escribir_hoja_excel_formateada (xlsxwriter)."""
    df_excel = _preparar_df_escritura(df, ordenar_por_dias=ordenar_por_dias)

    header_fmt = wb.add_format(
        {"bold": True, "bg_color": "#1F4E78", "font_color": "white", "border": 1, "align": "center"}
    )
    base_fmt = wb.add_format({"border": 1})
    date_fmt = wb.add_format({"num_format": "dd/mm/yyyy", "border": 1, "align": "center"})
    dias_fmt = wb.add_format({"border": 1, "bold": True, "font_color": "#C00000", "align": "center"})
    fmt_cache: dict[tuple[str, str | None], Any] = {}

    def _fmt(role: str, bg: str | None):
        key = (role, bg)
        if key not in fmt_cache:
            spec: dict[str, Any] = {"border": 1}
            if role == "date":
                spec["num_format"] = "dd/mm/yyyy"
                spec["align"] = "center"
            elif role == "dias":
                spec["bold"] = True
                spec["align"] = "center"
            if bg:
                spec["bg_color"] = bg
            fmt_cache[key] = wb.add_format(spec)
        return fmt_cache[key]

    if df_excel.empty:
        for col_num, col_name in enumerate(COLUMNAS):
            ws.write(0, col_num, _HEADER_OUT[col_name], header_fmt)
            ws.set_column(col_num, col_num, 14, base_fmt)
        return

    bg_filas: list[str | None]
    if colorear_por_dias:
        bg_filas = [_color_dias(df_excel["DIAS_FUERA"].iloc[r]) for r in range(len(df_excel))]
    else:
        bg_filas = [None] * len(df_excel)

    for col_num, col_name in enumerate(COLUMNAS):
        titulo = _HEADER_OUT[col_name]
        ws.write(0, col_num, titulo, header_fmt)
        max_len = len(titulo)
        for r in range(len(df_excel)):
            val = df_excel.iloc[r][col_name]
            txt = _texto_celda(val)
            if col_name in ("NUMERO_PEDIDO", "NUMERO_OC", "NUMERO_REMITO", "CODIGO"):
                txt = norm_doc(val)
            bg = bg_filas[r]
            f_base = _fmt("base", bg) if bg else base_fmt
            f_date = _fmt("date", bg) if bg else date_fmt
            f_dias = _fmt("dias", bg) if bg else dias_fmt

            if col_name == "DIAS_FUERA":
                try:
                    ws.write_number(r + 1, col_num, int(float(txt)) if txt else 0, f_dias)
                except ValueError:
                    ws.write(r + 1, col_num, txt, f_base)
            elif col_name == "CANTIDAD":
                ws.write_number(r + 1, col_num, _cantidad(val), f_base)
            elif col_name in ("FECHA_SALIDA", "FECHA_REGRESO"):
                d = parse_fecha(val)
                if d:
                    ws.write_datetime(r + 1, col_num, datetime(d.year, d.month, d.day), f_date)
                else:
                    ws.write(r + 1, col_num, "", f_base)
            else:
                ws.write(r + 1, col_num, txt, f_base)
            max_len = max(max_len, len(str(txt)))
        ws.set_column(col_num, col_num, min(max(12, int(max_len) + 2), 42), base_fmt)

    ws.autofilter(0, 0, len(df_excel), len(COLUMNAS) - 1)
    ws.freeze_panes(1, 0)


def escribir_ambas_hojas(df_fuera: pd.DataFrame, df_ing: pd.DataFrame, path: Path | None = None) -> None:
    """Guarda ambas hojas con el mismo formato visual que el escritorio (xlsxwriter)."""
    path = path or excel_path()
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with pd.ExcelWriter(tmp, engine="xlsxwriter") as writer:
            wb = writer.book
            # Crear hojas vacías y volcar con formato (como almacen_gui)
            for nombre, df_h, ordenar, colorear in (
                (SHEET_FUERA, df_fuera, True, True),
                (SHEET_INGRESADOS, df_ing, False, False),
            ):
                pd.DataFrame(columns=COLUMNAS).to_excel(writer, sheet_name=nombre, index=False)
                _escribir_hoja_formateada(
                    writer.sheets[nombre],
                    wb,
                    df_h if df_h is not None else pd.DataFrame(columns=COLUMNAS),
                    ordenar_por_dias=ordenar,
                    colorear_por_dias=colorear,
                )
    except PermissionError as e:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise PermissionError(
            "No se pudo guardar: el Excel está abierto o bloqueado. "
            "Revisá: cerrá salida_activos.xlsx en Excel (y ventanas de vista previa), "
            "confirmá que Drive no esté sincronizando el archivo, y volvé a intentar."
        ) from e

    if path.is_file():
        try:
            bak = path.with_suffix(path.suffix + ".bak")
            os.replace(path, bak)
        except OSError:
            pass
    try:
        os.replace(tmp, path)
    except PermissionError as e:
        raise PermissionError(
            "No se pudo guardar: el Excel está abierto o bloqueado. "
            "Revisá: cerrá salida_activos.xlsx en Excel (y ventanas de vista previa), "
            "confirmá que Drive no esté sincronizando el archivo, y volvé a intentar."
        ) from e


def reescribir_formateado(path: Path | None = None) -> dict[str, Any]:
    """Lee el Excel actual y lo vuelve a guardar con formato (sin cambiar datos de negocio)."""
    path = path or excel_path()
    with FileLock(path):
        df_fuera, df_ing = leer_ambas_hojas(path)
        escribir_ambas_hojas(df_fuera, df_ing, path)
    return {
        "mensaje": "Excel reescrito con formato de seguimiento.",
        "fuera": int(len(df_fuera)),
        "ingresados": int(len(df_ing)),
    }


def norm_doc(val: object) -> str:
    s = str(val or "").strip()
    if s.endswith(".0") and s[:-2].isdigit():
        return s[:-2]
    return s if s and s.lower() not in ("nan", "none") else ""


def norm_text(val: object) -> str:
    s = str(val or "").strip()
    return "" if s.lower() in ("nan", "none", "nat") else s


def fingerprint_row(row: pd.Series) -> str:
    parts = [
        norm_doc(row.get("CODIGO", "")),
        norm_doc(row.get("NUMERO_REMITO", "")),
        norm_doc(row.get("NUMERO_PEDIDO", "")),
        norm_doc(row.get("NUMERO_OC", "")),
        norm_text(row.get("NRO_SERIE", "")),
        fecha_str(parse_fecha(row.get("FECHA_SALIDA"))),
        norm_text(row.get("EQUIPO_REPUESTO", "")),
    ]
    return "|".join(parts)
