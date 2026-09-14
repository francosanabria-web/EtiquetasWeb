# -*- coding: utf-8 -*-
"""Scaffold de envío diario/mensual de gastos — CONFIGURADO PERO DESACTIVADO.

No arranca schedulers ni envía mails reales mientras:
  REPORTES_MAIL_DIARIO_ENABLED=0
  REPORTES_MAIL_MENSUAL_ENABLED=0

Formato del adjunto = misma Excel Table que GET /api/reportes/export.xlsx
(columnas del detalle del mail escritorio + SECTOR).

Cómo activar después
--------------------
1. Configurar SMTP (mismas vars que email_service):
     PANOL_SMTP_USER / PANOL_SMTP_PASSWORD / PANOL_SMTP_FROM
2. REPORTES_MAIL_DESTINATARIOS=a@x.com,b@y.com
3. REPORTES_MAIL_DIARIO_ENABLED=1  (y/o MENSUAL=1)
4. Programar tarea Windows / supervisor que llame:
     python -c "from mail_jobs import run_diario_si_habilitado; print(run_diario_si_habilitado())"
   o POST /api/reportes/mail/diario (solo si el flag está en 1; si no, 403).
5. ⚠️ Aún falta portar el cuerpo HTML completo multi-sector del escritorio
   (resúmenes + día a día + líneas Mant.). Hoy el scaffold envía un resumen
   simple + adjunto Excel Table de movimientos del período.
"""

from __future__ import annotations

import logging
import os
import smtplib
from datetime import date, timedelta
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import pandas as pd

from config import (
    REPORTES_MAIL_DESTINATARIOS,
    REPORTES_MAIL_DIARIO_ENABLED,
    REPORTES_MAIL_DIARIO_HORA,
    REPORTES_MAIL_MENSUAL_DIA,
    REPORTES_MAIL_MENSUAL_ENABLED,
    REPORTES_MAIL_MENSUAL_HORA,
)
from exports import build_xlsx_tabla
from store import ReportesStore

log = logging.getLogger("reportes.mail")


class MailDesactivadoError(Exception):
    pass


class MailNoConfiguradoError(Exception):
    pass


def mail_status() -> dict[str, Any]:
    return {
        "diario_enabled": REPORTES_MAIL_DIARIO_ENABLED,
        "mensual_enabled": REPORTES_MAIL_MENSUAL_ENABLED,
        "diario_hora": REPORTES_MAIL_DIARIO_HORA,
        "mensual_dia": REPORTES_MAIL_MENSUAL_DIA,
        "mensual_hora": REPORTES_MAIL_MENSUAL_HORA,
        "destinatarios_configurados": len(REPORTES_MAIL_DESTINATARIOS),
        "destinatarios": list(REPORTES_MAIL_DESTINATARIOS),
        "smtp_user_set": bool(
            (os.environ.get("PANOL_SMTP_USER") or os.environ.get("PANOL_SMTP_FROM") or "").strip()
        ),
        "nota": (
            "Flags en 0 = no envía. Activar con REPORTES_MAIL_*_ENABLED=1 "
            "+ destinatarios + SMTP. Sin scheduler en este servicio."
        ),
    }


def _smtp_creds() -> tuple[str, int, str, str, str]:
    user = (os.environ.get("PANOL_SMTP_USER") or os.environ.get("PANOL_SMTP_FROM") or "").strip()
    password = (os.environ.get("PANOL_SMTP_PASSWORD") or "").strip()
    from_addr = (os.environ.get("PANOL_SMTP_FROM") or user).strip()
    host = os.environ.get("PANOL_SMTP_HOST", "smtp.gmail.com").strip()
    port = int(os.environ.get("PANOL_SMTP_PORT", "587"))
    if not user or not password:
        raise MailNoConfiguradoError(
            "Configurá PANOL_SMTP_USER y PANOL_SMTP_PASSWORD (mismo patrón que email_service)."
        )
    return host, port, user, password, from_addr


def _destinatarios(override: list[str] | None = None) -> list[str]:
    dest = [d.strip() for d in (override or REPORTES_MAIL_DESTINATARIOS) if d and d.strip()]
    if not dest:
        raise MailNoConfiguradoError(
            "Sin destinatarios. Seteá REPORTES_MAIL_DESTINATARIOS o pasá override."
        )
    return list(dict.fromkeys(dest))


