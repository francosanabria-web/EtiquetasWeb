# -*- coding: utf-8 -*-
"""Scaffold de envío diario/mensual/activos — CONFIGURADO PERO DESACTIVADO POR DEFECTO.

No arranca schedulers ni envía mails reales mientras:
  REPORTES_MAIL_DIARIO_ENABLED=0
  REPORTES_MAIL_MENSUAL_ENABLED=0
  REPORTES_MAIL_ACTIVOS_ENABLED=0

Formato del adjunto = misma Excel Table que GET /api/reportes/export.xlsx
(columnas del detalle del mail escritorio + SECTOR).

Para activos fuera, usar mail_activos.py independiente (mismo .env, misma lógica SMTP).

Cómo activar después
--------------------
1. Configurar SMTP (mismas vars que email_service):
      PANOL_SMTP_USER / PANOL_SMTP_PASSWORD / PANOL_SMTP_FROM
2. REPORTES_MAIL_DESTINATARIOS=a@x.com,b@y.com
3. REPORTES_MAIL_DIARIO_ENABLED=1  (y/o MENSUAL=1 / ACTIVOS=1)
4. Programar tarea Windows / supervisor que llame:
      python -c "from mail_jobs import run_diario_si_habilitado; print(run_diario_si_habilitado())"
    o POST /api/reportes/mail/diario (solo si el flag está en 1; si no, 403).
     Cuerpo HTML: mail_diario_moderno.html (bloques por sector, tabla día a día, acumulado mes).
     Usa armar_cuerpo_diario_moderno() como cuerpo de envío.
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
    REPORTES_MAIL_ACTIVOS_ENABLED,
)
from exports import build_xlsx_tabla
from store import CargandoDatosError, ReportesStore

log = logging.getLogger("reportes.mail")


class MailDesactivadoError(Exception):
    pass


class MailNoConfiguradoError(Exception):
    pass


def mail_status() -> dict[str, Any]:
    return {
        "diario_enabled": REPORTES_MAIL_DIARIO_ENABLED,
        "mensual_enabled": REPORTES_MAIL_MENSUAL_ENABLED,
        "activos_enabled": REPORTES_MAIL_ACTIVOS_ENABLED,
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


def _personal_destinatarios(mail_tipo: str = "diario_gastos") -> list[str]:
    """Lee mails de Personal filtrados por preferencias de mail.
    
    Si personal_mail_prefs existe y tiene registros para mail_tipo,
    solo retorna los personales donde habilitado=1 para ese tipo.
    Si la tabla no existe o está vacía, fallback a todos los activos
    (compatibilidad con implementación previa).
    """
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
            cur.execute(
                "SELECT COUNT(*) AS c FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s",
                (REPORTES_DB_NAME, "personal_mail_prefs"),
            )
            table_exists = cur.fetchone()["c"] > 0

            if table_exists:
                cur.execute(
                    "SELECT COUNT(*) AS c FROM personal_mail_prefs WHERE mail_tipo = %s",
                    (mail_tipo,),
                )
                has_prefs = cur.fetchone()["c"] > 0

                if has_prefs:
                    cur.execute(
                        """SELECT p.email FROM personal p
                           INNER JOIN personal_mail_prefs pmp
                             ON pmp.personal_id = p.id AND pmp.mail_tipo = %s AND pmp.habilitado = 1
                           WHERE p.activo = 1 AND p.email IS NOT NULL AND p.email <> ''""",
                        (mail_tipo,),
                    )
                else:
                    cur.execute(
                        "SELECT email FROM personal WHERE activo=1 AND email IS NOT NULL AND email <> ''"
                    )
            else:
                cur.execute(
                    "SELECT email FROM personal WHERE activo=1 AND email IS NOT NULL AND email <> ''"
                )

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


def _destinatarios(override: list[str] | None = None, mail_tipo: str = "diario_gastos") -> list[str]:
    if override is not None:
        dest = [d.strip() for d in override if d and d.strip()]
        if not dest:
            raise MailNoConfiguradoError("Sin destinatarios (override vacío).")
        return list(dict.fromkeys(dest))
    dest_env = [d.strip() for d in REPORTES_MAIL_DESTINATARIOS if d and d.strip()]
    dest_personal = _personal_destinatarios(mail_tipo=mail_tipo)
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


def armar_excel_mensual_con_grafico(store: ReportesStore, year: int, month: int) -> bytes:
    """Excel mensual: respeta formato TablaGastos pero agrega gráficos (openpyxl).

    Hojas:
      - Movimientos (TablaGastos, mismo que diario)
      - RESUMEN_SECTOR (torta) + POR_LINEA_MANT (columnas) con gráficos openpyxl
    Respeta el formato actual (openpyxl Table) y añade hojas con gráficos.
    Fallback: si openpyxl charts no disponible, devuelve TablaGastos simple.
    """
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.chart import PieChart, BarChart, Reference

    desde = date(year, month, 1)
    if month == 12:
        hasta = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        hasta = date(year, month + 1, 1) - timedelta(days=1)
    hoy = date.today()
    if year == hoy.year and month == hoy.month:
        hasta = min(hasta, hoy)

    df = _filtrar_por_fecha(store.df, desde, hasta)
    if "_fecha" in df.columns and not df.empty:
        df = df.sort_values("_fecha", ascending=False, na_position="last")

    from config import COLUMNAS_EXPORT_TABLA as COLS

    # Totales por sector y por línea
    tot_sector: dict[str, float] = {}
    if not df.empty and "SECTOR" in df.columns:
        g = df.groupby("SECTOR")["MONTO_TOTAL_SALIDA"].sum()
        for k, v in g.items():
            tot_sector[str(k).upper()] = float(v)
    presentes = set(tot_sector.keys())
    orden = []
    vistos = set()
    for code, et in ORDEN_SECTORES_GASTOS:
        if code in presentes:
            orden.append((code, et))
            vistos.add(code)
    for c in sorted(presentes - vistos):
        orden.append((c, c.title()))
    if not orden and not df.empty:
        for c in sorted(presentes):
            orden.append((c, c))

    desde_m = date(year, month, 1)
    dias_mes = []
    d = desde_m
    while d <= hasta:
        dias_mes.append(d)
        d += timedelta(days=1)
    dia_linea = _gastos_dia_por_linea_mantenimiento_mes(store, hasta, dias_mes)
    gl_map: dict[str, float] = {}
    for k in dia_linea:
        for ln, val in dia_linea[k].items():
            gl_map[ln] = gl_map.get(ln, 0.0) + val
    orden_lineas = _orden_lineas_gasto()
    lineas = sorted([ln for ln in gl_map if gl_map[ln] > 0], key=lambda x: (orden_lineas.index(x) if x in orden_lineas else 999, x))

    # Crear workbook con openpyxl
    wb = Workbook()
    # ── Hoja Movimientos ──
    ws = wb.active
    ws.title = "Movimientos"
    HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
    HEADER_FONT = Font(bold=True, color="FFFFFF")
    THIN = Border(left=Side(style="thin", color="BFBFBF"), right=Side(style="thin", color="BFBFBF"), top=Side(style="thin", color="BFBFBF"), bottom=Side(style="thin", color="BFBFBF"))
    for col_idx, col_name in enumerate(COLS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=col_name.replace("_", " "))
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = THIN
        width = 36 if col_name == "DESCRIPCION" else (16 if col_name in ("MONTO_TOTAL_SALIDA", "PRECIO_UNITARIO") else 14)
        ws.column_dimensions[get_column_letter(col_idx)].width = width
    if not df.empty:
        for r, (_, row) in enumerate(df.iterrows(), start=2):
            for c_idx, col_name in enumerate(COLS, start=1):
                v = row.get(col_name, "")
                cell = ws.cell(row=r, column=c_idx)
                cell.border = THIN
                if col_name in ("CANTIDAD", "PRECIO_UNITARIO", "MONTO_TOTAL_SALIDA"):
                    try:
                        num = float(v) if v is not None and str(v).strip() != "" else 0
                    except Exception:
                        num = 0
                    cell.value = num
                    if col_name in ("PRECIO_UNITARIO", "MONTO_TOTAL_SALIDA"):
                        cell.number_format = '"$"#,##0.00'
                    cell.alignment = Alignment(horizontal="right")
                else:
                    cell.value = "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = f"A1:{get_column_letter(len(COLS))}{len(df)+1}"
    else:
        ws.cell(row=2, column=1, value="").border = THIN
        ws.freeze_panes = "A2"

    # ── Hoja RESUMEN_SECTOR ──
    ws2 = wb.create_sheet("RESUMEN_SECTOR")
    ws2.cell(row=1, column=1, value="SECTOR").fill = HEADER_FILL
    ws2.cell(row=1, column=1).font = HEADER_FONT
    ws2.cell(row=1, column=1).border = THIN
    ws2.cell(row=1, column=1).alignment = Alignment(horizontal="center")
    ws2.cell(row=1, column=2, value="TOTAL_MES").fill = HEADER_FILL
    ws2.cell(row=1, column=2).font = HEADER_FONT
    ws2.cell(row=1, column=2).border = THIN
    ws2.cell(row=1, column=2).alignment = Alignment(horizontal="center")
    ws2.column_dimensions["A"].width = 22
    ws2.column_dimensions["B"].width = 18
    total_mes = sum(tot_sector.values())
    for r, (code, et) in enumerate(orden, start=2):
        c1 = ws2.cell(row=r, column=1, value=et)
        c1.border = THIN
        c2 = ws2.cell(row=r, column=2, value=round(float(tot_sector.get(code, 0.0)), 2))
        c2.border = THIN
        c2.number_format = '"$"#,##0.00'
    r_tot = len(orden) + 2
    c1 = ws2.cell(row=r_tot, column=1, value="TOTAL")
    c1.fill = HEADER_FILL
    c1.font = HEADER_FONT
    c1.border = THIN
    c1.alignment = Alignment(horizontal="center")
    c2 = ws2.cell(row=r_tot, column=2, value=round(total_mes, 2))
    c2.font = Font(bold=True, color="C00000")
    c2.border = THIN
    c2.number_format = '"$"#,##0.00'
    if orden and total_mes > 0:
        try:
            from openpyxl.chart.label import DataLabelList
            pie = PieChart()
            labels = Reference(ws2, min_col=1, min_row=2, max_row=1+len(orden))
            data = Reference(ws2, min_col=2, min_row=1, max_row=1+len(orden))
            pie.add_data(data, titles_from_data=True)
            pie.set_categories(labels)
            pie.title = f"Gasto por sector — {month:02d}/{year}"
            pie.height = 9
            pie.width = 15
            pie.style = 10
            # Mostrar categoría + valor $ + porcentaje
            pie.dataLabels = DataLabelList()
            pie.dataLabels.showCatName = True
            pie.dataLabels.showVal = True
            pie.dataLabels.showPercent = True
            pie.dataLabels.showLeaderLines = True
            pie.dataLabels.numFmt = '"$"#,##0'
            ws2.add_chart(pie, "D2")
        except Exception:
            pass

    # ── Hoja POR_LINEA_MANT ──
    if lineas:
        ws3 = wb.create_sheet("POR_LINEA_MANT")
        ws3.cell(row=1, column=1, value="LINEA_PAÑOL").fill = HEADER_FILL
        ws3.cell(row=1, column=1).font = HEADER_FONT
        ws3.cell(row=1, column=1).border = THIN
        ws3.cell(row=1, column=1).alignment = Alignment(horizontal="center")
        ws3.cell(row=1, column=2, value="TOTAL_MES").fill = HEADER_FILL
        ws3.cell(row=1, column=2).font = HEADER_FONT
        ws3.cell(row=1, column=2).border = THIN
        ws3.cell(row=1, column=2).alignment = Alignment(horizontal="center")
        ws3.column_dimensions["A"].width = 18
        ws3.column_dimensions["B"].width = 18
        total_mant = sum(gl_map.values())
        for r, ln in enumerate(lineas, start=2):
            c1 = ws3.cell(row=r, column=1, value=ln)
            c1.border = THIN
            c2 = ws3.cell(row=r, column=2, value=round(float(gl_map[ln]), 2))
            c2.border = THIN
            c2.number_format = '"$"#,##0.00'
        r_tot2 = len(lineas) + 2
        c1 = ws3.cell(row=r_tot2, column=1, value="TOTAL MANT.")
        c1.fill = HEADER_FILL
        c1.font = HEADER_FONT
        c1.border = THIN
        c1.alignment = Alignment(horizontal="center")
        c2 = ws3.cell(row=r_tot2, column=2, value=round(total_mant, 2))
        c2.font = Font(bold=True, color="C00000")
        c2.border = THIN
        c2.number_format = '"$"#,##0.00'
        if total_mant > 0:
            try:
                from openpyxl.chart.label import DataLabelList
                bar = BarChart()
                bar.type = "col"
                bar.title = f"Mantenimiento por línea — {month:02d}/{year}"
                bar.x_axis.title = "Línea / Paño"
                bar.y_axis.title = 'Total $'
                bar.y_axis.numFmt = '"$"#,##0'
                bar.style = 10
                data = Reference(ws3, min_col=2, min_row=1, max_row=1+len(lineas))
                cats = Reference(ws3, min_col=1, min_row=2, max_row=1+len(lineas))
                bar.add_data(data, titles_from_data=True)
                bar.set_categories(cats)
                bar.height = 9
                bar.width = 18
                # Etiquetas con valor $ arriba de cada barra
                bar.dataLabels = DataLabelList()
                bar.dataLabels.showVal = True
                bar.dataLabels.showCatName = False
                bar.dataLabels.numFmt = '"$"#,##0'
                # Hacer que el eje Y muestre $ con separador miles
                bar.y_axis.scaling.min = 0
                ws3.add_chart(bar, "D2")
            except Exception:
                pass

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


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
    try:
        store.require_loaded()
    except CargandoDatosError:
        # Proceso fresco de Task Scheduler: el store arranca vacío sin el thread de main.py.
        # Hacemos refresh sincrónico idéntico a activos (mail_activos.py: s.refresh()).
        store.refresh()
        store.require_loaded()
    df = _filtrar_por_fecha(store.df, fecha_ref, fecha_ref)
    if len(df) == 0 and not forzar and destinatarios is None:
        return {
            "enviado": False,
            "motivo": f"sin_movimientos_{fecha_ref.isoformat()}",
            **mail_status(),
        }
    xlsx = armar_excel_periodo(store, fecha_ref, fecha_ref)
    txt, html = armar_cuerpo_diario_moderno(fecha_ref, df_dia=df)
    asunto = f"Reporte Diario de Gasto por Sector ({fecha_ref.strftime('%Y-%m-%d')})"
    fname = f"Reporte_Gastos_{fecha_ref.strftime('%Y-%m-%d')}.xlsx"
    dest = _destinatarios(destinatarios, mail_tipo="diario_gastos")
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


def _marca_mensual_path() -> _Path:
    return _Path(__file__).resolve().parent / ".ultimo_mail_mensual.txt"


def _leer_marca_mensual() -> str:
    p = _marca_mensual_path()
    if not p.is_file():
        return ""
    try:
        return p.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def _escribir_marca_mensual(periodo: str) -> None:
    p = _marca_mensual_path()
    try:
        p.write_text(periodo.strip() + "\n", encoding="utf-8")
    except Exception as e:
        log.warning("No se pudo escribir marca mensual %s: %s", periodo, e)


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
    # Si se llama sin args el día 1, se asume mes anterior (caso 01/10 -> 09)
    if year is None and month is None and hoy.day == 1:
        if hoy.month == 1:
            y = hoy.year - 1
            m = 12
        else:
            y = hoy.year
            m = hoy.month - 1
    else:
        y = year or hoy.year
        m = month or hoy.month
    periodo = f"{y:04d}-{m:02d}"
    # Candado idempotente: si ya se envió este período y no es forzar, no reenviar
    if not forzar:
        marca = _leer_marca_mensual()
        if marca == periodo:
            log.info("Mensual %s ya enviado (marca %s), se omite reenvío", periodo, marca)
            return {
                "enviado": False,
                "motivo": f"ya_enviado_{periodo}",
                "periodo": periodo,
                "marca_path": str(_marca_mensual_path()),
                "marca_contenido": marca,
                **mail_status(),
            }
    desde = date(y, m, 1)
    if m == 12:
        hasta = date(y + 1, 1, 1) - timedelta(days=1)
    else:
        hasta = date(y, m + 1, 1) - timedelta(days=1)
    if y == hoy.year and m == hoy.month:
        hasta = min(hasta, hoy)

    store = ReportesStore.get()
    try:
        store.require_loaded()
    except CargandoDatosError:
        store.refresh()
        store.require_loaded()
    df = _filtrar_por_fecha(store.df, desde, hasta)
    # Excel mensual con gráfico (respeta formato TablaGastos + hojas con gráficos)
    try:
        xlsx = armar_excel_mensual_con_grafico(store, y, m)
    except Exception as e:
        log.warning("Fallo armar_excel_mensual_con_grafico, fallback a periodo: %s", e)
        xlsx = armar_excel_periodo(store, desde, hasta)
    # Preferir cuerpo moderno si está disponible (mismo diseño que diario moderno)
    try:
        txt, html = armar_cuerpo_mensual_moderno(y, m, df)
        asunto = f"Reporte Mensual de Gastos por Sector — {_mes_formateado_es(y, m)} ({y}-{m:02d})"
    except Exception as e:
        log.warning("Fallo armar_cuerpo_mensual_moderno, fallback a clásico: %s", e)
        txt, html = armar_cuerpo_mensual(y, m, df)
        asunto = f"Reporte Mensual de Gastos ({m:02d}/{y})"
    fname = f"Reporte_Gastos_Mensual_{y}-{m:02d}.xlsx"
    dest = _destinatarios(destinatarios, mail_tipo="diario_gastos")
    enviar_con_adjunto_xlsx(
        destinatarios=dest,
        asunto=asunto,
        cuerpo_txt=txt,
        cuerpo_html=html,
        xlsx_bytes=xlsx,
        filename=fname,
    )
    log.info("Mail mensual enviado a %s (%s filas)", dest, len(df))
    # Escribir marca solo en envíos reales (sin override) para no bloquear producción con pruebas a Franco
    if destinatarios is None:
        _escribir_marca_mensual(periodo)
    return {
        "enviado": True,
        "tipo": "mensual",
        "periodo": f"{y}-{m:02d}",
        "filas": int(len(df)),
        "destinatarios": dest,
        "adjunto": fname,
        "marca_path": str(_marca_mensual_path()) if destinatarios is None else None,
    }


def dry_run_diario(fecha: date | None = None) -> dict[str, Any]:
    """Arma el Excel/cuerpo sin enviar (siempre seguro)."""
    fecha_ref = fecha or (date.today() - timedelta(days=1))
    store = ReportesStore.get()
    try:
        store.require_loaded()
    except CargandoDatosError:
        store.refresh()
        store.require_loaded()
    df = _filtrar_por_fecha(store.df, fecha_ref, fecha_ref)
    xlsx = armar_excel_periodo(store, fecha_ref, fecha_ref)
    txt, html = armar_cuerpo_diario_moderno(fecha_ref, df_dia=df)
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


def _normalizar_linea_gasto(val) -> str:
    """Agrupa comprobante como línea (L1…L7, PAÑOL, etc.) para totales de mantenimiento."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "OTROS"
    s = str(val).strip().upper()
    if not s:
        return "OTROS"
    if s in ("PAÑ", "PAN", "PAÑOL", "PANOL"):
        return "PAÑOL"
    for ln in ("L1", "L2", "L3", "L4", "L5", "L6", "L7"):
        if s == ln or s.startswith(ln + " ") or s.startswith(ln + "-") or s.startswith(ln + "/"):
            return ln
    if s == "PROYECTOS":
        return "PROYECTOS"
    return s


