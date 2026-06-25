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

def generar_imagen_codigo(codigo: str, descripcion: str, ubicacion: str, qr_data: str):
    """
    Etiqueta de código reconocido: código en caja negra (letra blanca, negrita) +
    descripción + ubicación + QR a la derecha.

    A diferencia del render heredado, acá el tamaño de fuente del código se ajusta
    para que entre COMPLETO en la caja (los códigos largos no se recortan).
    Reutiliza los helpers de bajo nivel del módulo heredado (fuentes, QR, medidas).
    """
    ancho_px = agente._mm_a_px(agente.LABEL_ANCHO_MM)
    alto_px = agente._mm_a_px(agente.LABEL_ALTO_MM)

    img = Image.new("RGB", (ancho_px, alto_px), "white")
    draw = ImageDraw.Draw(img)
    margen = max(6, ancho_px // 40)

    # --- QR a la derecha ---
    qr_lado = alto_px - 2 * margen
    qr_img = agente._generar_qr(qr_data or codigo, qr_lado)
    qr_x = ancho_px - qr_lado - margen
    img.paste(qr_img, (qr_x, margen))

    ancho_texto_max = qr_x - margen * 2
    fuente_normal = agente._cargar_fuente(agente.FUENTE_NORMAL_CANDIDATAS, max(11, alto_px // 11))

    y = margen
    texto_codigo = str(codigo).upper()

    # Achica la fuente del código hasta que entre en el ancho disponible.
    pad = max(4, alto_px // 40)
    tam = max(16, alto_px // 4)
    while tam >= 12:
        fuente_codigo = agente._cargar_fuente(agente.FUENTE_BOLD_CANDIDATAS, tam)
        ancho_cod = draw.textlength(texto_codigo, font=fuente_codigo)
        if ancho_cod <= ancho_texto_max - 2 * pad:
            break
        tam -= 2

    bbox = draw.textbbox((0, 0), texto_codigo, font=fuente_codigo)
    alto_codigo = bbox[3] - bbox[1]
    caja_alto = alto_codigo + pad * 2
    draw.rectangle([margen, y, margen + ancho_texto_max, y + caja_alto], fill="black")
    draw.text((margen + pad, y + pad - bbox[1]), texto_codigo, font=fuente_codigo, fill="white")
    y += caja_alto + pad

    # Descripción (hasta 2 líneas).
    for linea in agente._envolver_texto(draw, str(descripcion).upper(), fuente_normal, ancho_texto_max)[:2]:
        draw.text((margen, y), linea, font=fuente_normal, fill="black")
        y += fuente_normal.size + 3

    y += 3
    draw.text((margen, y), f"Ubic.: {ubicacion}", font=fuente_normal, fill="black")
    return img


def _render_pedido(pedido: dict):
    """Elige el render según el tipo de etiqueta."""
    tipo = pedido.get("tipo")
    if tipo == "simple":
        return generar_imagen_simple(pedido.get("texto_libre") or "")
    # tipo "codigo": código en negro + desc + ubic + QR
    return generar_imagen_codigo(
        codigo=pedido.get("codigo", ""),
        descripcion=pedido.get("descripcion", ""),
        ubicacion=pedido.get("ubicacion", ""),
        qr_data=pedido.get("qr_data") or pedido.get("codigo", ""),
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
