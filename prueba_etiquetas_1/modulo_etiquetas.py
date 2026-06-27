# -*- coding: utf-8 -*-
"""
MÓDULO DE ETIQUETAS - Sistema Pañol
====================================
Permite enviar etiquetas a imprimir a través de Firebase desde:
  - Otra PC (script Python con la misma serviceAccountKey)
  - La app web / móvil (carpeta etiquetas_web/index.html)
...hacia la PC que está conectada físicamente a la impresora por USB.

La PC con la impresora corre este módulo en modo "escuchar": queda atento a la
cola de impresión en Firestore (colección 'cola_impresion') y, cuando llega un
trabajo nuevo, genera la etiqueta (descripción + código + ubicación + QR) y la
manda a la impresora USB.

DISEÑO DE LA ETIQUETA:
  - Descripción del artículo (arriba)
  - Código en recuadro NEGRO con letras BLANCAS (destacado)
  - Ubicación
  - Código QR (codifica el código del artículo)

USO RÁPIDO (línea de comandos):
  python modulo_etiquetas.py demo
      -> Genera una etiqueta de ejemplo (PNG) y la abre. Ideal para ver el diseño.

  python modulo_etiquetas.py escuchar
      -> Corre en la PC de la impresora. Escucha la cola y va imprimiendo.

  python modulo_etiquetas.py enviar --codigo 12345 --copias 1
      -> Desde otra PC: encola una etiqueta (busca desc/ubicación en Firestore).

  python modulo_etiquetas.py preview --codigo 12345
      -> Trae el artículo de Firestore y genera el PNG de su etiqueta (sin imprimir).

Dependencias:
  pip install pillow qrcode firebase-admin pywin32
  (pywin32 sólo se necesita en la PC que imprime, en Windows)
"""

import os
import sys
import io
import time
import argparse
import threading
from datetime import datetime

# ----------------------------------------------------------------------------
# Dependencias de imagen / QR
# ----------------------------------------------------------------------------
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("[ERROR] Falta Pillow. Instalá con:  pip install pillow")
    raise

try:
    import qrcode
except ImportError:
    print("[ERROR] Falta qrcode. Instalá con:  pip install qrcode")
    raise

# ----------------------------------------------------------------------------
# Rutas base (compatible con el .exe de PyInstaller, igual que almacen_gui.py)
# ----------------------------------------------------------------------------
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

JSON_KEY = os.path.join(BASE_DIR, "serviceAccountKey.json")
COLECCION_COLA = "cola_impresion"
COLECCION_ARTICULOS = "articulos"

# ============================================================================
# 1) CONFIGURACIÓN DEL DISEÑO DE LA ETIQUETA
# ============================================================================
class ConfigEtiqueta:
    """Medidas y estilo de la etiqueta. Ajustá según tu impresora/rollo."""
    ANCHO_MM = 50          # ancho físico de la etiqueta
    ALTO_MM = 30           # alto físico de la etiqueta
    DPI = 300              # densidad (300 da buena calidad para QR)

    MARGEN = 16            # margen interno en px
    COLOR_FONDO = "white"
    COLOR_TEXTO = "black"
    COLOR_CAJA_CODIGO = "black"     # recuadro del código
    COLOR_TEXTO_CODIGO = "white"    # letras del código
    BORDE = True                     # dibujar borde de la etiqueta

    @classmethod
    def px(cls, mm):
        return int(round(mm / 25.4 * cls.DPI))

    @classmethod
    def tamano_px(cls):
        return (cls.px(cls.ANCHO_MM), cls.px(cls.ALTO_MM))


def _cargar_fuente(nombre, tamano):
    """Carga una TrueType; si no está, usa la fuente por defecto de PIL."""
    candidatos = [
        nombre,
        os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", nombre),
        "arial.ttf",
        "DejaVuSans.ttf",
    ]
    for c in candidatos:
        try:
            return ImageFont.truetype(c, tamano)
        except Exception:
            continue
    return ImageFont.load_default()


def _medir(draw, texto, fuente):
    bbox = draw.textbbox((0, 0), texto, font=fuente)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _ajustar_texto(draw, texto, fuente, ancho_max):
    """Parte el texto en varias líneas para que entre en ancho_max (px)."""
    palabras = str(texto).split()
    if not palabras:
        return [""]
    lineas, actual = [], palabras[0]
    for p in palabras[1:]:
        prueba = actual + " " + p
        w, _ = _medir(draw, prueba, fuente)
        if w <= ancho_max:
            actual = prueba
        else:
            lineas.append(actual)
            actual = p
    lineas.append(actual)
    return lineas