def _orden_lineas_gasto():
    return ["PAÑOL"] + [f"L{i}" for i in range(1, 8)] + ["PROYECTOS"]


def _gastos_dia_por_linea_mantenimiento_mes(store, fecha_ref, dias_mes):
    """Por cada día del mes: total de mantenimiento desglosado por línea/pañol."""
    dia_linea = {}
    for fd in dias_mes:
        k = _fecha_formateada_ar(fd)
        dia_linea[k] = {}
        df_d = _filtrar_por_fecha(store.df, fd, fd)
        if df_d is None or df_d.empty or "TIPO_COMPROBANTE" not in df_d.columns or "SECTOR" not in df_d.columns:
            continue
        dm = df_d[df_d["SECTOR"].astype(str).str.upper() == "MANTENIMIENTO"].copy()
        if dm.empty:
            continue
        dm["MONTO_TOTAL_SALIDA"] = pd.to_numeric(dm.get("MONTO_TOTAL_SALIDA", 0), errors="coerce").fillna(0.0)
        dm["_LINEA"] = dm["TIPO_COMPROBANTE"].apply(_normalizar_linea_gasto)
        g = dm.groupby("_LINEA")["MONTO_TOTAL_SALIDA"].sum()
        for ln in g.index:
            dia_linea[k][str(ln)] = float(g[ln])
    return dia_linea


