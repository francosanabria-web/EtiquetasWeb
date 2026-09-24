# Contexto técnico del proyecto — Sistema Pañol

> Documento de contexto para planificar la migración del monolito de escritorio a una app web.
> Datos verificados sobre el código y los archivos reales del proyecto (no estimaciones).
> Última actualización: 2026-06-24.

---

## 1. Monolito actual (app de escritorio)

### Lenguaje / framework
- **Python 3.14 + Tkinter** (GUI de escritorio para Windows).
- Archivo único: **`almacen_gui.py`** (~245 KB, ~4.800 líneas). Es un monolito en un solo archivo.
- Librerías clave: `pandas`, `openpyxl`, `xlsxwriter` (Excel), `tkcalendar` (fechas), `firebase-admin` (nube), `smtplib`/`email` (mails).
- Empaquetado a `.exe` con **PyInstaller** (specs: `almacen_gui.spec` → genera `SistemasPañol.exe`).
- Se distribuye/ejecuta como app local; los datos viajan junto al `.exe` (pendrive / carpeta).

### Módulos funcionales (hoy)
Organizado en 4 pestañas + lógica transversal:

1. **Registro de salidas** — descuento de stock, registro de movimientos con precarga (botón *Registrar salida* → *Finalizar* confirma y escribe), simulador de costos.
2. **Reportes** — gasto diario y mensual por sector, reporte de reposición, envío de mails (automáticos 07:30 y manuales).
3. **Salida de activos** — seguimiento de equipos/repuestos que salen de planta y su reingreso (días fuera, sector, estado, etc.).
4. **Configuración y datos** — carga del maestro, edición de artículos, sincronización a Firebase ("Actualizar App Pañol"), gestión de correos, importación/actualización semanal del stock.

Lógica transversal: búsqueda avanzada, cálculo de críticos/reposición, clasificación por sector (Producción / Proyectos / Mantenimiento) y por línea (L1–L7 / Pañol), automatización de correos.

**No existe** módulo de usuarios, permisos ni login. Es **mono-usuario** de escritorio. No hay "préstamos/devoluciones" como tal, salvo el flujo salida/reingreso de *Salida de activos*.

### Git / aislamiento
- **NO está en Git.** El versionado es manual: copias fechadas en la carpeta `BACKUP .TXT/` (ej. `almacen_gui_BACKUP_2026-06-23.py`).
- Producción = el `.exe` en `dist/`. Se puede experimentar sobre el `.py` sin afectar al ejecutable en uso.
- **Recomendación:** inicializar un repo Git ya y trabajar en rama para la migración.

### Tests
- **No hay tests automatizados** (ningún archivo de test). Validación 100% manual (compilar + probar).
- **Recomendación:** crear tests sobre la lógica de negocio antes/durante el port (clasificación de sectores, líneas, reposición, agregaciones de gasto).

---

## 2. Base de datos actual

### Motor
- **No hay base de datos relacional.** Los datos viven en **archivos Excel (.xlsx)** locales, leídos/escritos con `pandas`.
- En paralelo, hay una copia en la nube en **Firebase Firestore** (NoSQL documental), usada **solo** para alimentar la app web.
- No hay SQL Server / PostgreSQL / MySQL / Access / Firebird.

### Volumen (verificado)
| Archivo | Contenido | Volumen |
|---|---|---|
| `master_codes.xlsx` | hoja `ARTICULOS` (catálogo) | **6.988 filas** |
| `master_codes.xlsx` | hoja `config` | 21 filas |
| `master_codes.xlsx` | hoja `correos` | 1 fila |
| `master_salidas.xlsx` | movimientos históricos | **1.457 filas** |
| `salidas_DD-MM-AAAA.xlsx` | salidas del día | decenas de filas |
| `salida_activos.xlsx` | seguimiento activos | decenas de filas |
| Firestore `articulos` | catálogo en la nube | ~7.000 documentos |
| Firestore `config/catalogo` | versión del catálogo | 1 documento |

Columnas de `master_salidas.xlsx`: `FECHA, MES, AÑO, CODIGO, DESCRIPCION, CANTIDAD, TIPO_COMPROBANTE, NUMERO_ORDEN, PRECIO_UNITARIO, MONTO_TOTAL_SALIDA, OPERARIO, UBICACION, MAQUINA_SITIO, SECTOR`.

**Es un volumen chico.** Migrar los datos es trivial; el desafío real es portar la lógica.

