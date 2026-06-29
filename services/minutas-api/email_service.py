# -*- coding: utf-8 -*-
"""Generación y envío de minutas por correo (SMTP)."""

from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape
from typing import Optional

from models import SesionDetalle, Solicitud, Tema, Urgencia

URGencia_LABEL = {
    Urgencia.BAJA: "Baja",
    Urgencia.MEDIA: "Media",
    Urgencia.ALTA: "Alta",
    Urgencia.CRITICA: "Crítica",
}


class EmailNoConfigurado(Exception):
    pass


def _smtp_configurado() -> bool:
    return bool(
        os.environ.get("MINUTAS_SMTP_HOST")
        and os.environ.get("MINUTAS_SMTP_FROM")
    )


def _default_destinatarios() -> list[str]:
    raw = os.environ.get("MINUTAS_EMAIL_DEFAULT_TO", "")
    return [e.strip() for e in raw.split(",") if e.strip()]


def construir_asunto(sesion: SesionDetalle, personalizado: Optional[str] = None) -> str:
    if personalizado:
        return personalizado
    return f"Minuta semanal Compras — {sesion.semana_iso} ({sesion.fecha})"


def _bloque_solicitud_texto(s: Solicitud) -> str:
    lineas = [
        f"• Ref. {s.numero_referencia} | {s.solicitante} | Urgencia: {URGencia_LABEL[s.urgencia]}",
        f"  Ítems: {s.cantidad_items} | Entrega: {s.estado_entrega.value}",
    ]
    if s.descripcion:
        lineas.append(f"  Descripción: {s.descripcion}")
    if s.entregas:
        lineas.append("  Entregas parciales:")
        for e in s.entregas:
            obs = f" — {e.observacion}" if e.observacion else ""
            lineas.append(f"    - {e.fecha}: {e.cantidad} u.{obs}")
    if s.actualizaciones:
        lineas.append("  Actualizaciones de hoy:")
        for a in s.actualizaciones:
            autor = f" ({a.autor})" if a.autor else ""
            lineas.append(f"    -{autor} {a.texto}")
    return "\n".join(lineas)


def _bloque_tema_texto(t: Tema) -> str:
    estado = "Resuelto" if t.resuelto else "Pendiente"
    desc = f"\n  {t.descripcion}" if t.descripcion else ""
    return f"• [{estado}] {t.titulo}{desc}"


def construir_cuerpo_texto(sesion: SesionDetalle) -> str:
    partes = [
        "MINUTA DE REUNIÓN — ACTUALIZACIÓN COMPRAS",
        f"Semana: {sesion.semana_iso}",
        f"Fecha: {sesion.fecha}",
    ]
    if sesion.responsable:
        partes.append(f"Responsable: {sesion.responsable}")
    partes.append("")

    if sesion.solicitudes:
        partes.append("=== SOLICITUDES A COMPRAS ===")
        for s in sesion.solicitudes:
            partes.append(_bloque_solicitud_texto(s))
            partes.append("")
    else:
        partes.append("(Sin solicitudes registradas en esta reunión)")
        partes.append("")

    if sesion.temas:
        partes.append("=== OTROS TEMAS ===")
        for t in sesion.temas:
            partes.append(_bloque_tema_texto(t))
        partes.append("")

    if sesion.notas_generales:
        partes.append("=== NOTAS GENERALES ===")
        partes.append(sesion.notas_generales)
        partes.append("")

    partes.append("— Enviado desde SistemasPañol / Módulo Minutas")
    return "\n".join(partes)


