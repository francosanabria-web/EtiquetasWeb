# -*- coding: utf-8 -*-
"""API Solicitud de pedidos — Starlette + SQLite (puerto 8014)."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Route

import db
from config import PORT, UPLOADS_DIR, cargar_catalogos, cors_origins_list
from excel_solicitud import generar_excel
from pdf_solicitud import generar_pdf

db.init_db()


async def health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "solicitudes-pedidos"})


async def get_catalogos(_: Request) -> JSONResponse:
    cats = cargar_catalogos()
    cats.pop("_comentario", None)
    # Sugerencias de proveedor = catálogo + lo que ya se cargó.
    cats["proveedores"] = db.proveedores_sugeridos()
    return JSONResponse(cats)


async def get_resumen(_: Request) -> JSONResponse:
    return JSONResponse(db.resumen())


async def get_listado(request: Request) -> JSONResponse:
    tipo = (request.query_params.get("tipo") or "").strip() or None
    estado = (request.query_params.get("estado") or "").strip() or None
    q = (request.query_params.get("q") or "").strip() or None
    limite = int(request.query_params.get("limite") or "200")
    return JSONResponse({"solicitudes": db.listar(tipo=tipo, estado=estado, q=q, limite=limite)})


async def get_una(request: Request) -> JSONResponse:
    sid = int(request.path_params["id"])
    row = db.obtener(sid)
    if not row:
        return JSONResponse({"detail": "Solicitud no encontrada."}, status_code=404)
    return JSONResponse({"solicitud": row})


async def post_crear(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"detail": "JSON inválido."}, status_code=400)
    rol = str((body or {}).get("rol") or request.query_params.get("rol") or "").strip().lower()
    try:
        row = db.crear(body if isinstance(body, dict) else {}, rol=rol)
        return JSONResponse({"solicitud": row}, status_code=201)
    except ValueError as e:
        return JSONResponse({"detail": str(e)}, status_code=400)


async def patch_actualizar(request: Request) -> JSONResponse:
    sid = int(request.path_params["id"])
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"detail": "JSON inválido."}, status_code=400)
    rol = str((body or {}).get("rol") or request.query_params.get("rol") or "").strip().lower()
    try:
        row = db.actualizar(sid, body if isinstance(body, dict) else {}, rol=rol)
    except ValueError as e:
        return JSONResponse({"detail": str(e)}, status_code=400)
    if not row:
        return JSONResponse({"detail": "Solicitud no encontrada."}, status_code=404)
    return JSONResponse({"solicitud": row})


async def delete_una(request: Request) -> JSONResponse:
    sid = int(request.path_params["id"])
    rol = str(request.query_params.get("rol") or "").strip().lower()
    try:
        ok = db.eliminar(sid, rol=rol)
    except ValueError as e:
        return JSONResponse({"detail": str(e)}, status_code=403)
    if not ok:
        return JSONResponse({"detail": "Solicitud no encontrada."}, status_code=404)
    return JSONResponse({"ok": True})


async def get_pdf(request: Request) -> Response:
    sid = int(request.path_params["id"])
    row = db.obtener(sid)
    if not row:
        return JSONResponse({"detail": "Solicitud no encontrada."}, status_code=404)
    pdf_bytes = generar_pdf(row)
    filename = f"solicitud_{sid}.pdf"
    return Response(
        pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


async def get_excel(request: Request) -> Response:
    sid = int(request.path_params["id"])
    row = db.obtener(sid)
    if not row:
        return JSONResponse({"detail": "Solicitud no encontrada."}, status_code=404)
    data = generar_excel(row)
    filename = f"solicitud_{sid}.xlsx"
    return Response(
        data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _safe_ext(filename: str) -> str:
    ext = Path(filename or "").suffix.lower()
    if ext in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".pdf"):
        return ext
    return ".bin"


async def post_upload(request: Request) -> JSONResponse:
    form = await request.form()
    upload = form.get("file")
    if upload is None or not hasattr(upload, "filename"):
        return JSONResponse({"detail": "Archivo requerido (campo file)."}, status_code=400)
    ext = _safe_ext(str(upload.filename))
    kind = re.sub(r"[^a-z0-9_]+", "", str(form.get("kind") or "archivo").lower()) or "archivo"
    name = f"{kind}_{uuid.uuid4().hex[:12]}{ext}"
    dest = UPLOADS_DIR / name
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    content = await upload.read()
    dest.write_bytes(content)
    return JSONResponse({"path": name, "url": f"/api/solicitudes/archivos/{name}"})


async def get_archivo(request: Request) -> Response:
    name = request.path_params["name"]
    if ".." in name or "/" in name or "\\" in name:
        return JSONResponse({"detail": "Nombre inválido."}, status_code=400)
    path = UPLOADS_DIR / name
    if not path.is_file():
        return JSONResponse({"detail": "Archivo no encontrado."}, status_code=404)
    return FileResponse(path)


app = Starlette(
    routes=[
        Route("/health", health, methods=["GET"]),
        Route("/api/solicitudes/health", health, methods=["GET"]),
        Route("/api/solicitudes/catalogos", get_catalogos, methods=["GET"]),
        Route("/api/solicitudes/resumen", get_resumen, methods=["GET"]),
        Route("/api/solicitudes", get_listado, methods=["GET"]),
        Route("/api/solicitudes", post_crear, methods=["POST"]),
        Route("/api/solicitudes/upload", post_upload, methods=["POST"]),
        Route("/api/solicitudes/archivos/{name}", get_archivo, methods=["GET"]),
        Route("/api/solicitudes/{id:int}", get_una, methods=["GET"]),
        Route("/api/solicitudes/{id:int}", patch_actualizar, methods=["PATCH"]),
        Route("/api/solicitudes/{id:int}", delete_una, methods=["DELETE"]),
        Route("/api/solicitudes/{id:int}/pdf", get_pdf, methods=["GET"]),
        Route("/api/solicitudes/{id:int}/excel", get_excel, methods=["GET"]),
    ],
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins_list(),
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)
