# -*- coding: utf-8 -*-
"""Configuración SMTP — misma lógica que almacen_gui.py (Gmail :587 + starttls)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from contacts_reader import fila_smtp_excel


@dataclass(frozen=True)
class SmtpConfig:
    host: str
    port: int
    user: str
    password: str
    from_addr: str


class SmtpNoConfigurado(Exception):
    pass


def _desde_env() -> SmtpConfig | None:
    user = (os.environ.get("PANOL_SMTP_USER") or os.environ.get("PANOL_SMTP_FROM") or "").strip()
    password = (os.environ.get("PANOL_SMTP_PASSWORD") or "").strip()
    if not user or not password:
        return None
    from_addr = (os.environ.get("PANOL_SMTP_FROM") or user).strip()
    host = os.environ.get("PANOL_SMTP_HOST", "smtp.gmail.com").strip()
    port = int(os.environ.get("PANOL_SMTP_PORT", "587"))
    return SmtpConfig(host=host, port=port, user=user, password=password, from_addr=from_addr)


def _desde_excel_solo_lectura() -> SmtpConfig | None:
    try:
        creds = fila_smtp_excel()
    except (FileNotFoundError, ValueError, OSError) as e:
        # No romper la cadena: si Excel no está (G: no montada), cae a 503 arriba
        print(f"[smtp_config] fallback Excel no disponible: {e}")
        return None
    if not creds:
        return None
    remitente, password = creds
    host = os.environ.get("PANOL_SMTP_HOST", "smtp.gmail.com").strip()
    port = int(os.environ.get("PANOL_SMTP_PORT", "587"))
    return SmtpConfig(
        host=host,
        port=port,
        user=remitente,
        password=password,
        from_addr=remitente,
    )


def obtener_smtp_config() -> SmtpConfig:
    cfg = _desde_env() or _desde_excel_solo_lectura()
    if not cfg:
        raise SmtpNoConfigurado(
            "Configurá PANOL_SMTP_USER y PANOL_SMTP_PASSWORD en .env, "
            "o verificá remitente/password en master_codes (hoja correos)."
        )
    return cfg