def _bloque_sector_html_moderno(code: str, etiqueta: str, df_sector: pd.DataFrame, g_dia: float, acum_mes: float) -> str:
    est = ESTILO_SECTOR_HTML.get(code, {"bg": "#F8F9F9", "border": "#BDC3C7", "title": "#2C3E50", "th": "#5D6D7E"})
    esc = _html.escape
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
    <div class="sector-block {th_class}">
      <p class="sector-title {th_class}">{esc(etiqueta)}</p>
      <p class="sector-meta">Gasto del día: <b>{esc(_formato_pesos_ar(g_dia))}</b> &nbsp;•&nbsp; Acumulado mes: <b>{esc(_formato_pesos_ar(acum_mes))}</b></p>
    </div>
    <div class="table-wrap">
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

    desde_mes = date(fecha.year, fecha.month, 1)
    df_mes = _filtrar_por_fecha(store.df, desde_mes, fecha)
    acum_mes = float(pd.to_numeric(df_mes.get("MONTO_TOTAL_SALIDA", 0), errors="coerce").fillna(0).sum()) if not df_mes.empty else 0.0

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

    bloques_html = ""
    lineas_txt: list[str] = [
        f"Reporte diario de gastos por sector — {_fecha_formateada_ar(fecha)}",
        f"Movimientos: {filas} | Monto del día: {_formato_pesos_ar(monto_dia)} | Acumulado mes: {_formato_pesos_ar(acum_mes)}",
        "",
    ]
    sector_lineas_txt: list[str] = []
    for code, et in orden:
        g = tot_dia.get(code, 0.0)
        a = tot_mes.get(code, 0.0)
        df_s = df_dia[df_dia["SECTOR"] == code].copy() if not df_dia.empty and "SECTOR" in df_dia.columns else pd.DataFrame()
        bloques_html += _bloque_sector_html_moderno(code, et, df_s, g, a)
        sector_lineas_txt.extend([f"{et}: día {_formato_pesos_ar(g)} | mes {_formato_pesos_ar(a)} ({len(df_s)} líneas)"])

    dias_mes = []
    d = desde_mes
    while d <= fecha:
        dias_mes.append(d)
        d += timedelta(days=1)
    totales_por_dia: dict[str, dict[str, float]] = {}
    for fd in dias_mes:
        df_fd = _filtrar_por_fecha(store.df, fd, fd)
        totales_por_dia[_fecha_formateada_ar(fd)] = {}
        if not df_fd.empty and "SECTOR" in df_fd.columns:
            g = df_fd.groupby("SECTOR")["MONTO_TOTAL_SALIDA"].sum()
            for k, v in g.items():
                totales_por_dia[_fecha_formateada_ar(fd)][str(k).upper()] = float(v)

    # ── Cuadro 1: Gastos por línea — Mantenimiento (acumulado del mes) ──
    # Vertical: Filas = Linea, Cols = Total gastado (como en la app local y la imagen del usuario)
    dia_linea = _gastos_dia_por_linea_mantenimiento_mes(store, fecha, dias_mes)
    gl_map: dict[str, float] = {}
    for k in dia_linea:
        for ln, val in dia_linea[k].items():
            gl_map[ln] = gl_map.get(ln, 0.0) + val
    orden_lineas = _orden_lineas_gasto()
    lineas_presentes = sorted(
        [ln for ln in gl_map if gl_map.get(ln, 0.0) > 0],
        key=lambda x: (orden_lineas.index(x) if x in orden_lineas else 999, x),
    )
    mant_lineas_txt: list[str] = []
    orden_sin_mant = [(c, et) for c, et in orden if c != "MANTENIMIENTO"]
    total_sin = sum(float(tot_mes.get(c, 0.0)) for c, _ in orden_sin_mant) if orden_sin_mant else 0.0

    if lineas_presentes or orden_sin_mant:
        hdr_mant = ["Línea / Sector", "Total"]
        rows_mant_html = ""
        mant_lineas_txt.append("Gastos por línea — Mantenimiento (acumulado del mes):")
        for ln in lineas_presentes:
            row_vals = [ln, _formato_pesos_ar(gl_map[ln])]
            rows_mant_html += "<tr>" + "".join(f"<td>{_html.escape(str(v))}</td>" for v in row_vals) + "</tr>"
            mant_lineas_txt.append(" | ".join(str(v) for v in row_vals))
        # Unificar: a continuación de L7 anexar Edilicio / Proyectos / Producción / Autoelevadores y TOTAL real
        if orden_sin_mant:
            if lineas_presentes:
                mant_lineas_txt.append("")
            mant_lineas_txt.append("Totales por sector (sin Mantenimiento):")
            for c, et in orden_sin_mant:
                v = float(tot_mes.get(c, 0.0))
                row_vals = [et, _formato_pesos_ar(v)]
                rows_mant_html += "<tr>" + "".join(f"<td>{_html.escape(str(x))}</td>" for x in row_vals) + "</tr>"
                mant_lineas_txt.append(f"{et} | {_formato_pesos_ar(v)}")
        # TOTAL real del cuadro unificado (líneas + sectores)
        total_cuadro = (sum(float(v) for v in gl_map.values()) if lineas_presentes else 0.0) + total_sin
        rows_mant_html += "<tr>" + "".join(f"<td><b>{_html.escape(str(x))}</b></td>" for x in ["TOTAL", _formato_pesos_ar(total_cuadro)]) + "</tr>"
        mant_lineas_txt.append(f"TOTAL | {_formato_pesos_ar(total_cuadro)}")
        tabla_mant_linea_html = (
            f'<div style="max-width:380px; background:#ffffff; border:1px solid #e2e8f0; border-radius:8px; padding:12px 12px 14px 12px; margin:18px 0;">'
            f'<p style="font-size:13px; font-weight:700; color:#1a365d; margin:0 0 8px 0;">'
            f'Gastos por línea — Mantenimiento (acumulado del mes)</p>'
            f'<div class="table-wrap" style="max-width:none; margin:0;"><table><thead><tr>{"".join(f"<th>{_html.escape(h)}</th>" for h in hdr_mant)}</tr></thead>'
            f'<tbody>{rows_mant_html}</tbody></table></div>'
            f'</div>'
        )
    else:
        tabla_mant_linea_html = '<p style="font-size:13px; color:#718096; margin:18px 0 8px 0;">Sin movimientos en el mes</p>'

    # ── Cuadro 2: Resumen día a día (todos los sectores) — ancho completo como estaba ──
    if orden:
        hdr = ["Fecha"] + [et for _, et in orden] + ["Total día"]
        rows_html = ""
        mant_dia_a_dia_txt: list[str] = ["Día a día (todos los sectores):"]
        for fd in dias_mes:
            k = _fecha_formateada_ar(fd)
            vals = totales_por_dia.get(k, {})
            td = sum(vals.get(code, 0.0) for code, _ in orden)
            row_vals = [k] + [_formato_pesos_ar(vals.get(code, 0.0)) for code, _ in orden] + [_formato_pesos_ar(td)]
            rows_html += "<tr>" + "".join(f"<td>{_html.escape(str(v))}</td>" for v in row_vals) + "</tr>"
            mant_dia_a_dia_txt.append(" | ".join(str(v) for v in row_vals))
        tabla_resumen_html = f"""
        <p style="font-size:13px; font-weight:700; color:#1a365d; margin:18px 0 8px 0;">Resumen día a día — {fecha.strftime('%m/%Y')}</p>
        <div class="table-wrap"><table><thead><tr>{"".join(f"<th>{_html.escape(h)}</th>" for h in hdr)}</tr></thead><tbody>{rows_html}</tbody></table></div>
        """
    else:
        tabla_resumen_html = ""
        mant_dia_a_dia_txt = []

    tabla_detalle = ""

    # ── Reordenar lineas_txt: Mant línea por línea, luego Día a día, luego detalle por sector ──
    lineas_txt = (
        lineas_txt[:3]  # header lines
        + mant_lineas_txt
        + mant_dia_a_dia_txt
        + sector_lineas_txt
    )

    tpl_path = _Path(__file__).resolve().parent / "templates" / "mail_diario_moderno.html"
    try:
        tpl = tpl_path.read_text(encoding="utf-8")
    except Exception:
        tpl = "<html><body><h1>Reporte {{FECHA_ISO}}</h1>{{BLOQUES_SECTOR}}</body></html>"

    html_out = tpl.replace("{{FECHA_ISO}}", fecha.isoformat())
    html_out = html_out.replace("{{FECHA_FORMATEADA}}", _fecha_formateada_ar(fecha))
    html_out = html_out.replace("{{FILAS}}", str(filas))
    html_out = html_out.replace("{{MONTO_TOTAL}}", _formato_pesos_ar(monto_dia))
    html_out = html_out.replace("{{ACUMULADO_MES}}", _formato_pesos_ar(acum_mes))
    sectores_resumen = ", ".join(f"{et}: {_formato_pesos_ar(tot_dia.get(code,0.0))}" for code, et in orden) if orden else "(sin sectores)"
    html_out = html_out.replace("{{SECTORES_RESUMEN}}", _html.escape(sectores_resumen))
    html_out = html_out.replace("{{TABLA_MANT_LINEA_DIA_A_DIA}}", tabla_mant_linea_html)
    html_out = html_out.replace("{{TABLA_RESUMEN_DIA_A_DIA}}", tabla_resumen_html)
    html_out = html_out.replace("{{BLOQUES_SECTOR}}", bloques_html)
    html_out = html_out.replace("{{TABLA_DETALLE}}", tabla_detalle)
    html_out = html_out.replace("{{TIMESTAMP}}", pd.Timestamp.now().strftime("%d/%m/%Y %H:%M"))
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