def _filtrar_por_fecha(df: pd.DataFrame, desde: date, hasta: date) -> pd.DataFrame:
    if df.empty or "_fecha" not in df.columns:
        return df.iloc[0:0]
    d0 = pd.Timestamp(desde)
    d1 = pd.Timestamp(hasta)
    return df[(df["_fecha"] >= d0) & (df["_fecha"] <= d1)].copy()


def armar_excel_periodo(store: ReportesStore, desde: date, hasta: date) -> bytes:
    store.require_loaded()
    df = _filtrar_por_fecha(store.df, desde, hasta)
    if "_fecha" in df.columns and not df.empty:
        df = df.sort_values("_fecha", ascending=False, na_position="last")
    return build_xlsx_tabla(df, sheet_name="Movimientos", table_name="TablaGastos")


def armar_cuerpo_diario(fecha: date, df: pd.DataFrame) -> tuple[str, str]:
    """Resumen simple. ⚠️ Cuerpo HTML completo multi-sector del escritorio: pendiente."""
    filas = int(len(df))
    monto = float(pd.to_numeric(df.get("MONTO_TOTAL_SALIDA", 0), errors="coerce").fillna(0).sum()) if filas else 0.0
    fs = fecha.strftime("%Y-%m-%d")
    txt = (
        f"Adjunto reporte diario de gastos ({fs}).\n\n"
        f"Movimientos: {filas}\n"
        f"Monto total: $ {monto:,.2f}\n\n"
        "Detalle en el Excel adjunto (formato tabla).\n"
    )
    html = (
        f'<p style="font-family:Arial,sans-serif;font-size:13px;color:#1a5276;">'
        f"Reporte diario de gastos por sector.</p>"
        f'<p style="font-family:Arial,sans-serif;font-size:13px;">'
        f"Fecha: <b>{fs}</b><br/>"
        f"Movimientos: <b>{filas}</b><br/>"
        f"Monto total: <b>$ {monto:,.2f}</b></p>"
        f'<p style="font-family:Arial,sans-serif;font-size:12px;color:#555;">'
        f"El detalle está en el Excel adjunto (tabla Movimientos).</p>"
    )
    return txt, html


def armar_cuerpo_mensual(year: int, month: int, df: pd.DataFrame) -> tuple[str, str]:
    filas = int(len(df))
    monto = float(pd.to_numeric(df.get("MONTO_TOTAL_SALIDA", 0), errors="coerce").fillna(0).sum()) if filas else 0.0
    label = f"{month:02d}/{year}"
    txt = (
        f"Adjunto reporte mensual de gastos ({label}).\n\n"
        f"Movimientos: {filas}\n"
        f"Monto total: $ {monto:,.2f}\n\n"
        "Detalle en el Excel adjunto (formato tabla).\n"
    )
    html = (
        f'<p style="font-family:Arial,sans-serif;font-size:13px;color:#1a5276;">'
        f"Reporte mensual de gastos.</p>"
        f'<p style="font-family:Arial,sans-serif;font-size:13px;">'
        f"Período: <b>{label}</b><br/>"
        f"Movimientos: <b>{filas}</b><br/>"
        f"Monto total: <b>$ {monto:,.2f}</b></p>"
        f'<p style="font-family:Arial,sans-serif;font-size:12px;color:#555;">'
        f"El detalle está en el Excel adjunto (tabla Movimientos).</p>"
    )
    return txt, html


