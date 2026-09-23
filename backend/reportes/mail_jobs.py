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

import html as _html
import pandas as pd
from pathlib import Path as _Path

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


def _personal_destinatarios() -> list[str]:
    """Lee mails de Personal (panol.personal) donde activo=1 y email no vacío."""
    if os.environ.get("REPORTES_MAIL_USAR_PERSONAL", "0").strip().lower() in ("0", "false", "no", "off", ""):
        return []
    try:
        import pymysql
        from config import REPORTES_DB_HOST, REPORTES_DB_PORT, REPORTES_DB_USER, REPORTES_DB_PASSWORD, REPORTES_DB_NAME
        conn = pymysql.connect(
            host=REPORTES_DB_HOST, port=int(REPORTES_DB_PORT),
            user=REPORTES_DB_USER, password=REPORTES_DB_PASSWORD,
            database=REPORTES_DB_NAME, charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor
        )
        with conn.cursor() as cur:
            cur.execute("SELECT email FROM personal WHERE activo=1 AND email IS NOT NULL AND email <> ''")
            rows = cur.fetchall()
            mails = [str(r["email"]).strip() for r in rows if str(r["email"]).strip() and "@" in str(r["email"])]
            return mails
    except Exception as e:
        log.warning("No se pudieron leer mails de Personal: %s", e)
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _destinatarios(override: list[str] | None = None) -> list[str]:
    if override is not None:
        dest = [d.strip() for d in override if d and d.strip()]
        if not dest:
            raise MailNoConfiguradoError("Sin destinatarios (override vacío).")
        return list(dict.fromkeys(dest))
    # Base: env var + Personal si está habilitado
    dest_env = [d.strip() for d in REPORTES_MAIL_DESTINATARIOS if d and d.strip()]
    dest_personal = _personal_destinatarios()
    dest = dest_env + dest_personal
    if not dest:
        raise MailNoConfiguradoError(
            "Sin destinatarios. Seteá REPORTES_MAIL_DESTINATARIOS o activá REPORTES_MAIL_USAR_PERSONAL=1 con mails en Personal."
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


# ── Moderno preview (no envía, solo genera HTML del nuevo diseño) ─────────

ORDEN_SECTORES_GASTOS = [
    ("MANTENIMIENTO", "Mantenimiento"),
    ("EDILICIO", "Edilicio"),
    ("PROYECTOS", "Proyectos"),
    ("PRODUCCION", "Producción"),
]

ESTILO_SECTOR_HTML = {
    "MANTENIMIENTO": {"bg": "#D6EAF8", "border": "#2980B9", "title": "#1A5276", "th": "#2980B9"},
    "EDILICIO": {"bg": "#ECF0F1", "border": "#95A5A6", "title": "#566573", "th": "#7F8C8D"},
    "PROYECTOS": {"bg": "#D5F5E3", "border": "#27AE60", "title": "#1E8449", "th": "#27AE60"},
    "PRODUCCION": {"bg": "#FCF3CF", "border": "#F4D03F", "title": "#9A7D0A", "th": "#D4AC0D"},
}


def _formato_pesos_ar(valor: float) -> str:
    try:
        x = float(valor)
    except (TypeError, ValueError):
        return "$ 0"
    entero = int(round(x))
    s = f"{abs(entero):,}".replace(",", ".")
    if entero < 0:
        return f"- $ {s}"
    return f"$ {s}"


def _formato_precio_ar(valor: float) -> str:
    try:
        x = float(valor)
    except (TypeError, ValueError):
        return "$ 0"
    if pd.isna(x):
        return "$ 0"
    neg = x < 0
    x = abs(x)
    ent = int(x)
    frac = int(round((x - ent) * 100))
    if frac >= 100:
        ent += 1
        frac = 0
    s_int = f"{ent:,}".replace(",", ".")
    if abs(x - ent) < 1e-9 and frac == 0:
        body = s_int
    else:
        body = f"{s_int},{frac:02d}"
    if neg:
        return f"- $ {body}"
    return f"$ {body}"


def _fecha_formateada_ar(fecha: date) -> str:
    return f"{fecha.day}/{fecha.month}/{fecha.year}"


def _bloque_sector_html_moderno(code: str, etiqueta: str, df_sector: pd.DataFrame, g_dia: float, acum_mes: float) -> str:
    est = ESTILO_SECTOR_HTML.get(code, {"bg": "#F8F9F9", "border": "#BDC3C7", "title": "#2C3E50", "th": "#5D6D7E"})
    esc = _html.escape
    # Tabla detalle
    detalle_cols = ["FECHA", "CODIGO", "DESCRIPCION", "CANTIDAD", "PRECIO_UNITARIO", "MONTO_TOTAL_SALIDA", "TIPO_COMPROBANTE", "NUMERO_ORDEN", "MAQUINA_SITIO", "OPERARIO"]
    cab = [c.replace("_", " ") for c in detalle_cols]
    th_class = code.lower()
    header_html = "".join(f'<th class="{th_class}">{esc(h)}</th>' for h in cab)
    filas_html = ""
    if df_sector is not None and not df_sector.empty:
        df_s = df_sector.sort_values("OPERARIO")
        for _, row in df_s.iterrows():
            celdas = []
            for c in detalle_cols:
                v = row.get(c, "")
                if c == "PRECIO_UNITARIO":
                    celdas.append(f"<td class=\"monto\">{esc(_formato_precio_ar(v))}</td>")
                elif c == "MONTO_TOTAL_SALIDA":
                    celdas.append(f"<td class=\"monto\">{esc(_formato_pesos_ar(v))}</td>")
                elif c == "CANTIDAD":
                    try:
                        cv = float(v)
                        celdas.append(f"<td style=\"text-align:center;\">{int(cv) if cv==int(cv) else cv}</td>")
                    except Exception:
                        celdas.append(f"<td>{esc(str(v))}</td>")
                else:
                    celdas.append(f"<td>{esc(str(v) if pd.notna(v) else '')}</td>")
            filas_html += f"<tr>{''.join(celdas)}</tr>"
    else:
        filas_html = f"<tr><td colspan=\"{len(detalle_cols)}\" style=\"text-align:center;color:#718096;padding:12px;\">Sin movimientos para este sector el {esc(_fecha_formateada_ar(date.today()))}</td></tr>"

    bloque = f"""
    <div class=\"sector-block {th_class}\">
      <p class=\"sector-title {th_class}\">{esc(etiqueta)}</p>
      <p class=\"sector-meta\">Gasto del día: <b>{esc(_formato_pesos_ar(g_dia))}</b> &nbsp;•&nbsp; Acumulado mes: <b>{esc(_formato_pesos_ar(acum_mes))}</b></p>
    </div>
    <div class=\"table-wrap\">
      <table>
        <thead><tr>{header_html}</tr></thead>
        <tbody>{filas_html}</tbody>
      </table>
    </div>
    """
    return bloque


def armar_cuerpo_diario_moderno(fecha: date, df_dia: pd.DataFrame | None = None) -> tuple[str, str]:
    """Genera cuerpo TXT + HTML moderno con template mail_diario_moderno.html.

    Si df_dia es None, lo carga desde ReportesStore para la fecha.
    No envía mail.
    """
    store = ReportesStore.get()
    store.require_loaded()
    if df_dia is None:
        df_dia = _filtrar_por_fecha(store.df, fecha, fecha)
    filas = int(len(df_dia))
    monto_dia = float(pd.to_numeric(df_dia.get("MONTO_TOTAL_SALIDA", 0), errors="coerce").fillna(0).sum()) if filas else 0.0

    # Acumulado mes hasta fecha inclusive
    desde_mes = date(fecha.year, fecha.month, 1)
    df_mes = _filtrar_por_fecha(store.df, desde_mes, fecha)
    acum_mes = float(pd.to_numeric(df_mes.get("MONTO_TOTAL_SALIDA", 0), errors="coerce").fillna(0).sum()) if not df_mes.empty else 0.0

    # Sectores presentes (orden fijo + extras alfabético)
    presentes: set[str] = set()
    if not df_mes.empty and "SECTOR" in df_mes.columns:
        presentes.update(str(s).strip().upper() for s in df_mes["SECTOR"].dropna().unique())
    if not df_dia.empty and "SECTOR" in df_dia.columns:
        presentes.update(str(s).strip().upper() for s in df_dia["SECTOR"].dropna().unique())
    orden: list[tuple[str, str]] = []
    vistos: set[str] = set()
    for code, et in ORDEN_SECTORES_GASTOS:
        if code in presentes:
            orden.append((code, et))
            vistos.add(code)
    extras = sorted(c for c in presentes if c not in vistos)
    for c in extras:
        orden.append((c, c.replace("_", " ").title()))

    # Totales por sector día y mes
    tot_dia = {}
    tot_mes = {}
    if not df_dia.empty:
        g_d = df_dia.groupby("SECTOR")["MONTO_TOTAL_SALIDA"].sum()
        for k, v in g_d.items():
            tot_dia[str(k).upper()] = float(v)
    if not df_mes.empty:
        g_m = df_mes.groupby("SECTOR")["MONTO_TOTAL_SALIDA"].sum()
        for k, v in g_m.items():
            tot_mes[str(k).upper()] = float(v)

    # Bloques HTML por sector
    bloques_html = ""
    lineas_txt: list[str] = [
        f"Reporte diario de gastos por sector — {_fecha_formateada_ar(fecha)}",
        f"Movimientos: {filas} | Monto del día: {_formato_pesos_ar(monto_dia)} | Acumulado mes: {_formato_pesos_ar(acum_mes)}",
        "",
    ]
    for code, et in orden:
        g = tot_dia.get(code, 0.0)
        a = tot_mes.get(code, 0.0)
        df_s = df_dia[df_dia["SECTOR"] == code].copy() if not df_dia.empty and "SECTOR" in df_dia.columns else pd.DataFrame()
        bloques_html += _bloque_sector_html_moderno(code, et, df_s, g, a)
        lineas_txt.extend([f"{et}: día {_formato_pesos_ar(g)} | mes {_formato_pesos_ar(a)} ({len(df_s)} líneas)"])

    # Día a día table (por sector + total)
    # Build resumen día a día rows
    dias_mes = []
    d = desde_mes
    while d <= fecha:
        dias_mes.append(d)
        d += timedelta(days=1)
    # totales por día por sector
    totales_por_dia: dict[str, dict[str, float]] = {}
    for fd in dias_mes:
        df_fd = _filtrar_por_fecha(store.df, fd, fd)
        totales_por_dia[_fecha_formateada_ar(fd)] = {}
        if not df_fd.empty and "SECTOR" in df_fd.columns:
            g = df_fd.groupby("SECTOR")["MONTO_TOTAL_SALIDA"].sum()
            for k, v in g.items():
                totales_por_dia[_fecha_formateada_ar(fd)][str(k).upper()] = float(v)
    # Render tabla resumen día a día global
    if orden:
        hdr = ["Fecha"] + [et for _, et in orden] + ["Total día"]
        rows_html = ""
        lineas_txt.append("")
        lineas_txt.append("Día a día (todos los sectores):")
        for fd in dias_mes:
            k = _fecha_formateada_ar(fd)
            vals = totales_por_dia.get(k, {})
            td = sum(vals.get(code, 0.0) for code, _ in orden)
            row_vals = [k] + [_formato_pesos_ar(vals.get(code, 0.0)) for code, _ in orden] + [_formato_pesos_ar(td)]
            rows_html += "<tr>" + "".join(f"<td>{_html.escape(str(v))}</td>" for v in row_vals) + "</tr>"
            lineas_txt.append(" | ".join(str(v) for v in row_vals))
        tabla_resumen = f"""
        <p style="font-size:13px; font-weight:700; color:#1a365d; margin:18px 0 8px 0;">Resumen día a día — {fecha.strftime('%m/%Y')}</p>
        <div class="table-wrap"><table><thead><tr>{"".join(f"<th>{_html.escape(h)}</th>" for h in hdr)}</tr></thead><tbody>{rows_html}</tbody></table></div>
        """
    else:
        tabla_resumen = ""

    # Tabla detalle global (si hay filas)
    if not df_dia.empty:
        detalle_cols = ["FECHA", "CODIGO", "DESCRIPCION", "CANTIDAD", "PRECIO_UNITARIO", "MONTO_TOTAL_SALIDA", "TIPO_COMPROBANTE", "NUMERO_ORDEN", "MAQUINA_SITIO", "OPERARIO", "SECTOR"]
        # Use TXT only
        pass
        tabla_detalle = ""
    else:
        tabla_detalle = ""

    # Load template
    tpl_path = _Path(__file__).resolve().parent / "templates" / "mail_diario_moderno.html"
    try:
        tpl = tpl_path.read_text(encoding="utf-8")
    except Exception:
        # fallback minimal
        tpl = "<html><body><h1>Reporte {{FECHA_ISO}}</h1>{{BLOQUES_SECTOR}}</body></html>"

    html_out = tpl.replace("{{FECHA_ISO}}", fecha.isoformat())
    html_out = html_out.replace("{{FECHA_FORMATEADA}}", _fecha_formateada_ar(fecha))
    html_out = html_out.replace("{{FILAS}}", str(filas))
    html_out = html_out.replace("{{MONTO_TOTAL}}", _formato_pesos_ar(monto_dia))
    html_out = html_out.replace("{{ACUMULADO_MES}}", _formato_pesos_ar(acum_mes))
    sectores_resumen = ", ".join(f"{et}: {_formato_pesos_ar(tot_dia.get(code,0.0))}" for code, et in orden) if orden else "(sin sectores)"
    html_out = html_out.replace("{{SECTORES_RESUMEN}}", _html.escape(sectores_resumen))
    html_out = html_out.replace("{{BLOQUES_SECTOR}}", bloques_html)
    html_out = html_out.replace("{{TABLA_DETALLE}}", tabla_detalle)
    html_out = html_out.replace("{{TABLA_RESUMEN_DIA_A_DIA}}", tabla_resumen)
    html_out = html_out.replace("{{TIMESTAMP}}", pd.Timestamp.now().strftime("%d/%m/%Y %H:%M"))
    # Clean any leftover placeholders
    html_out = html_out.replace("{{", "").replace("}}", "")

    txt = "\n".join(lineas_txt)
    return txt, html_out


def preview_diario_moderno(fecha: date | str | None = None, *, destinatarios: list[str] | None = None) -> dict[str, Any]:
    """Genera preview del nuevo diseño sin enviar.

    Usa fecha (YYYY-MM-DD o date). Si no se pasa, usa ayer.
    Retorna dict con html, txt, métricas y estado de mail (sin enviar).
    Destinatario preview fijo: franco.sanabria@pilaresca.com.ar (no se usa para envío real aquí).
    """
    if isinstance(fecha, str):
        try:
            fecha = date.fromisoformat(fecha.strip())
        except Exception:
            # try dayfirst
            ts = pd.to_datetime(fecha, dayfirst=True, errors="coerce")
            fecha = ts.date() if not pd.isna(ts) else (date.today() - timedelta(days=1))
    if fecha is None:
        fecha = date.today() - timedelta(days=1)
    store = ReportesStore.get()
    store.require_loaded()
    df_dia = _filtrar_por_fecha(store.df, fecha, fecha)
    txt, html_mod = armar_cuerpo_diario_moderno(fecha, df_dia)
    xlsx = armar_excel_periodo(store, fecha, fecha)
    preview_dest = destinatarios or ["franco.sanabria@pilaresca.com.ar"]
    return {
        "enviado": False,
        "preview": True,
        "diseño": "moderno",
        "fecha": fecha.isoformat(),
        "fecha_formateada": _fecha_formateada_ar(fecha),
        "filas": int(len(df_dia)),
        "xlsx_bytes": len(xlsx),
        "asunto": f"Reporte Diario de Gasto por Sector ({fecha.isoformat()}) — PREVIEW MODERNO",
        "destinatario_preview": preview_dest,
        "cuerpo_txt_preview": txt[:2000],
        "cuerpo_html_len": len(html_mod),
        "cuerpo_html_preview": html_mod[:5000],
        "cuerpo_html_completo": html_mod,
        "nota": "PREVIEW ONLY — no se envió mail. Flags siguen en 0. Enviar solo a franco.sanabria@pilaresca.com.ar cuando el usuario apruebe el diseño.",
        **mail_status(),
    }


def dry_run_diario_moderno(fecha: date | None = None) -> dict[str, Any]:
    """Alias de preview para compat con dry-run endpoint futuro."""
    return preview_diario_moderno(fecha)

