# -*- coding: utf-8 -*-
"""Servicio genérico de correo — Sistemas Pañol (Starlette, sin pydantic)."""

from __future__ import annotations

import json
import os
import smtplib
import traceback
from pathlib import Path

from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from contacts_reader import listar_contactos
from mailer import enviar_correo
from smtp_config import SmtpNoConfigurado, obtener_smtp_config


def _cargar_env_local() -> None:
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


_cargar_env_local()


async def health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "email-service"})


async def get_contacts(_: Request) -> JSONResponse:
    try:
        contactos = listar_contactos()
        return JSONResponse({"contactos": [c.to_dict() for c in contactos]})
    except FileNotFoundError as e:
        return JSONResponse({"detail": str(e)}, status_code=503)
    except ValueError as e:
        return JSONResponse({"detail": str(e)}, status_code=503)


async def post_send(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"detail": "JSON inválido."}, status_code=400)

    destinatarios = body.get("destinatarios")
    asunto = (body.get("asunto") or "").strip()
    cuerpo_html = (body.get("cuerpo_html") or "").strip()
    cuerpo_texto = body.get("cuerpo_texto")

    if not isinstance(destinatarios, list) or not destinatarios:
        return JSONResponse({"detail": "destinatarios requerido (lista no vacía)."}, status_code=400)
    if not asunto:
        return JSONResponse({"detail": "asunto requerido."}, status_code=400)
    if not cuerpo_html:
        return JSONResponse({"detail": "cuerpo_html requerido."}, status_code=400)

    try:
        cfg = obtener_smtp_config()
        dest = list(dict.fromkeys(str(d).strip() for d in destinatarios if str(d).strip()))
        enviar_correo(cfg, dest, asunto, cuerpo_html, cuerpo_texto)
    except SmtpNoConfigurado as e:
        return JSONResponse({"detail": str(e)}, status_code=503)
    except ValueError as e:
        return JSONResponse({"detail": str(e)}, status_code=400)
    except smtplib.SMTPException as e:
        traceback.print_exc()
        return JSONResponse({"detail": f"Error SMTP: {e}"}, status_code=502)
    except (OSError, TimeoutError, ConnectionError) as e:
        traceback.print_exc()
        return JSONResponse({"detail": f"Error de conexión SMTP: {e}"}, status_code=502)
    except Exception as e:
        traceback.print_exc()
        return JSONResponse({"detail": f"Error interno: {e}"}, status_code=500)

    return JSONResponse(
        {"ok": True, "mensaje": "Correo enviado correctamente.", "destinatarios": dest}
    )


_origins = os.environ.get("EMAIL_CORS_ORIGINS", "*").strip()
_allow = ["*"] if _origins == "*" else [o.strip() for o in _origins.split(",") if o.strip()]

app = Starlette(
    routes=[
        Route("/health", health, methods=["GET"]),
        Route("/api/email/contacts", get_contacts, methods=["GET"]),
        Route("/api/email/send", post_send, methods=["POST"]),
    ],
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow,
    allow_methods=["*"],
    allow_headers=["*"],
)
