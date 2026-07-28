# -*- coding: utf-8 -*-
"""Envío multipart texto+HTML — patrón almacen_gui.py."""

from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from smtp_config import SmtpConfig


def enviar_correo(
    cfg: SmtpConfig,
    destinatarios: list[str],
    asunto: str,
    cuerpo_html: str,
    cuerpo_texto: str | None = None,
) -> None:
    dest = [d.strip() for d in destinatarios if d.strip()]
    if not dest:
        raise ValueError("Lista de destinatarios vacía.")

    texto = cuerpo_texto or "Minuta de reunión (ver versión HTML)."

    msg = MIMEMultipart("mixed")
    msg["From"] = cfg.from_addr
    msg["To"] = ", ".join(dest)
    msg["Subject"] = asunto

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(texto, "plain", "utf-8"))
    alt.attach(MIMEText(cuerpo_html, "html", "utf-8"))
    msg.attach(alt)

    with smtplib.SMTP(cfg.host, cfg.port, timeout=30) as server:
        server.starttls()
        server.login(cfg.user.strip(), cfg.password.strip())
        server.sendmail(cfg.from_addr, dest, msg.as_string())
