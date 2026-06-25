"""
agente_impresion_etiquetas.py

Modulo INDEPENDIENTE para el sistema de panol. No modifica nada de
almacen_gui.py. Escucha en tiempo real la cola de impresion en Firestore
(coleccion "cola_impresion_etiquetas") y envia cada etiqueta pendiente a
la impresora termica conectada por USB a esta PC.

MODO DEMO: si no se encuentra serviceAccountKey.json en esta carpeta (o se
pasa --demo por linea de comandos), el script NO se conecta a Firestore:
genera una etiqueta de ejemplo y la guarda como imagen, para poder probar
el diseno y la logica de impresion aunque todavia no este el proyecto
completo en esta PC.

Uso:
    python agente_impresion_etiquetas.py            -> modo normal (Firestore)
    python agente_impresion_etiquetas.py --demo      -> modo demo forzado

Dependencias:
    pip install Pillow qrcode firebase-admin pywin32
    (pywin32 solo hace falta en la PC Windows real, con la impresora)
"""

import os
import sys
import time
import traceback
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

# --- QR (opcional: si no esta instalado, se usa un placeholder y se avisa) ---
try:
    import qrcode
except ImportError:
    qrcode = None

# --- Firebase (opcional, mismo patron que almacen_gui.py) ---
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
except ImportError:
    firebase_admin = None

# --- Impresion Windows (opcional, solo existe en Windows) ---
try:
    import win32print
    import win32ui
    from PIL import ImageWin
except ImportError:
    win32print = None


# ======================= CONFIGURACION =======================
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

JSON_KEY = os.path.join(BASE_DIR, "serviceAccountKey.json")
COLECCION_COLA = "cola_impresion_etiquetas"

# Tamano de etiqueta fisica. AJUSTAR segun la etiquetadora real.
LABEL_ANCHO_MM = 50
LABEL_ALTO_MM = 25
DPI = 300

LOG_FILE = os.path.join(BASE_DIR, "log_impresion_etiquetas.txt")