# ============================================================================
# 2) RENDER DE LA ETIQUETA (genera la imagen PIL)
# ============================================================================
def render_etiqueta(datos, cfg=ConfigEtiqueta):
    """
    datos: dict con claves 'codigo', 'descripcion', 'ubicacion'.
    Devuelve una imagen PIL lista para imprimir o guardar.
    """
    codigo = str(datos.get("codigo", "") or "").strip()
    descripcion = str(datos.get("descripcion", "") or "").strip()
    ubicacion = str(datos.get("ubicacion", "") or "").strip() or "S/U"

    W, H = cfg.tamano_px()
    img = Image.new("RGB", (W, H), cfg.COLOR_FONDO)
    d = ImageDraw.Draw(img)

    m = cfg.MARGEN
    if cfg.BORDE:
        d.rectangle([2, 2, W - 3, H - 3], outline=cfg.COLOR_TEXTO, width=2)

    # --- QR (codifica el código del artículo) arriba a la derecha ---
    qr_lado = int(H * 0.46)
    qr_img = None
    if codigo:
        qr = qrcode.QRCode(version=None, box_size=10, border=1,
                           error_correction=qrcode.constants.ERROR_CORRECT_M)
        qr.add_data(codigo)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        qr_img = qr_img.resize((qr_lado, qr_lado), Image.NEAREST)
        img.paste(qr_img, (W - m - qr_lado, m))

    # Ancho disponible para el texto a la izquierda del QR
    ancho_texto = (W - m - qr_lado - m) - m if qr_img else (W - 2 * m)

    # --- Etiqueta "DESCRIPCIÓN" + texto (arriba a la izquierda) ---
    f_mini = _cargar_fuente("arial.ttf", int(H * 0.055))
    f_desc = _cargar_fuente("arialbd.ttf", int(H * 0.085))

    y = m
    d.text((m, y), "DESCRIPCIÓN", font=f_mini, fill="#555555")
    y += _medir(d, "DESCRIPCIÓN", f_mini)[1] + 4

    lineas = _ajustar_texto(d, descripcion, f_desc, ancho_texto)[:3]
    alto_linea = _medir(d, "Ag", f_desc)[1] + 6
    for ln in lineas:
        d.text((m, y), ln, font=f_desc, fill=cfg.COLOR_TEXTO)
        y += alto_linea

    # --- CÓDIGO: recuadro negro, letras blancas (ancho completo) ---
    caja_top = max(y + 8, m + qr_lado + 8)
    caja_h = int(H * 0.27)
    caja = [m, caja_top, W - m, caja_top + caja_h]
    d.rectangle(caja, fill=cfg.COLOR_CAJA_CODIGO)

    # Tamaño de fuente del código que entre en la caja
    tam = caja_h
    f_cod = _cargar_fuente("arialbd.ttf", tam)
    while tam > 10:
        f_cod = _cargar_fuente("arialbd.ttf", tam)
        cw, ch = _medir(d, codigo or " ", f_cod)
        if cw <= (caja[2] - caja[0]) - 20 and ch <= caja_h - 8:
            break
        tam -= 2
    cw, ch = _medir(d, codigo or " ", f_cod)
    cx = caja[0] + ((caja[2] - caja[0]) - cw) // 2
    cy = caja[1] + ((caja[3] - caja[1]) - ch) // 2
    bbox = d.textbbox((0, 0), codigo or " ", font=f_cod)
    d.text((cx - bbox[0], cy - bbox[1]), codigo, font=f_cod, fill=cfg.COLOR_TEXTO_CODIGO)

    # --- UBICACIÓN (abajo) ---
    f_ulbl = _cargar_fuente("arial.ttf", int(H * 0.055))
    f_ubic = _cargar_fuente("arialbd.ttf", int(H * 0.075))
    uy = caja[3] + 8
    d.text((m, uy), "UBICACIÓN", font=f_ulbl, fill="#555555")
    uy += _medir(d, "UBICACIÓN", f_ulbl)[1] + 2
    d.text((m, uy), ubicacion, font=f_ubic, fill=cfg.COLOR_TEXTO)

    return img