# ── Mensual moderno — mismo diseño que diario pero agregado mensual ────────

_MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
    7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}


def _mes_formateado_es(year: int, month: int) -> str:
    return f"{_MESES_ES.get(month, str(month))} {year}"


def _bloque_sector_html_mensual(code: str, etiqueta: str, df_sector: pd.DataFrame, total_mes: float, filas_mes: int) -> str:
    est = ESTILO_SECTOR_HTML.get(code, {"bg": "#F8F9F9", "border": "#BDC3C7", "title": "#2C3E50", "th": "#5D6D7E"})
    esc = _html.escape
    detalle_cols = ["FECHA", "CODIGO", "DESCRIPCION", "CANTIDAD", "PRECIO_UNITARIO", "MONTO_TOTAL_SALIDA", "TIPO_COMPROBANTE", "NUMERO_ORDEN", "MAQUINA_SITIO", "OPERARIO"]
    cab = [c.replace("_", " ") for c in detalle_cols]
    th_class = code.lower()
    header_html = "".join(f'<th class="{th_class}">{esc(h)}</th>' for h in cab)
    filas_html = ""
    # Para mensual no mostramos detalle por defecto (sería gigante). Mostramos resumen y tabla día a día ya cubre.
    # Si hay pocas filas (<50) mostramos detalle; si no, solo mensaje con link al Excel.
    if df_sector is not None and not df_sector.empty and len(df_sector) <= 50:
        df_s = df_sector.sort_values("_fecha")
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
                    # FECHA formateada
                    if c == "FECHA":
                        try:
                            v = str(v)[:10]
                        except Exception:
                            pass
                    celdas.append(f"<td>{esc(str(v) if pd.notna(v) else '')}</td>")
            filas_html += f"<tr>{''.join(celdas)}</tr>"
        detalle_html = f"""
        <div class="table-wrap">
          <table>
            <thead><tr>{header_html}</tr></thead>
            <tbody>{filas_html}</tbody>
          </table>
        </div>
        """
    elif df_sector is not None and not df_sector.empty:
        detalle_html = f'<p style="font-size:12px;color:#4a5568;margin:8px 0;">{len(df_sector)} movimientos en el mes — detalle completo en el Excel adjunto.</p>'
    else:
        detalle_html = f'<p style="font-size:12px;color:#718096;margin:8px 0;">Sin movimientos para este sector en el mes.</p>'

    bloque = f"""
    <div class="sector-block {th_class}">
      <p class="sector-title {th_class}">{esc(etiqueta)}</p>
      <p class="sector-meta">Total del mes: <b>{esc(_formato_pesos_ar(total_mes))}</b> &nbsp;•&nbsp; Movimientos: <b>{filas_mes}</b></p>
    </div>
    {detalle_html}
    """
    return bloque