def enviar_con_adjunto_xlsx(
    *,
    destinatarios: list[str],
    asunto: str,
    cuerpo_txt: str,
    cuerpo_html: str,
    xlsx_bytes: bytes,
    filename: str,
) -> None:
    host, port, user, password, from_addr = _smtp_creds()
    dest = _destinatarios(destinatarios)

    msg = MIMEMultipart("mixed")
    msg["From"] = from_addr
    msg["To"] = ", ".join(dest)
    msg["Subject"] = asunto

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(cuerpo_txt, "plain", "utf-8"))
    alt.attach(MIMEText(cuerpo_html, "html", "utf-8"))
    msg.attach(alt)

    part = MIMEBase(
        "application",
        "vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    part.set_payload(xlsx_bytes)
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
    msg.attach(part)

    with smtplib.SMTP(host, port, timeout=45) as server:
        server.starttls()
        server.login(user, password)
        server.sendmail(from_addr, dest, msg.as_string())


def run_diario_si_habilitado(
    fecha: date | None = None,
    *,
    destinatarios: list[str] | None = None,
    forzar: bool = False,
) -> dict[str, Any]:
    """Arma y (si enabled) envía el diario. Sin enabled → no envía."""
    if not forzar and not REPORTES_MAIL_DIARIO_ENABLED:
        return {
            "enviado": False,
            "motivo": "REPORTES_MAIL_DIARIO_ENABLED=0",
            **mail_status(),
        }

    fecha_ref = fecha or (date.today() - timedelta(days=1))
    store = ReportesStore.get()
    store.require_loaded()
    df = _filtrar_por_fecha(store.df, fecha_ref, fecha_ref)
    xlsx = armar_excel_periodo(store, fecha_ref, fecha_ref)
    txt, html = armar_cuerpo_diario(fecha_ref, df)
    asunto = f"Reporte Diario de Gasto por Sector ({fecha_ref.strftime('%Y-%m-%d')})"
    fname = f"Reporte_Gastos_{fecha_ref.strftime('%Y-%m-%d')}.xlsx"
    dest = _destinatarios(destinatarios)
    enviar_con_adjunto_xlsx(
        destinatarios=dest,
        asunto=asunto,
        cuerpo_txt=txt,
        cuerpo_html=html,
        xlsx_bytes=xlsx,
        filename=fname,
    )
    log.info("Mail diario enviado a %s (%s filas)", dest, len(df))
    return {
        "enviado": True,
        "tipo": "diario",
        "fecha": fecha_ref.isoformat(),
        "filas": int(len(df)),
        "destinatarios": dest,
        "adjunto": fname,
    }


def run_mensual_si_habilitado(
    year: int | None = None,
    month: int | None = None,
    *,
    destinatarios: list[str] | None = None,
    forzar: bool = False,
) -> dict[str, Any]:
    if not forzar and not REPORTES_MAIL_MENSUAL_ENABLED:
        return {
            "enviado": False,
            "motivo": "REPORTES_MAIL_MENSUAL_ENABLED=0",
            **mail_status(),
        }

    hoy = date.today()
    y = year or hoy.year
    m = month or hoy.month
    desde = date(y, m, 1)
    if m == 12:
        hasta = date(y + 1, 1, 1) - timedelta(days=1)
    else:
        hasta = date(y, m + 1, 1) - timedelta(days=1)
    if y == hoy.year and m == hoy.month:
        hasta = min(hasta, hoy)

    store = ReportesStore.get()
    store.require_loaded()
    df = _filtrar_por_fecha(store.df, desde, hasta)
    xlsx = armar_excel_periodo(store, desde, hasta)
    txt, html = armar_cuerpo_mensual(y, m, df)
    asunto = f"Reporte Mensual de Gastos ({m:02d}/{y})"
    fname = f"Reporte_Gastos_Mensual_{y}-{m:02d}.xlsx"
    dest = _destinatarios(destinatarios)
    enviar_con_adjunto_xlsx(
        destinatarios=dest,
        asunto=asunto,
        cuerpo_txt=txt,
        cuerpo_html=html,
        xlsx_bytes=xlsx,
        filename=fname,
    )
    log.info("Mail mensual enviado a %s (%s filas)", dest, len(df))
    return {
        "enviado": True,
        "tipo": "mensual",
        "periodo": f"{y}-{m:02d}",
        "filas": int(len(df)),
        "destinatarios": dest,
        "adjunto": fname,
    }


def dry_run_diario(fecha: date | None = None) -> dict[str, Any]:
    """Arma el Excel/cuerpo sin enviar (siempre seguro)."""
    fecha_ref = fecha or (date.today() - timedelta(days=1))
    store = ReportesStore.get()
    store.require_loaded()
    df = _filtrar_por_fecha(store.df, fecha_ref, fecha_ref)
    xlsx = armar_excel_periodo(store, fecha_ref, fecha_ref)
    txt, html = armar_cuerpo_diario(fecha_ref, df)
    return {
        "enviado": False,
        "dry_run": True,
        "fecha": fecha_ref.isoformat(),
        "filas": int(len(df)),
        "xlsx_bytes": len(xlsx),
        "asunto": f"Reporte Diario de Gasto por Sector ({fecha_ref.strftime('%Y-%m-%d')})",
        "cuerpo_txt_preview": txt[:400],
        "cuerpo_html_len": len(html),
        **mail_status(),
    }
