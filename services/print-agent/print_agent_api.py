# -*- coding: utf-8 -*-
"""
print_agent_api.py — Agente de impresión que trabaja contra etiquetas-api.

Reemplaza la versión vieja que escuchaba Firestore (`agente_impresion_etiquetas.py`)
por el nuevo modelo de la app_web_salidas: el agente NO recibe push, sino que
hace *polling* a la API:

    1. GET  {API}/etiquetas/pendientes          -> trae los pedidos a imprimir
    2. (imprime cada etiqueta)
    3. POST {API}/etiquetas/{id}/confirmar       -> informa 'impreso' o 'error'

Así esta PC (la que tiene la impresora USB) sólo necesita salida de red hacia la
API: no expone puertos ni necesita IP fija. La API se encarga de los reintentos y
del descarte tras varios fallos.

Reutiliza el render y la impresión ya escritos en `agente_impresion_etiquetas.py`
(no se reescriben) y agrega el render del modo "simple" (sólo texto libre).

Dependencias: Pillow, qrcode (y pywin32 sólo en la PC real con impresora).
El cliente HTTP usa la librería estándar (urllib), sin dependencias extra.

Uso:
    python print_agent_api.py                 -> loop de polling (producción)
    python print_agent_api.py --una-vez       -> procesa una vuelta y sale (test)
    python print_agent_api.py --api http://192.168.1.50:8000

Variables de entorno:
    ETIQUETAS_API_URL   (default http://127.0.0.1:8000)
    ETIQUETAS_POLL_SEG  (default 3)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

from PIL import Image, ImageDraw

# Reutilizamos TODO lo ya escrito (render del modo código, impresión, fuentes, log).
import agente_impresion_etiquetas as agente

# ======================= CONFIGURACIÓN =======================
API_URL_DEFAULT = os.environ.get("ETIQUETAS_API_URL", "http://127.0.0.1:8000")
POLL_SEG_DEFAULT = float(os.environ.get("ETIQUETAS_POLL_SEG", "3"))
HTTP_TIMEOUT = 10  # segundos


# ======================= CLIENTE HTTP (urllib, sin dependencias) =======================

def _get_pendientes(api_url: str) -> list[dict]:
    url = f"{api_url.rstrip('/')}/etiquetas/pendientes"
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _confirmar(api_url: str, pedido_id: int, resultado: str, error_msg: str | None = None) -> None:
    url = f"{api_url.rstrip('/')}/etiquetas/{pedido_id}/confirmar"
    cuerpo = {"resultado": resultado}
    if error_msg:
        cuerpo["error_msg"] = error_msg[:500]
    data = json.dumps(cuerpo).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST", headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        resp.read()


# ======================= RENDER MODO "SIMPLE" =======================

def generar_imagen_simple(texto_libre: str):
    """
    Etiqueta de rotulación simple: SÓLO el texto libre, centrado.
    Sin QR, sin caja de código en negro. Reutiliza medidas y fuentes del agente.
    """
    ancho_px = agente._mm_a_px(agente.LABEL_ANCHO_MM)
    alto_px = agente._mm_a_px(agente.LABEL_ALTO_MM)

    img = Image.new("RGB", (ancho_px, alto_px), "white")
    draw = ImageDraw.Draw(img)
    margen = max(6, ancho_px // 40)
    ancho_texto_max = ancho_px - 2 * margen

    # Buscamos el tamaño de fuente más grande que entre (hasta 4 líneas).
    texto = str(texto_libre).strip().upper()
    tam = max(14, alto_px // 4)
    while tam >= 12:
        fuente = agente._cargar_fuente(agente.FUENTE_BOLD_CANDIDATAS, tam)
        lineas = agente._envolver_texto(draw, texto, fuente, ancho_texto_max)
        alto_total = len(lineas) * (fuente.size + 4)
        if len(lineas) <= 4 and alto_total <= (alto_px - 2 * margen):
            break
        tam -= 2

    alto_total = len(lineas) * (fuente.size + 4)
    y = max(margen, (alto_px - alto_total) // 2)
    for linea in lineas[:4]:
        ancho_linea = draw.textlength(linea, font=fuente)
        x = max(margen, (ancho_px - ancho_linea) // 2)
        draw.text((x, y), linea, font=fuente, fill="black")
        y += fuente.size + 4

    return img


# ======================= PROCESAMIENTO DE UN PEDIDO =======================

def _fuente_que_entra(draw, texto, candidatas, max_w, max_h, tam_inicial, tam_min=10):
    """Devuelve la fuente más grande (de las candidatas) con la que `texto` entra
    en un recuadro de max_w × max_h."""
    tam = tam_inicial
    fuente = agente._cargar_fuente(candidatas, tam)
    while tam > tam_min:
        fuente = agente._cargar_fuente(candidatas, tam)
        bbox = draw.textbbox((0, 0), texto, font=fuente)
        if (bbox[2] - bbox[0]) <= max_w and (bbox[3] - bbox[1]) <= max_h:
            break
        tam -= 2
    return fuente


def _texto_centrado(draw, texto, fuente, cx, cy, fill):
    """Dibuja `texto` centrado (horizontal y vertical) en el punto (cx, cy)."""
    bbox = draw.textbbox((0, 0), texto, font=fuente)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    draw.text((cx - w / 2 - bbox[0], cy - h / 2 - bbox[1]), texto, font=fuente, fill=fill)


def generar_imagen_codigo(codigo: str, descripcion: str, ubicacion: str, _qr_data: str = ""):
    """
    Etiqueta de código reconocido, con el formato del sistema actual:

        ┌──────────────────────────┐
        │      DESCRIPCIÓN (2 lín)  │
        ├──────────────────────────┤
        │ ███  CÓDIGO  (blanco) ███ │   barra negra
        ├──────────┬───────────────┤
        │UBICACIÓN │     VALOR      │
        └──────────┴───────────────┘
    """
    W = agente._mm_a_px(agente.LABEL_ANCHO_MM)
    H = agente._mm_a_px(agente.LABEL_ALTO_MM)
    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)

    borde = max(2, W // 200)
    pad = max(4, W // 60)

    # Alturas de las tres secciones.
    h_barra = int(H * 0.30)
    h_ubic = int(H * 0.28)
    h_desc = H - h_barra - h_ubic

    y_barra0 = h_desc
    y_barra1 = h_desc + h_barra
    x_div = int(W * 0.34)  # ancho de la celda "UBICACIÓN"

    # --- Bordes y líneas de la grilla ---
    draw.rectangle([0, 0, W - 1, H - 1], outline="black", width=borde)
    draw.rectangle([borde, y_barra0, W - borde, y_barra1], fill="black")
    draw.line([(0, y_barra1), (W, y_barra1)], fill="black", width=borde)
    draw.line([(x_div, y_barra1), (x_div, H)], fill="black", width=borde)

    # --- Descripción (hasta 2 líneas, centrada) ---
    desc = str(descripcion).upper().strip()
    ancho_desc = W - 2 * pad
    fuente_desc = agente._cargar_fuente(agente.FUENTE_BOLD_CANDIDATAS, max(14, int(h_desc * 0.42)))
    lineas = agente._envolver_texto(draw, desc, fuente_desc, ancho_desc)
    while len(lineas) > 2 and fuente_desc.size > 12:
        fuente_desc = agente._cargar_fuente(agente.FUENTE_BOLD_CANDIDATAS, fuente_desc.size - 2)
        lineas = agente._envolver_texto(draw, desc, fuente_desc, ancho_desc)
    lineas = lineas[:2]
    alto_linea = fuente_desc.size + 4
    y_txt = (h_desc - alto_linea * len(lineas)) / 2
    for ln in lineas:
        _texto_centrado(draw, ln, fuente_desc, W / 2, y_txt + alto_linea / 2, "black")
        y_txt += alto_linea

    # --- Código en la barra negra (blanco, ajustado para entrar completo) ---
    cod = str(codigo).upper().strip()
    fuente_cod = _fuente_que_entra(
        draw, cod, agente.FUENTE_BOLD_CANDIDATAS,
        W - 2 * (borde + pad), h_barra - 2 * pad, int(h_barra * 0.8),
    )
    _texto_centrado(draw, cod, fuente_cod, W / 2, (y_barra0 + y_barra1) / 2, "white")

    # --- Fila de ubicación: etiqueta + valor ---
    cy_ubic = (y_barra1 + H) / 2
    fuente_lbl = _fuente_que_entra(
        draw, "UBICACIÓN", agente.FUENTE_BOLD_CANDIDATAS,
        x_div - 2 * pad, h_ubic - 2 * pad, int(h_ubic * 0.5),
    )
    _texto_centrado(draw, "UBICACIÓN", fuente_lbl, x_div / 2, cy_ubic, "black")

    valor = str(ubicacion).upper().strip()
    fuente_val = _fuente_que_entra(
        draw, valor or "-", agente.FUENTE_BOLD_CANDIDATAS,
        (W - x_div) - 2 * pad, h_ubic - 2 * pad, int(h_ubic * 0.6),
    )
    _texto_centrado(draw, valor, fuente_val, (x_div + W) / 2, cy_ubic, "black")

    return img


def _render_pedido(pedido: dict):
    """Elige el render según el tipo de etiqueta."""
    tipo = pedido.get("tipo")
    if tipo == "simple":
        return generar_imagen_simple(pedido.get("texto_libre") or "")
    # tipo "codigo": descripción + barra de código + fila de ubicación
    return generar_imagen_codigo(
        codigo=pedido.get("codigo", ""),
        descripcion=pedido.get("descripcion", ""),
        ubicacion=pedido.get("ubicacion", ""),
    )


def _procesar_uno(api_url: str, pedido: dict) -> bool:
    """Imprime un pedido y lo confirma en la API. Devuelve True si imprimió."""
    pid = pedido.get("id")
    copias = int(pedido.get("cantidad", 1) or 1)
    etiqueta = pedido.get("texto_libre") or pedido.get("codigo") or f"#{pid}"
    try:
        img = _render_pedido(pedido)
        if agente.win32print is None:
            # Modo vista previa (sin impresora): un PNG por pedido (nombre único).
            salida = os.path.join(agente.BASE_DIR, f"preview_pedido_{pid}.png")
            img.save(salida)
            agente._log(f"[PREVIEW] Pedido {pid} guardado en: {salida}")
        else:
            agente.imprimir_imagen(img, copias=copias)
        _confirmar(api_url, pid, "impreso")
        agente._log(f"[OK] Pedido {pid} ({pedido.get('tipo')}: {etiqueta}) impreso.")
        return True
    except Exception as e:  # noqa: BLE001
        agente._log(f"[ERROR] Pedido {pid} ({etiqueta}): {e}")
        try:
            _confirmar(api_url, pid, "error", str(e))
        except Exception as e2:  # noqa: BLE001
            agente._log(f"[ERROR] No se pudo confirmar el error del pedido {pid}: {e2}")
        return False


def procesar_pendientes(api_url: str) -> int:
    """Trae y procesa todos los pendientes de una vuelta. Devuelve cuántos imprimió."""
    try:
        pendientes = _get_pendientes(api_url)
    except urllib.error.URLError as e:
        agente._log(f"[RED] No se pudo contactar la API ({api_url}): {e}")
        return 0

    impresos = 0
    for pedido in pendientes:
        if _procesar_uno(api_url, pedido):
            impresos += 1
    return impresos


# ======================= LOOP PRINCIPAL =======================

def main() -> None:
    parser = argparse.ArgumentParser(description="Agente de impresión de etiquetas (polling a etiquetas-api).")
    parser.add_argument("--api", default=API_URL_DEFAULT, help="URL base de la API.")
    parser.add_argument("--poll", type=float, default=POLL_SEG_DEFAULT, help="Segundos entre consultas.")
    parser.add_argument("--una-vez", action="store_true", help="Procesa una sola vuelta y sale (para pruebas).")
    parser.add_argument(
        "--preview",
        action="store_true",
        help="No imprime: guarda cada etiqueta como PNG (para probar sin impresora real).",
    )
    args = parser.parse_args()

    if args.preview:
        # Fuerza la rama de vista previa de imprimir_imagen (guarda PNG).
        agente.win32print = None
        agente._log("Modo PREVIEW: las etiquetas se guardan como PNG, no se imprimen.")

    agente._log(f"Print-agent iniciado. API={args.api} | polling cada {args.poll}s")

    if args.una_vez:
        n = procesar_pendientes(args.api)
        agente._log(f"Vuelta única terminada. {n} etiqueta(s) procesada(s).")
        return

    try:
        while True:
            procesar_pendientes(args.api)
            time.sleep(args.poll)
    except KeyboardInterrupt:
        agente._log("Print-agent detenido por el usuario.")


if __name__ == "__main__":
    main()