def armar_cuerpo_mensual_moderno(year: int, month: int, df_mes: pd.DataFrame | None = None) -> tuple[str, str]:
    """Genera cuerpo TXT + HTML mensual moderno (template mail_mensual_moderno.html).

    Agregado completo del mes, con misma estética que el diario moderno.
    Si df_mes es None, lo carga desde ReportesStore filtrando el mes completo.
    No envía mail.
    """
    store = ReportesStore.get()
    store.require_loaded()

    desde = date(year, month, 1)
    if month == 12:
        hasta = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        hasta = date(year, month + 1, 1) - timedelta(days=1)
    # Si es mes en curso, cortar a hoy
    hoy = date.today()
    if year == hoy.year and month == hoy.month:
        hasta = min(hasta, hoy)

    if df_mes is None:
        df_mes = _filtrar_por_fecha(store.df, desde, hasta)

    filas = int(len(df_mes))
    monto_total_mes = float(pd.to_numeric(df_mes.get("MONTO_TOTAL_SALIDA", 0), errors="coerce").fillna(0).sum()) if filas else 0.0

    # Dias con movimiento y promedio
    dias_con_mov = 0
    promedio_dia = 0.0
    if filas and "_fecha" in df_mes.columns:
        try:
            dias_con_mov = int(df_mes["_fecha"].dt.normalize().nunique())
        except Exception:
            dias_con_mov = len(set(str(x)[:10] for x in df_mes.get("FECHA", [])))
        if dias_con_mov:
            promedio_dia = monto_total_mes / dias_con_mov

    # Sectores presentes en el mes
    presentes: set[str] = set()
    if not df_mes.empty and "SECTOR" in df_mes.columns:
        presentes.update(str(s).strip().upper() for s in df_mes["SECTOR"].dropna().unique())
    orden: list[tuple[str, str]] = []
    vistos: set[str] = set()
    for code, et in ORDEN_SECTORES_GASTOS:
        if code in presentes:
            orden.append((code, et))
            vistos.add(code)
    extras = sorted(c for c in presentes if c not in vistos)
    for c in extras:
        orden.append((c, c.replace("_", " ").title()))

    tot_mes: dict[str, float] = {}
    filas_por_sector: dict[str, int] = {}
    if not df_mes.empty and "SECTOR" in df_mes.columns:
        g_m = df_mes.groupby("SECTOR")["MONTO_TOTAL_SALIDA"].sum()
        for k, v in g_m.items():
            tot_mes[str(k).upper()] = float(v)
        g_c = df_mes.groupby("SECTOR").size()
        for k, v in g_c.items():
            filas_por_sector[str(k).upper()] = int(v)

    # Dias del mes y totales por dia (para Resumen dia a dia y Mant por dia)
    dias_mes: list[date] = []
    d = desde
    while d <= hasta:
        dias_mes.append(d)
        d += timedelta(days=1)

    totales_por_dia: dict[str, dict[str, float]] = {}
    for fd in dias_mes:
        df_fd = _filtrar_por_fecha(store.df, fd, fd)
        totales_por_dia[_fecha_formateada_ar(fd)] = {}
        if not df_fd.empty and "SECTOR" in df_fd.columns:
            g = df_fd.groupby("SECTOR")["MONTO_TOTAL_SALIDA"].sum()
            for k, v in g.items():
                totales_por_dia[_fecha_formateada_ar(fd)][str(k).upper()] = float(v)

    # Mantenimiento por dia y linea/panol
    dia_linea = _gastos_dia_por_linea_mantenimiento_mes(store, hasta, dias_mes)
    gl_map: dict[str, float] = {}
    for k in dia_linea:
        for ln, val in dia_linea[k].items():
            gl_map[ln] = gl_map.get(ln, 0.0) + val
    orden_lineas = _orden_lineas_gasto()
    lineas_presentes = sorted(
        [ln for ln in gl_map if gl_map.get(ln, 0.0) > 0],
        key=lambda x: (orden_lineas.index(x) if x in orden_lineas else 999, x),
    )
    # Asegurar orden fijo PAÑOL + L1..L7 si existen, incluso si alguno dio 0 pero tiene total global
    # lineas_presentes ya cubre solo >0 global, que es lo que muestra Image 2

    # ── Cabecera bloques colores por sector (Image 1) — arriba de todo ──
    # Header total + 5 bloques numerados con colores por sector
    mes_et = _mes_formateado_es(year, month)  # Ej: Septiembre 2026
    periodo_num = f"{month:02d}/{year}"
    total_mes_fmt = _formato_pesos_ar(monto_total_mes)
    bloques_colores_html = ""
    bloques_colores_html += f'<p style="font-family:Arial,sans-serif;font-size:15px;font-weight:700;color:#111;margin:6px 0 14px 0;">Total gastado en el mes {periodo_num}: {total_mes_fmt}</p>'
    for idx, (code, et) in enumerate(orden, start=1):
        est = ESTILO_SECTOR_HTML.get(code, {"bg": "#F8F9F9", "border": "#BDC3C7", "title": "#2C3E50"})
        total_sec = _formato_pesos_ar(float(tot_mes.get(code, 0.0)))
        bloques_colores_html += (
            f'<div style="font-family:Arial,sans-serif;margin:8px 0;padding:10px 14px;'
            f'background:{est["bg"]};border-left:5px solid {est["border"]};border-radius:4px;">'
            f'<p style="margin:0;font-size:14px;color:{est["title"]};"><b>{idx}. { _html.escape(et)}</b></p>'
            f'<p style="margin:4px 0 0 0;font-size:13px;color:#333;">'
            f'Gasto total del mes: <b>{total_sec}</b></p></div>'
        )
    # Autoelevadores y variaciones: asegurar que tenga estilo aunque no esté en mapa
    # Si no hubo movimientos, mostrar mensaje en cabecera
    if not orden:
        bloques_colores_html += '<p style="font-size:13px;color:#718096;">Sin movimientos en el mes.</p>'
    cabecera_bloques_html = f'<div style="margin:8px 0 16px 0;">{bloques_colores_html}</div>'

    # ── Cuadro A: Resumen día a día — (por sector + Total día) ── KEEP
    if orden:
        hdr = ["Fecha"] + [et for _, et in orden] + ["Total día"]
        rows_html = ""
        for fd in dias_mes:
            k = _fecha_formateada_ar(fd)
            vals = totales_por_dia.get(k, {})
            td = sum(vals.get(code, 0.0) for code, _ in orden)
            if td == 0:
                continue
            row_vals = [k] + [_formato_pesos_ar(vals.get(code, 0.0)) for code, _ in orden] + [_formato_pesos_ar(td)]
            rows_html += "<tr>" + "".join(f"<td>{_html.escape(str(v))}</td>" for v in row_vals) + "</tr>"
        row_total = ["TOTAL MES"] + [_formato_pesos_ar(tot_mes.get(code, 0.0)) for code, _ in orden] + [_formato_pesos_ar(monto_total_mes)]
        rows_html += "<tr>" + "".join(f"<td><b>{_html.escape(str(v))}</b></td>" for v in row_total) + "</tr>"
        tabla_resumen_html = f"""
        <p style="font-size:13px; font-weight:700; color:#1a365d; margin:18px 0 8px 0;">Resumen día a día — {_mes_formateado_es(year, month)}</p>
        <div class="table-wrap"><table><thead><tr>{"".join(f"<th>{_html.escape(h)}</th>" for h in hdr)}</tr></thead><tbody>{rows_html}</tbody></table></div>
        """
    else:
        tabla_resumen_html = ""

    # ── Cuadro B: Mantenimiento gasto por día y línea/paño (mes) — Image 1 ──
    if lineas_presentes:
        hdr_mant_dia = ["Fecha"] + lineas_presentes + ["Total día"]
        rows_mant_dia = ""
        for fd in dias_mes:
            k = _fecha_formateada_ar(fd)
            dl = dia_linea.get(k, {})
            tot_dia_mant = sum(float(dl.get(ln, 0.0)) for ln in lineas_presentes)
            if tot_dia_mant == 0:
                continue
            row_vals = [k] + [_formato_pesos_ar(dl.get(ln, 0.0)) for ln in lineas_presentes] + [_formato_pesos_ar(tot_dia_mant)]
            rows_mant_dia += "<tr>" + "".join(f"<td>{_html.escape(str(v))}</td>" for v in row_vals) + "</tr>"
        # TOTAL MES fila
        total_mant = sum(float(v) for v in gl_map.values())
        row_total_mant = ["TOTAL MES"] + [_formato_pesos_ar(gl_map.get(ln, 0.0)) for ln in lineas_presentes] + [_formato_pesos_ar(total_mant)]
        rows_mant_dia += "<tr>" + "".join(f"<td><b>{_html.escape(str(v))}</b></td>" for v in row_total_mant) + "</tr>"
        tabla_mant_dia_linea_html = f"""
        <p style="font-size:13px; font-weight:700; color:#1a365d; margin:18px 0 8px 0;">Mantenimiento: gasto por día y línea/paño (mes)</p>
        <div class="table-wrap"><table><thead><tr>{"".join(f'<th class="mantenimiento">{_html.escape(h)}</th>' for h in hdr_mant_dia)}</tr></thead><tbody>{rows_mant_dia}</tbody></table></div>
        """
    else:
        tabla_mant_dia_linea_html = '<p style="font-size:13px; color:#718096; margin:18px 0 8px 0;">Sin movimientos de Mantenimiento en el mes</p>'

    # ── Cuadro C: Gasto por sector (mes) — Image 2 top (separado) ──
    if orden:
        hdr_sec = ["Sector", "Total mes"]
        rows_sec = ""
        for code, et in orden:
            v = float(tot_mes.get(code, 0.0))
            rows_sec += "<tr>" + "".join(f"<td>{_html.escape(str(x))}</td>" for x in [et, _formato_pesos_ar(v)]) + "</tr>"
        rows_sec += "<tr>" + "".join(f"<td><b>{_html.escape(str(x))}</b></td>" for x in ["TOTAL", _formato_pesos_ar(monto_total_mes)]) + "</tr>"
        tabla_sector_mes_html = (
            f'<div style="max-width:380px; background:#ffffff; border:1px solid #e2e8f0; border-radius:8px; padding:12px 12px 14px 12px; margin:18px 0;">'
            f'<p style="font-size:13px; font-weight:700; color:#1a365d; margin:0 0 8px 0;">Gasto por sector (mes)</p>'
            f'<div class="table-wrap" style="max-width:none; margin:0;"><table><thead><tr>{"".join(f"<th>{_html.escape(h)}</th>" for h in hdr_sec)}</tr></thead>'
            f'<tbody>{rows_sec}</tbody></table></div>'
            f'</div>'
        )
    else:
        tabla_sector_mes_html = '<p style="font-size:13px; color:#718096; margin:18px 0 8px 0;">Sin movimientos en el mes</p>'

    # ── Cuadro D: Desglose de Mantenimiento por línea y paño (mes) — Image 2 bottom ──
    if lineas_presentes:
        hdr_des = ["Línea / Paño", "Total mes"]
        rows_des = ""
        for ln in lineas_presentes:
            rows_des += "<tr>" + "".join(f"<td>{_html.escape(str(v))}</td>" for v in [ln, _formato_pesos_ar(gl_map[ln])]) + "</tr>"
        total_mant2 = sum(float(v) for v in gl_map.values())
        rows_des += "<tr>" + "".join(f"<td><b>{_html.escape(str(x))}</b></td>" for x in ["TOTAL MANTENIMIENTO", _formato_pesos_ar(total_mant2)]) + "</tr>"
        tabla_desglose_mant_html = (
            f'<div style="max-width:380px; background:#ffffff; border:1px solid #e2e8f0; border-radius:8px; padding:12px 12px 14px 12px; margin:18px 0;">'
            f'<p style="font-size:13px; font-weight:700; color:#1a365d; margin:0 0 8px 0;">Desglose de Mantenimiento por línea y paño (mes)</p>'
            f'<div class="table-wrap" style="max-width:none; margin:0;"><table><thead><tr>{"".join(f"<th>{_html.escape(h)}</th>" for h in hdr_des)}</tr></thead>'
            f'<tbody>{rows_des}</tbody></table></div>'
            f'</div>'
        )
    else:
        tabla_desglose_mant_html = '<p style="font-size:13px; color:#718096; margin:18px 0 8px 0;">Sin desglose de Mantenimiento en el mes</p>'

    # ── Resumen por día por sector con color de ese sector — abajo de todo ──
    resumen_por_sector_abajo_html = ""
    if orden:
        for code, et in orden:
            th_class = code.lower()
            # No incluir autoelevadores si no tiene datos? ya está filtrado
            # Calcular acumulado por sector
            hdr_sec_dia = ["Fecha", "Gasto del día", "Acumulado"]
            rows_sec_dia = ""
            acum = 0.0
            has_rows = False
            for fd in dias_mes:
                k = _fecha_formateada_ar(fd)
                g = float(totales_por_dia.get(k, {}).get(code, 0.0))
                if g == 0:
                    continue
                has_rows = True
                acum += g
                rows_sec_dia += "<tr>" + "".join(f"<td>{_html.escape(str(v))}</td>" for v in [k, _formato_pesos_ar(g), _formato_pesos_ar(acum)]) + "</tr>"
            if not has_rows:
                # Si no hubo movimiento para ese sector, mostrar mensaje en color del sector
                resumen_por_sector_abajo_html += f"""
                <p style="font-size:13px; font-weight:700; color:#1a365d; margin:18px 0 8px 0;"><span style="display:inline-block;width:12px;height:12px;background:{ESTILO_SECTOR_HTML.get(code, {'bg':'#ccc'})['border']};border-radius:2px;margin-right:6px;vertical-align:middle;"></span>Resumen día a día — { _html.escape(et)}</p>
                <p style="font-size:12px;color:#718096;margin:0 0 12px 0;">Sin movimientos para { _html.escape(et)} en el mes.</p>
                """
                continue
            # Total mes para ese sector
            total_sec = float(tot_mes.get(code, 0.0))
            rows_sec_dia += "<tr>" + "".join(f"<td><b>{_html.escape(str(v))}</b></td>" for v in ["TOTAL MES", _formato_pesos_ar(total_sec), _formato_pesos_ar(total_sec)]) + "</tr>"
            th_html = "".join(f'<th class="{th_class}">{_html.escape(h)}</th>' for h in hdr_sec_dia)
            resumen_por_sector_abajo_html += f"""
            <p style="font-size:13px; font-weight:700; color:#1a365d; margin:18px 0 8px 0;"><span style="display:inline-block;width:12px;height:12px;background:{ESTILO_SECTOR_HTML.get(code, {'border':'#1a365d'})['border']};border-radius:2px;margin-right:6px;vertical-align:middle;"></span>Resumen día a día — { _html.escape(et)}</p>
            <div class="table-wrap"><table><thead><tr>{th_html}</tr></thead><tbody>{rows_sec_dia}</tbody></table></div>
            """
        # Envolver en contenedor si hay contenido
        if resumen_por_sector_abajo_html:
            resumen_por_sector_abajo_html = f'<div style="margin-top:22px; border-top:2px solid #e2e8f0; padding-top:12px;">{resumen_por_sector_abajo_html}</div>'

    # TXT (sin bloques por sector, con nuevos cuadros)
    mes_fmt = _mes_formateado_es(year, month)
    periodo_iso = f"{year}-{month:02d}"
    lineas_txt: list[str] = [
        f"Reporte mensual de gastos por sector — {mes_fmt} ({periodo_iso})",
        f"Movimientos: {filas} | Total mes: {_formato_pesos_ar(monto_total_mes)} | Promedio diario: {_formato_pesos_ar(promedio_dia)} ({dias_con_mov} días)",
        "",
        "Totales por sector:",
    ] + [f"  {et}: {_formato_pesos_ar(tot_mes.get(code,0.0))} ({filas_por_sector.get(code,0)} mov.)" for code, et in orden] + [""]

    if lineas_presentes:
        lineas_txt.append("Desglose Mantenimiento por línea/paño:")
        for ln in lineas_presentes:
            lineas_txt.append(f"  {ln}: {_formato_pesos_ar(gl_map[ln])}")
        lineas_txt.append(f"  TOTAL MANTENIMIENTO: {_formato_pesos_ar(sum(float(v) for v in gl_map.values()))}")
        lineas_txt.append("")

    # Cargar template mensual moderno
    tpl_path = _Path(__file__).resolve().parent / "templates" / "mail_mensual_moderno.html"
    try:
        tpl = tpl_path.read_text(encoding="utf-8")
    except Exception:
        tpl = "<html><body><h1>Reporte {{MES_FORMATEADO}} {{PERIODO_ISO}}</h1>{{TABLA_RESUMEN_DIA_A_DIA}}</body></html>"

    html_out = tpl.replace("{{MES_FORMATEADO}}", _html.escape(mes_fmt))
    html_out = html_out.replace("{{PERIODO_ISO}}", _html.escape(periodo_iso))
    html_out = html_out.replace("{{FILAS}}", str(filas))
    html_out = html_out.replace("{{MONTO_TOTAL_MES}}", _formato_pesos_ar(monto_total_mes))
    html_out = html_out.replace("{{PROMEDIO_DIA}}", _formato_pesos_ar(promedio_dia))
    html_out = html_out.replace("{{DIAS_CON_MOVIMIENTO}}", str(dias_con_mov))
    sectores_resumen = ", ".join(f"{et}: {_formato_pesos_ar(tot_mes.get(code,0.0))}" for code, et in orden) if orden else "(sin sectores)"
    html_out = html_out.replace("{{SECTORES_RESUMEN}}", _html.escape(sectores_resumen))
    html_out = html_out.replace("{{CABECERA_BLOQUES}}", cabecera_bloques_html)
    html_out = html_out.replace("{{TABLA_RESUMEN_DIA_A_DIA}}", tabla_resumen_html)
    html_out = html_out.replace("{{TABLA_MANT_DIA_LINEA}}", tabla_mant_dia_linea_html)
    html_out = html_out.replace("{{TABLA_SECTOR_MES}}", tabla_sector_mes_html)
    html_out = html_out.replace("{{TABLA_DESGLOSE_MANT}}", tabla_desglose_mant_html)
    html_out = html_out.replace("{{RESUMEN_POR_SECTOR_ABAJO}}", resumen_por_sector_abajo_html)
    # compat: viejos placeholders vacíos
    html_out = html_out.replace("{{TABLA_MANT_LINEA_MES}}", "")
    html_out = html_out.replace("{{BLOQUES_SECTOR}}", "")
    html_out = html_out.replace("{{TABLA_MANT_LINEA_DIA_A_DIA}}", "")
    html_out = html_out.replace("{{BLOQUES_SECTOR}}", "")
    html_out = html_out.replace("{{TIMESTAMP}}", pd.Timestamp.now().strftime("%d/%m/%Y %H:%M"))
    html_out = html_out.replace("{{", "").replace("}}", "")

    # TXT sin bloques de movimientos
    txt = "\n".join(lineas_txt)
    return txt, html_out