def construir_cuerpo_html(sesion: SesionDetalle) -> str:
    def fila_solicitud(s: Solicitud) -> str:
        entregas = "".join(
            f"<li>{escape(e.fecha)}: <strong>{e.cantidad}</strong> u."
            f"{(' — ' + escape(e.observacion)) if e.observacion else ''}</li>"
            for e in s.entregas
        )
        acts = "".join(
            f"<li><em>{escape(a.autor or 'Anónimo')}</em>: {escape(a.texto)}</li>"
            for a in s.actualizaciones
        )
        return f"""
        <div style="margin-bottom:16px;padding:12px;border:1px solid #e2e8f0;border-radius:8px;">
          <strong>Ref. {escape(s.numero_referencia)}</strong> —
          {escape(s.solicitante)} —
          <span style="color:#b45309;">{URGencia_LABEL[s.urgencia]}</span><br/>
          Ítems: {s.cantidad_items} | Estado: <strong>{s.estado_entrega.value}</strong>
          {f'<br/>{escape(s.descripcion)}' if s.descripcion else ''}
          {f'<ul>{entregas}</ul>' if entregas else ''}
          {f'<p>Actualizaciones:</p><ul>{acts}</ul>' if acts else ''}
        </div>"""

    temas = "".join(
        f"<li><strong>{'✓' if t.resuelto else '○'} {escape(t.titulo)}</strong>"
        f"{('<br/><span style=\"color:#64748b\">' + escape(t.descripcion) + '</span>') if t.descripcion else ''}</li>"
        for t in sesion.temas
    )

    return f"""
    <html><body style="font-family:Segoe UI,sans-serif;color:#0f172a;max-width:720px;">
      <h2 style="color:#1e40af;">Minuta — Actualización Compras</h2>
      <p><strong>Semana:</strong> {escape(sesion.semana_iso)} &nbsp;|&nbsp;
         <strong>Fecha:</strong> {escape(sesion.fecha)}</p>
      {f'<p><strong>Responsable:</strong> {escape(sesion.responsable)}</p>' if sesion.responsable else ''}
      <h3>Solicitudes</h3>
      {''.join(fila_solicitud(s) for s in sesion.solicitudes) or '<p><em>Sin solicitudes.</em></p>'}
      {f'<h3>Otros temas</h3><ul>{temas}</ul>' if temas else ''}
      {f'<h3>Notas generales</h3><p>{escape(sesion.notas_generales)}</p>' if sesion.notas_generales else ''}
      <hr/><p style="font-size:12px;color:#64748b;">SistemasPañol — Módulo Minutas</p>
    </body></html>"""


def enviar_minuta(
    destinatarios: list[str],
    asunto: str,
    cuerpo_texto: str,
    cuerpo_html: str,
) -> None:
    if not _smtp_configurado():
        raise EmailNoConfigurado(
            "SMTP no configurado. Definí MINUTAS_SMTP_HOST y MINUTAS_SMTP_FROM."
        )

    host = os.environ["MINUTAS_SMTP_HOST"]
    port = int(os.environ.get("MINUTAS_SMTP_PORT", "587"))
    user = os.environ.get("MINUTAS_SMTP_USER")
    password = os.environ.get("MINUTAS_SMTP_PASSWORD")
    from_addr = os.environ["MINUTAS_SMTP_FROM"]
    use_tls = os.environ.get("MINUTAS_SMTP_TLS", "true").lower() != "false"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = asunto
    msg["From"] = from_addr
    msg["To"] = ", ".join(destinatarios)
    msg.attach(MIMEText(cuerpo_texto, "plain", "utf-8"))
    msg.attach(MIMEText(cuerpo_html, "html", "utf-8"))

    with smtplib.SMTP(host, port, timeout=30) as smtp:
        if use_tls:
            smtp.starttls()
        if user and password:
            smtp.login(user, password)
        smtp.sendmail(from_addr, destinatarios, msg.as_string())


def destinatarios_default_o(provistos: list[str]) -> list[str]:
    if provistos:
        return provistos
    defaults = _default_destinatarios()
    if not defaults:
        raise ValueError("Indicá al menos un destinatario o configurá MINUTAS_EMAIL_DEFAULT_TO.")
    return defaults
