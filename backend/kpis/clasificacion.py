# -*- coding: utf-8 -*-
"""
Clasificación de sector, línea y criticidad — portado de almacen_gui.py.
Sin listas hardcodeadas de operarios: todo desde hoja config de master_codes.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

import pandas as pd

CRITICIDAD_OPCIONES = ("CRÍTICO", "ALTA FRECUENCIA", "BASE")

SECTORES_DEFAULT = (
    "MANTENIMIENTO",
    "PROYECTOS",
    "EDILICIO",
    "AUTOELEVADORES",
    "PRODUCCION",
)


def norm_header(val: object) -> str:
    s = str(val or "").strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip()


def normalizar_operario(txt: object) -> str:
    return str(txt or "").strip().lower()


def resolver_sector_texto(txt: object) -> str:
    """Equivalente a _resolver_sector_texto (sin side effects)."""
    n = norm_header(txt)
    if not n:
        return ""
    if n.startswith("prod"):
        return "produccion"
    if n.startswith("proy"):
        return "proyectos"
    if n.startswith("mant"):
        return "mantenimiento"
    if n.startswith("edil"):
        return "edilicio"
    if n.startswith("auto"):
        return "autoelevadores"
    return n.replace(" ", "_")


def cargar_mapa_sectores(config_df: pd.DataFrame) -> tuple[list[str], dict[str, list[str]]]:
    """
    Lee hoja config: columna sector + operario/operarios.
    Devuelve lista de sectores oficiales y mapa sector_key -> [operarios].
    """
    if config_df is None or config_df.empty:
        return list(SECTORES_DEFAULT), {}

    cols = {norm_header(c).replace(" ", "_"): c for c in config_df.columns}
    col_sector = cols.get("sector")
    col_operario = cols.get("operario") or cols.get("operarios")

    sectores_set: set[str] = set()
    tmp_map: dict[str, list[str]] = {}

    if col_sector:
        for raw in config_df[col_sector].dropna().astype(str):
            s = str(raw).strip().upper()
            if s:
                sectores_set.add(s)

    if col_sector and col_operario:
        for _, row in config_df.iterrows():
            s_raw = str(row.get(col_sector, "")).strip()
            o_raw = str(row.get(col_operario, "")).strip()
            if not s_raw:
                continue
            s_key = resolver_sector_texto(s_raw) or s_raw.lower()
            sec_upper = s_raw.upper()
            sectores_set.add(sec_upper)
            if s_key not in tmp_map:
                tmp_map[s_key] = []
            if o_raw and o_raw.lower() not in ("nan", "none"):
                if o_raw not in tmp_map[s_key]:
                    tmp_map[s_key].append(o_raw)

    sectores = sorted(sectores_set) if sectores_set else list(SECTORES_DEFAULT)
    return sectores, tmp_map


def clasificar_sector(
    operario: object,
    sector_operarios_map: dict[str, list[str]],
    sectores_oficiales: list[str],
) -> str:
    """
    Clasifica OPERARIO → código de sector (MANTENIMIENTO, PROYECTOS, etc.).
    Siempre recalcula; no usa columna SECTOR del Excel de salidas.
    """
    t = normalizar_operario(operario)
    if not t or t in ("nan", "none"):
        return "MANTENIMIENTO"

    oficiales_upper = {s.upper() for s in sectores_oficiales}

    # El operario es el nombre del sector (ej. "produccion" en columna OPERARIO)
    for sec in sectores_oficiales:
        if t == normalizar_operario(sec):
            return sec.upper()

    resolved = resolver_sector_texto(t)
    alias_sector = {
        "produccion": "PRODUCCION",
        "proyectos": "PROYECTOS",
        "mantenimiento": "MANTENIMIENTO",
        "edilicio": "EDILICIO",
        "autoelevadores": "AUTOELEVADORES",
    }
    if resolved in alias_sector and alias_sector[resolved] in oficiales_upper:
        return alias_sector[resolved]

    # Mapa sector → operarios desde config
    for sec_key, ops in sector_operarios_map.items():
        sec_candidates = {sec_key.upper(), resolver_sector_texto(sec_key).upper()}
        for cand in sec_candidates:
            if cand in oficiales_upper:
                sec_code = cand
                break
        else:
            sec_code = sec_key.upper()
        if t == normalizar_operario(sec_key):
            return sec_code if sec_code in oficiales_upper else sec_code
        for op in ops:
            if t == normalizar_operario(op):
                return sec_code if sec_code in oficiales_upper else sec_code

    return "MANTENIMIENTO"


def normalizar_criticidad(val: object) -> str:
    v = str(val or "").strip().upper().replace("_", " ")
    if not v or v in ("NAN", "NONE"):
        return "BASE"
    if "CRIT" in v:
        return "CRÍTICO"
    if "ALTA" in v and ("FREQ" in v.replace(" ", "") or "FRECUENCIA" in v):
        return "ALTA FRECUENCIA"
    if v in CRITICIDAD_OPCIONES:
        return v
    return "BASE"


def normalizar_linea_gasto(val: object) -> str:
    """Port de _normalizar_linea_gasto — usa TIPO_COMPROBANTE."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "OTROS"
    s = str(val).strip().upper()
    if not s:
        return "OTROS"
    if s in ("PAÑ", "PAÑOL", "PANOL"):
        return "PAÑOL"
    for ln in ("L1", "L2", "L3", "L4", "L5", "L6", "L7"):
        if s == ln or s.startswith(ln + " "):
            return ln
    if s == "PROYECTOS":
        return "PROYECTOS"
    return s


def orden_lineas_gasto() -> list[str]:
    return ["PAÑOL"] + [f"L{i}" for i in range(1, 8)] + ["PROYECTOS", "OTROS"]