### Lógica de negocio
- Excel no tiene stored procedures ni triggers.
- **Toda la lógica está en Python** y es lo más importante a migrar:
  - Clasificación de sector según `OPERARIO` (Producción directo; Proyectos = Maccaroni/Valenzuela; resto = Mantenimiento).
  - Desglose por línea de comprobante (L1–L7 / Pañol) para Mantenimiento.
  - Normalización de criticidad: `CRÍTICO` / `ALTA FRECUENCIA` / `BASE`.
  - Cálculo de reposición y de críticos (stock ≤ mínimo).
  - Agregaciones de gasto diario/mensual por sector y por línea.
  - Generación de reportes (Excel con formato + gráficos) y envío de mails.

---

## 3. App "móvil" (en realidad, app WEB)

> Ubicación del código: `C:\Users\Mantenimiento\Desktop\panol_movil\AppPanolWeb`

### Tecnología (verificada)
- **Web app: Vite 6 + React 19 + TypeScript.** SDK `firebase` JS v12.
- Se sirve como sitio web (build con Vite, deploy por Firebase Hosting; `firebase.json` presente). Se usa desde el navegador del celular (responsive), no es app nativa ni Flutter/React Native.
- Proyecto Firebase: `sistemapanol-a1bd4`.
- Usa `xlsx` para **exportar conteos a Excel** desde el navegador.

### ¿API o acceso directo a la base?
- **Acceso DIRECTO a Firestore, sin API intermedia.** No existe backend propio.
- **Lecturas:** `getDocs(collection(db, "articulos"))` con caché persistente (IndexedDB) para minimizar lecturas facturables. Filtrado y búsqueda **en el cliente**.
- **Escrituras:** muy acotadas — solo actualiza el campo `alias` de un artículo (`updateDoc(doc(db,"articulos",id), { alias })`). El resto del catálogo es de solo lectura para la web.
- Funciones de la web: buscar catálogo, artículos recientes, parseo de ubicación, **conteo de stock** (store local + export a Excel), edición de `alias`.

### Contrato de datos hoy (Firestore)
Colección **`articulos`** (id del doc = código):
- Escrito por el **escritorio**: `codigo`, `desc`, `stock`, `ubicacion`, `categoria` (con `merge=True`).
- Escrito por la **web**: `alias`.
- Leído por la web como tipo: `{ id, codigo?, desc?, alias?, stock?, ubicacion? }`.
- **Detalle clave:** el escritorio sincroniza con `merge=True`, por lo que **no pisa el `alias`** que escribe la web. La web no usa `categoria`. Cualquier backend nuevo debe respetar este contrato (no borrar `alias`).

Documento **`config/catalogo`**: campo `version` (timestamp) que el escritorio "bumpea" en cada sync para señalar cambios.

> Nota: `firebaseConfig` está embebido en el cliente web (normal en Firebase web). La seguridad se maneja con **Firestore Rules** (`firestore.rules` / `REGLAS_FIREBASE.txt`). Hoy las reglas están en modo de prueba con vencimiento extendido (RTDB no se usa; la app usa Firestore).

### ¿Se modifica la web en esta etapa o el backend debe ser 100% compatible?
Decisión a tomar (define el esfuerzo):

- **Opción A (recomendada, menor riesgo):** el backend web nuevo sigue escribiendo en Firestore con el **mismo esquema** (`articulos` + `config/catalogo`). La app web **no se toca** y sigue funcionando. Permite migrar el escritorio sin frenar la operación móvil.
- **Opción B (más esfuerzo):** backend nuevo con API propia; se **modifica** la app web para consumirla. Más limpio a futuro, pero implica reescribir parte de la web y coordinar despliegues.

---

## 4. Resumen para la migración

- **Punto de partida ideal:** la app móvil **ya es web** (React + Vite + Firestore). No hay que "crear" la parte móvil desde cero; se puede expandir.
- **Fuente de verdad hoy:** Excel local (escritorio) → Firestore (espejo para la web).
- **Riesgo principal:** la concurrencia con Excel y la lógica de negocio embebida en `almacen_gui.py`.
- **Camino sugerido:**
  1. Inicializar Git y crear tests de la lógica de negocio.
  2. Definir la base de datos destino (recomendado: una DB real como Postgres/Firestore como fuente de verdad; Excel queda como import/export).
  3. Portar la lógica de negocio a un backend/servicios (un módulo por dominio: salidas, reportes, activos, catálogo/config).
  4. Mantener el contrato Firestore para no romper la app web existente (Opción A).
  5. Migrar pestaña por pestaña a vistas web, reutilizando la app React actual como base del front.