# ============================================================================
# 3) IMPRESIÓN EN WINDOWS (impresora USB / por defecto)
# ============================================================================
def imprimir_imagen_windows(img, printer_name=None):
    """
    Manda la imagen PIL a la impresora de Windows indicada (o la predeterminada).
    Requiere pywin32. Escala la etiqueta al área imprimible manteniendo proporción.
    """
    try:
        import win32print
        import win32ui
        from PIL import ImageWin
    except ImportError:
        # Fallback: guardar y mandar a imprimir con el visor predeterminado
        ruta = os.path.join(BASE_DIR, "_etiqueta_tmp.png")
        img.save(ruta, dpi=(ConfigEtiqueta.DPI, ConfigEtiqueta.DPI))
        try:
            os.startfile(ruta, "print")
            return True
        except Exception as e:
            print(f"[ERROR] No se pudo imprimir (instalá pywin32): {e}")
            return False

    if printer_name is None:
        printer_name = win32print.GetDefaultPrinter()

    hDC = win32ui.CreateDC()
    hDC.CreatePrinterDC(printer_name)
    hDC.StartDoc("Etiqueta Pañol")
    hDC.StartPage()

    HORZRES, VERTRES = 8, 10  # GetDeviceCaps índices
    ancho_imp = hDC.GetDeviceCaps(HORZRES)
    alto_imp = hDC.GetDeviceCaps(VERTRES)

    w, h = img.size
    escala = min(ancho_imp / w, alto_imp / h)
    nw, nh = int(w * escala), int(h * escala)

    dib = ImageWin.Dib(img)
    dib.draw(hDC.GetHandleOutput(), (0, 0, nw, nh))

    hDC.EndPage()
    hDC.EndDoc()
    hDC.DeleteDC()
    print(f"[OK] Enviado a impresora: {printer_name}")
    return True


# ============================================================================
# 4) FIREBASE: inicialización, cola y envío
# ============================================================================
_db = None

def get_db():
    """Inicializa Firebase Admin (una sola vez) y devuelve el cliente Firestore."""
    global _db
    if _db is not None:
        return _db
    import firebase_admin
    from firebase_admin import credentials, firestore
    if not firebase_admin._apps:
        cred = credentials.Certificate(JSON_KEY)
        firebase_admin.initialize_app(cred)
    _db = firestore.client()
    return _db


def buscar_articulo(codigo):
    """Trae descripción y ubicación de un artículo desde Firestore."""
    db = get_db()
    doc = db.collection(COLECCION_ARTICULOS).document(str(codigo).strip()).get()
    if doc.exists:
        a = doc.to_dict()
        return {
            "codigo": a.get("codigo", codigo),
            "descripcion": a.get("desc", a.get("descripcion", "")),
            "ubicacion": a.get("ubicacion", "S/U"),
        }
    return None


def enviar_etiqueta(codigo, descripcion=None, ubicacion=None, copias=1, origen="script"):
    """
    Encola una etiqueta en Firestore para que la PC de la impresora la imprima.
    Si no se pasan desc/ubicación, las busca en la colección 'articulos'.
    """
    from firebase_admin import firestore
    db = get_db()
    codigo = str(codigo).strip()

    if descripcion is None or ubicacion is None:
        art = buscar_articulo(codigo)
        if art:
            descripcion = descripcion or art["descripcion"]
            ubicacion = ubicacion or art["ubicacion"]
        else:
            print(f"[AVISO] Código '{codigo}' no encontrado en Firestore. Se encola igual.")
            descripcion = descripcion or ""
            ubicacion = ubicacion or "S/U"

    trabajo = {
        "codigo": codigo,
        "descripcion": descripcion,
        "ubicacion": ubicacion,
        "copias": int(copias),
        "estado": "pendiente",
        "origen": origen,
        "creado": firestore.SERVER_TIMESTAMP,
    }
    ref = db.collection(COLECCION_COLA).add(trabajo)
    doc_id = ref[1].id if isinstance(ref, tuple) else ref.id
    print(f"[OK] Etiqueta encolada (id={doc_id}) -> {codigo} | {descripcion} | {ubicacion}")
    return doc_id


# ============================================================================
# 5) ESCUCHA EN LA PC DE LA IMPRESORA
# ============================================================================
def _procesar_trabajo(doc_ref, data, printer_name, sin_impresora=False):
    from firebase_admin import firestore
    codigo = data.get("codigo", "")
    try:
        doc_ref.update({"estado": "imprimiendo"})
        img = render_etiqueta({
            "codigo": codigo,
            "descripcion": data.get("descripcion", ""),
            "ubicacion": data.get("ubicacion", "S/U"),
        })
        copias = int(data.get("copias", 1) or 1)

        if sin_impresora:
            ruta = os.path.join(BASE_DIR, f"etiqueta_{codigo or 'job'}.png")
            img.save(ruta, dpi=(ConfigEtiqueta.DPI, ConfigEtiqueta.DPI))
            print(f"[SIM] (sin impresora) Etiqueta guardada en: {ruta}")
        else:
            for _ in range(max(1, copias)):
                imprimir_imagen_windows(img, printer_name)

        doc_ref.update({
            "estado": "impreso",
            "impreso_en": firestore.SERVER_TIMESTAMP,
        })
        print(f"[OK] Trabajo impreso: {codigo}")
    except Exception as e:
        print(f"[ERROR] Falló trabajo {codigo}: {e}")
        try:
            doc_ref.update({"estado": "error", "mensaje_error": str(e)})
        except Exception:
            pass