def preview_mensual_moderno(year: int | None = None, month: int | None = None, *, destinatarios: list[str] | None = None) -> dict[str, Any]:
    """Genera preview mensual moderno sin enviar.

    Si no se pasa year/month, usa mes anterior a hoy (ej: 2026-10-01 => 2026-09).
    Retorna dict con html, txt, métricas y estado de mail (sin enviar).
    """
    hoy = date.today()
    if year is None or month is None:
        # mes anterior
        if hoy.month == 1:
            year = hoy.year - 1
            month = 12
        else:
            year = hoy.year
            month = hoy.month - 1
        # Si hoy es 1 y piden sin args, igual va al mes anterior (septiembre)
        # Si estamos en octubre, preview es septiembre
    if year is None:
        year = hoy.year
    if month is None:
        month = hoy.month

    store = ReportesStore.get()
    try:
        store.require_loaded()
    except CargandoDatosError:
        store.refresh()
        store.require_loaded()

    desde = date(year, month, 1)
    if month == 12:
        hasta = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        hasta = date(year, month + 1, 1) - timedelta(days=1)
    if year == hoy.year and month == hoy.month:
        hasta = min(hasta, hoy)

    df_mes = _filtrar_por_fecha(store.df, desde, hasta)
    txt, html_mod = armar_cuerpo_mensual_moderno(year, month, df_mes)
    try:
        xlsx = armar_excel_mensual_con_grafico(store, year, month)
    except Exception:
        xlsx = armar_excel_periodo(store, desde, hasta)
    preview_dest = destinatarios or ["franco.sanabria@pilaresca.com.ar"]
    mes_fmt = _mes_formateado_es(year, month)
    periodo_iso = f"{year}-{month:02d}"
    return {
        "enviado": False,
        "preview": True,
        "diseño": "moderno-mensual",
        "year": year,
        "month": month,
        "periodo": periodo_iso,
        "mes_formateado": mes_fmt,
        "desde": desde.isoformat(),
        "hasta": hasta.isoformat(),
        "filas": int(len(df_mes)),
        "xlsx_bytes": len(xlsx),
        "asunto": f"Reporte Mensual de Gastos por Sector ({mes_fmt} — {periodo_iso}) — PREVIEW MODERNO",
        "destinatario_preview": preview_dest,
        "cuerpo_txt_preview": txt[:2500],
        "cuerpo_html_len": len(html_mod),
        "cuerpo_html_preview": html_mod[:6000],
        "cuerpo_html_completo": html_mod,
        "nota": "PREVIEW ONLY — no se envió mail. Flags siguen en 0. Enviar solo a franco.sanabria@pilaresca.com.ar cuando el usuario apruebe el diseño.",
        **mail_status(),
    }


def dry_run_mensual_moderno(year: int | None = None, month: int | None = None) -> dict[str, Any]:
    """Alias de preview mensual moderno."""
    return preview_mensual_moderno(year, month)