# Fuentes candidatas (Linux de prueba / Windows real). Se usa la primera que exista.
FUENTE_BOLD_CANDIDATAS = [
    "C:\\Windows\\Fonts\\arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
FUENTE_NORMAL_CANDIDATAS = [
    "C:\\Windows\\Fonts\\arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _mm_a_px(mm, dpi=DPI):
    return int(round((mm / 25.4) * dpi))


def _cargar_fuente(candidatas, tamano):
    for ruta in candidatas:
        if os.path.exists(ruta):
            try:
                return ImageFont.truetype(ruta, tamano)
            except Exception:
                continue
    return ImageFont.load_default()


def _log(mensaje):
    linea = f"[{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}] {mensaje}"
    print(linea)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(linea + "\n")
    except Exception:
        pass


def _envolver_texto(draw, texto, fuente, ancho_max_px):
    """Corta el texto en lineas para que entre en ancho_max_px."""
    palabras = str(texto).split()
    lineas = []
    actual = ""
    for palabra in palabras:
        prueba = (actual + " " + palabra).strip()
        if draw.textlength(prueba, font=fuente) <= ancho_max_px:
            actual = prueba
        else:
            if actual:
                lineas.append(actual)
            actual = palabra
    if actual:
        lineas.append(actual)
    return lineas


def _generar_qr(data, lado_px):
    """Devuelve la imagen del QR. Si la libreria 'qrcode' no esta instalada,
    devuelve un placeholder (para poder probar el modulo igual)."""
    if qrcode is not None:
        img = qrcode.make(data or "SIN-CODIGO")
        return img.resize((lado_px, lado_px))

    placeholder = Image.new("RGB", (lado_px, lado_px), "white")
    d = ImageDraw.Draw(placeholder)
    d.rectangle([0, 0, lado_px - 1, lado_px - 1], outline="black", width=3)
    d.line([0, 0, lado_px, lado_px], fill="black", width=2)
    d.line([0, lado_px, lado_px, 0], fill="black", width=2)
    fuente = _cargar_fuente(FUENTE_NORMAL_CANDIDATAS, max(10, lado_px // 8))
    d.text((6, lado_px // 2 - 6), "QR", font=fuente, fill="black")
    return placeholder


# ======================= DISENO DE LA ETIQUETA =======================

def generar_imagen_etiqueta(codigo, descripcion, ubicacion, qr_data, cantidad=1):
    """
    Genera la imagen de la etiqueta lista para imprimir.

    Diseno:
      - CODIGO: remarcado con fondo negro y letra blanca en negrita (facil lectura).
      - Descripcion: texto normal, debajo del codigo.
      - Ubicacion: texto normal, debajo de la descripcion.
      - QR (qr_data): a la derecha, ocupando el alto disponible.
    """
    ancho_px = _mm_a_px(LABEL_ANCHO_MM)
    alto_px = _mm_a_px(LABEL_ALTO_MM)

    img = Image.new("RGB", (ancho_px, alto_px), "white")
    draw = ImageDraw.Draw(img)

    margen = max(6, ancho_px // 40)

    # --- Zona QR (derecha) ---
    qr_lado = alto_px - 2 * margen
    qr_img = _generar_qr(qr_data or codigo, qr_lado)
    qr_x = ancho_px - qr_lado - margen
    img.paste(qr_img, (qr_x, margen))

    # --- Zona de texto (izquierda) ---
    ancho_texto_max = qr_x - margen * 2

    fuente_codigo = _cargar_fuente(FUENTE_BOLD_CANDIDATAS, max(16, alto_px // 5))
    fuente_normal = _cargar_fuente(FUENTE_NORMAL_CANDIDATAS, max(11, alto_px // 11))

    y = margen

    # CODIGO remarcado: fondo negro, letra blanca, negrita
    texto_codigo = str(codigo).upper()
    bbox = draw.textbbox((0, 0), texto_codigo, font=fuente_codigo)
    alto_codigo = bbox[3] - bbox[1]
    pad = max(4, alto_codigo // 5)
    caja_alto = alto_codigo + pad * 2
    draw.rectangle(
        [margen, y, margen + ancho_texto_max, y + caja_alto],
        fill="black",
    )
    draw.text((margen + pad, y + pad - bbox[1]), texto_codigo, font=fuente_codigo, fill="white")
    y += caja_alto + pad

    # Descripcion (texto normal, hasta 2 lineas para no salirse de la etiqueta)
    lineas_desc = _envolver_texto(draw, str(descripcion).upper(), fuente_normal, ancho_texto_max)
    for linea in lineas_desc[:2]:
        draw.text((margen, y), linea, font=fuente_normal, fill="black")
        y += fuente_normal.size + 3

    y += 3
    # Ubicacion
    draw.text((margen, y), f"Ubic.: {ubicacion}", font=fuente_normal, fill="black")

    return img


# ======================= IMPRESION =======================

def imprimir_imagen(img, copias=1):
    """
    Envia la imagen a la impresora predeterminada de Windows.
    Si no se esta en Windows (ej. probando este modulo en otra PC/SO antes
    de tener la impresora a mano), guarda la imagen en disco para revisarla.
    """
    if win32print is None:
        salida = os.path.join(
            BASE_DIR, f"etiqueta_preview_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        )
        img.save(salida)
        _log(f"[SIN IMPRESORA WINDOWS DETECTADA] Etiqueta guardada como preview en: {salida}")
        return salida

    impresora = win32print.GetDefaultPrinter()
    hdc = win32ui.CreateDC()
    hdc.CreatePrinterDC(impresora)

    # Escalamos la imagen al área imprimible REAL de la etiqueta. La imagen se
    # genera a 300 DPI, pero la impresora térmica suele ser de 203 DPI: si se
    # dibuja a tamaño de píxel, se interpreta como un área mayor y se corta.
    # GetDeviceCaps(HORZRES/VERTRES) da el área imprimible en píxeles del equipo.
    HORZRES, VERTRES = 8, 10
    ancho_imp = hdc.GetDeviceCaps(HORZRES)
    alto_imp = hdc.GetDeviceCaps(VERTRES)
    w, h = img.size
    if ancho_imp > 0 and alto_imp > 0:
        escala = min(ancho_imp / w, alto_imp / h)
        nw, nh = max(1, int(w * escala)), max(1, int(h * escala))
    else:
        nw, nh = w, h

    for _ in range(max(1, copias)):
        hdc.StartDoc("Etiqueta Panol")
        hdc.StartPage()
        dib = ImageWin.Dib(img)
        dib.draw(hdc.GetHandleOutput(), (0, 0, nw, nh))
        hdc.EndPage()
        hdc.EndDoc()
    hdc.DeleteDC()
    _log(f"Etiqueta enviada a '{impresora}' ({copias} copia/s, area {ancho_imp}x{alto_imp}px).")
    return None


def _procesar_pedido(datos, on_exito=None, on_error=None):
    try:
        img = generar_imagen_etiqueta(
            codigo=datos.get("codigo", ""),
            descripcion=datos.get("descripcion", ""),
            ubicacion=datos.get("ubicacion", ""),
            qr_data=datos.get("qr_data") or datos.get("codigo", ""),
            cantidad=datos.get("cantidad", 1),
        )
        imprimir_imagen(img, copias=datos.get("cantidad", 1))
        if on_exito:
            on_exito()
    except Exception as e:
        _log(f"ERROR al procesar pedido {datos.get('codigo')}: {e}")
        traceback.print_exc()
        if on_error:
            on_error(str(e))


# ======================= MODO FIRESTORE (produccion) =======================

def _inicializar_firebase():
    if not firebase_admin:
        return None
    if not os.path.exists(JSON_KEY):
        return None
    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(JSON_KEY)
            firebase_admin.initialize_app(cred)
        return firestore.client()
    except Exception as e:
        _log(f"No se pudo conectar a Firebase: {e}")
        return None


def _escuchar_cola(db):
    coleccion = db.collection(COLECCION_COLA)

    def on_snapshot(col_snapshot, changes, read_time):
        for change in changes:
            if change.type.name not in ("ADDED", "MODIFIED"):
                continue
            doc = change.document
            datos = doc.to_dict()
            if datos.get("estado") != "pendiente":
                continue

            intentos = datos.get("intentos", 0)
            if intentos >= 3:
                continue

            def marcar_impreso(doc_ref=doc.reference):
                doc_ref.update({
                    "estado": "impreso",
                    "fecha_impresion": firestore.SERVER_TIMESTAMP,
                })

            def marcar_error(msg, doc_ref=doc.reference, intentos_prev=intentos):
                doc_ref.update({
                    "estado": "error",
                    "error_msg": msg,
                    "intentos": intentos_prev + 1,
                })

            _procesar_pedido(datos, on_exito=marcar_impreso, on_error=marcar_error)

    query = coleccion.where("estado", "==", "pendiente")
    return query.on_snapshot(on_snapshot)


def iniciar_modo_produccion():
    db = _inicializar_firebase()
    if not db:
        _log("No se encontro serviceAccountKey.json o Firebase no esta disponible.")
        _log("Probá el modulo con: python agente_impresion_etiquetas.py --demo")
        return False

    _log(f"Agente de impresion iniciado. Escuchando coleccion '{COLECCION_COLA}'...")
    watch = _escuchar_cola(db)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        watch.unsubscribe()
        _log("Agente detenido por el usuario.")
    return True


# ======================= MODO DEMO (sin proyecto completo) =======================

PEDIDO_DEMO = {
    "codigo": "ROD-6204-2RS",
    "descripcion": "Rodamiento 6204 2RS doble blindaje",
    "ubicacion": "Estanteria B - Fila 3",
    "qr_data": "ROD-6204-2RS",
    "cantidad": 1,
}


def iniciar_modo_demo():
    _log("=== MODO DEMO === (no se encontro el proyecto completo / Firebase en esta PC)")
    _log("Generando una etiqueta de prueba con datos de ejemplo...")
    _procesar_pedido(
        PEDIDO_DEMO,
        on_exito=lambda: _log("Etiqueta de prueba procesada con exito."),
        on_error=lambda msg: _log(f"Fallo la etiqueta de prueba: {msg}"),
    )


if __name__ == "__main__":
    forzar_demo = "--demo" in sys.argv
    if forzar_demo or not os.path.exists(JSON_KEY):
        iniciar_modo_demo()
    else:
        iniciar_modo_produccion()