def escuchar(printer_name=None, sin_impresora=False):
    """
    Corre en la PC de la impresora. Queda escuchando la cola de Firestore y
    cada trabajo 'pendiente' lo imprime. Mantené esta ventana abierta.
    """
    db = get_db()
    procesados = set()
    listo = threading.Event()

    def on_snapshot(col_snapshot, changes, read_time):
        for change in changes:
            if change.type.name in ("ADDED", "MODIFIED"):
                doc = change.document
                data = doc.to_dict() or {}
                if data.get("estado") == "pendiente" and doc.id not in procesados:
                    procesados.add(doc.id)
                    _procesar_trabajo(doc.reference, data, printer_name, sin_impresora)

    query = db.collection(COLECCION_COLA).where("estado", "==", "pendiente")
    watch = query.on_snapshot(on_snapshot)

    modo = "SIMULACIÓN (guarda PNG)" if sin_impresora else f"impresora '{printer_name or 'predeterminada'}'"
    print("=" * 60)
    print(f"  ESCUCHANDO COLA DE IMPRESIÓN  ({modo})")
    print("  Colección Firestore:", COLECCION_COLA)
    print("  Dejá esta ventana abierta. Ctrl+C para salir.")
    print("=" * 60)
    try:
        while not listo.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nCerrando escucha...")
    finally:
        try:
            watch.unsubscribe()
        except Exception:
            pass


# ============================================================================
# 6) DEMO / PREVIEW
# ============================================================================
def demo():
    """Genera una etiqueta de ejemplo y la abre para ver el diseño."""
    ejemplo = {
        "codigo": "A-10543",
        "descripcion": "RODAMIENTO RIGIDO DE BOLAS 6204 2RS SKF",
        "ubicacion": "EST 3 - FILA B - CAJON 12",
    }
    img = render_etiqueta(ejemplo)
    ruta = os.path.join(BASE_DIR, "etiqueta_demo.png")
    img.save(ruta, dpi=(ConfigEtiqueta.DPI, ConfigEtiqueta.DPI))
    print(f"[OK] Demo generada: {ruta}")
    try:
        os.startfile(ruta)
    except Exception:
        pass
    return ruta


def preview(codigo):
    """Trae el artículo de Firestore y genera el PNG de su etiqueta (sin imprimir)."""
    art = buscar_articulo(codigo)
    if not art:
        print(f"[ERROR] Código '{codigo}' no encontrado en Firestore.")
        return None
    img = render_etiqueta(art)
    ruta = os.path.join(BASE_DIR, f"preview_{codigo}.png")
    img.save(ruta, dpi=(ConfigEtiqueta.DPI, ConfigEtiqueta.DPI))
    print(f"[OK] Preview generada: {ruta}")
    try:
        os.startfile(ruta)
    except Exception:
        pass
    return ruta


# ============================================================================
# CLI
# ============================================================================
def main():
    parser = argparse.ArgumentParser(description="Módulo de etiquetas - Sistema Pañol")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("demo", help="Genera y abre una etiqueta de ejemplo")

    p_esc = sub.add_parser("escuchar", help="PC impresora: escucha la cola e imprime")
    p_esc.add_argument("--impresora", default=None, help="Nombre exacto de la impresora")
    p_esc.add_argument("--sin-impresora", action="store_true",
                       help="No imprime: guarda cada etiqueta como PNG (para probar)")

    p_env = sub.add_parser("enviar", help="Otra PC: encola una etiqueta")
    p_env.add_argument("--codigo", required=True)
    p_env.add_argument("--descripcion", default=None)
    p_env.add_argument("--ubicacion", default=None)
    p_env.add_argument("--copias", type=int, default=1)
    p_env.add_argument("--origen", default="script")

    p_prev = sub.add_parser("preview", help="Genera el PNG de un código desde Firestore")
    p_prev.add_argument("--codigo", required=True)

    args = parser.parse_args()

    if args.cmd == "demo":
        demo()
    elif args.cmd == "escuchar":
        escuchar(printer_name=args.impresora, sin_impresora=args.sin_impresora)
    elif args.cmd == "enviar":
        enviar_etiqueta(args.codigo, args.descripcion, args.ubicacion,
                        args.copias, args.origen)
    elif args.cmd == "preview":
        preview(args.codigo)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
