# Módulo de Etiquetas - Sistema Pañol

Imprime etiquetas de artículos (descripción + código + ubicación + QR) enviando
la orden **por Firebase** desde otra PC o desde el celular/web, hacia la PC que
tiene la impresora conectada por **USB**.

```
   Otra PC / Celular (web)              PC con impresora USB
   ┌───────────────────┐               ┌────────────────────────┐
   │  index.html  ó     │   Firebase    │ modulo_etiquetas.py    │
   │  enviar (script) ──┼──►(cola_  ───►│   escuchar  ──► 🖨️ USB │
   └───────────────────┘   impresion)   └────────────────────────┘
```

## Archivos nuevos
- `modulo_etiquetas.py` — núcleo: diseño de la etiqueta, cola de Firebase, impresión USB, demo.
- `etiquetas_web/index.html` — app web/móvil: busca el artículo, muestra el diseño y lo manda a imprimir.
- `IMPRIMIR_ETIQUETAS.bat` — se corre en la PC de la impresora (queda escuchando).
- `VER_DEMO_ETIQUETA.bat` — genera una etiqueta de ejemplo para ver el diseño.
- `requirements_etiquetas.txt` — dependencias.

## Instalación (una vez)
```
pip install -r requirements_etiquetas.txt
```
`pywin32` solo hace falta en la PC que imprime (Windows).

## 1) Ver el diseño HOY (demo)
**Opción A — sin Python:** abrí `etiquetas_web/index.html` con doble clic.
Ya viene con un artículo de ejemplo y dibuja la etiqueta en vivo.

**Opción B — con Python:** doble clic en `VER_DEMO_ETIQUETA.bat`
(o `python modulo_etiquetas.py demo`). Genera `etiqueta_demo.png` y la abre.

## 2) Probar SIN impresora (simulación)
En cualquier PC con la `serviceAccountKey.json`:
```
python modulo_etiquetas.py escuchar --sin-impresora
```
Cada trabajo que llegue se guarda como PNG (`etiqueta_<codigo>.png`) en vez de imprimirse.
Desde otra terminal o desde la web, encolá una etiqueta y vas a ver el archivo aparecer.

## 3) En la estación real (mañana)
En la **PC de la impresora**:
```
doble clic en  IMPRIMIR_ETIQUETAS.bat
```
(o `python modulo_etiquetas.py escuchar` / `--impresora "Nombre exacto"`).
Dejá esa ventana abierta. Imprime en la impresora predeterminada salvo que indiques otra.

Desde **otra PC**:
```
python modulo_etiquetas.py enviar --codigo A-10543 --copias 2
```
Desde el **celular/web**: abrí `etiquetas_web/index.html`, buscá el artículo y tocá *Enviar*.

## Configurar la web (para móvil/otra PC)
La web usa el SDK público de Firebase. Una sola vez, en `index.html` →
sección *⚙️ Configuración de Firebase*, pegá tu config web:
Firebase Console → ⚙️ Configuración del proyecto → *Tus apps* → Web → SDK config
(`apiKey`, `authDomain`, `projectId`, `appId`). El `projectId` ya viene puesto
(`sistemapanol-a1bd4`). Queda guardado en el navegador.

> La app de escritorio usa el Admin SDK (ignora las reglas). Para que la web pueda
> leer `articulos` y escribir en `cola_impresion`, las reglas de Firestore deben
> permitirlo (en modo prueba ya funciona).

## Diseño de la etiqueta
- **Descripción** arriba a la izquierda (hasta 3 líneas, se ajusta sola).
- **Código** en recuadro **negro con letras blancas** (destacado, centrado).
- **Ubicación** abajo.
- **QR** arriba a la derecha (codifica el código, escaneable hacia la app).

Medidas y estilo se ajustan en la clase `ConfigEtiqueta` de `modulo_etiquetas.py`
(`ANCHO_MM`, `ALTO_MM`, `DPI`, colores, márgenes).

## Integración opcional con la app (almacen_gui.py)
Para imprimir la etiqueta del artículo cargado, agregá un botón que llame:
```python
from modulo_etiquetas import render_etiqueta, imprimir_imagen_windows

def imprimir_etiqueta_actual(self):
    datos = {
        "codigo": self.codigo_var.get().strip().upper(),
        "descripcion": self.desc_var.get(),
        "ubicacion": self.stk_ubic_var.get(),
    }
    imprimir_imagen_windows(render_etiqueta(datos))
```
(o `enviar_etiqueta(codigo)` si esa PC no es la que tiene la impresora).
