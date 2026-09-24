# Salidas

**Estado:** 🔄 En desarrollo (prueba avanzada web) / ✅ Funcionando (escritorio)  
**Última actualización:** 2026-08-07 (UX: sin popup forzar_negativos; placeholders; reset post-carga)

## Qué hace

Registra el **egreso de material del pañol** (no confundir con Activos fuera de planta): busca artículo en el maestro, arma una carga pendiente, al finalizar escribe movimientos.

- **Escritorio (producción hoy):** descuenta stock en `master_codes` + escribe `master_salidas` / diarios en la raíz del pañol; puede sync Firebase.
- **Web (`backend/salidas`):** lee `master_codes` **solo lectura**; escribe **solo** en `salidas_web/`. **No** modifica `master_codes.xlsx` ni `master_salidas.xlsx` de producción. **No** escribe Firestore al confirmar (decisión 2026-08-05; default `SALIDAS_FIREBASE_WRITE=0`).

## Hecho 2026-08-07 (prueba avanzada — rutas planta)

- [x] Buscador / catálogos leen `master_codes.xlsx` del escritorio (hojas `ARTICULOS` + `config`).
- [x] Comprobante, Sector y Operario desde hoja `config` (columnas `comprobantes`, `sector`, `operario` / `operarios`).
- [x] Al confirmar: `salidas_web/master_salidas.xlsx` + `salidas_web/salidas_DD-MM-AAAA.xlsx`.
- [x] Stock del maestro: solo en memoria de sesión (no se persiste en el Excel de producción).
- [x] `_start_salidas.bat` setea rutas de planta; `config.py` también las detecta si existe `G:\...\pañol v5.0`.
- [x] Verificado: health ok, catálogos reales, artículo `K0001FER`, confirm de prueba en `salidas_web`; mtime de `master_codes` / `master_salidas` prod sin cambio.

## Hecho 2026-08-07 (post-prueba — limpieza + formato + UI)

- [x] Limpiadas filas de prueba en `salidas_web` (órdenes 99999/99998, máquina `PRUEBA-WEB` / `PRUEBA-WEB-UTF8`); historial y diario del 07-08 quedan con estructura vacía formateada. No se tocó `master_codes` ni `master_salidas` de producción.
- [x] Escritura Excel web (`excel_io._escribir_excel_atomico`) con estética alineada a diarios de escritorio: cabecera azul `#1F4E78` + texto blanco, anchos de columna, formato `$ #,##0.00` en precios/montos, enteros en AÑO/N° orden, freeze A2 + autofilter.
- [x] UI `/salidas`: labels visibles con `htmlFor`/`id` en Fecha, Código, Cantidad, Comprobante, N° orden, Máquina/sitio, Sector, Operario y toggle Devolución.

## Fix UI 2026-08-07 (labels + toggle Devolución)

- Causa: el CSS global `label { flex-direction: column }` + estilos de `input` (padding/borde) rompían el toggle **Devolución** (checkbox apilado / “corrido”). Los labels del form ya estaban en el TSX; el contraste `--muted` los hacía poco legibles.
- Fix en `apps/web/src/styles/salidas.css`: `.sal-toggle` fuerza `flex-direction: row` y resetea el checkbox; `.sal-field > span` usa color de texto más visible.
- Reiniciados vía supervisor: API Salidas `:8018` + Portal Vite `:5180`. Confirmar en browser con hard refresh (Ctrl+F5).


## UX 2026-08-07 (feedback: alerta / placeholders / reset)

- [x] Eliminado el `window.confirm` técnico al confirmar con stock negativo (texto con `forzar_negativos` / `permitir_stock_negativo`).
- [x] Al ingresar código + cantidad se muestra **en pantalla** el stock proyectado (aviso suave si quedaría negativo); no hay popup nativo en ese paso.
- [x] Al finalizar carga: se fuerza stock negativo automáticamente (como escritorio), sin diálogo de flags de API.
- [x] Placeholders dentro de inputs/selects ("Ingrese…" / "Seleccione…"); sin labels encima de los campos.
- [x] Tras finalizar (o limpiar) se vacían código, cantidad, orden, máquina, comprobante, sector, operario y carga; se conserva fecha del día y catálogos.
- Reiniciar portal `:5180` + hard refresh (Ctrl+F5) para ver cambios.

## UX móvil (2026-08-07)

- En el shell: módulo incluido en **bottom quick nav** (campo).
- Carga pendiente: vista en **cards** en lugar de tabla por debajo de **900px** (`salidas.css` / `SalidasPage`).
- Usa `.btn-secondary` del shell.

## Cómo funciona (técnico)

**Producción hoy (escritorio):** pestaña Registro de salidas en `almacen_gui.py`.

**Web (shell):**
- UI: `apps/web/src/modules/salidas/SalidasPage.tsx` → ruta `/salidas`
- Cliente: `apps/web/src/api/salidasClient.ts`
- Proxy Vite: `/api/salidas` → `:8018`
- Backend: `backend/salidas/` (Starlette)

**Flujo:**
1. Fecha + código → desc / precio / ubicación / stock del maestro (memoria)
2. Cantidad, tipo comprobante, N° orden, máquina (opc), sector, operario
3. Agregar a carga pendiente (proyección de stock con pendientes)
4. Finalizar → escribe historial + diario en `salidas_web` (sin mutar maestro prod; sin write FS)
5. Devolución = cantidad negativa (prefijo `(DEVOLUCIÓN)` en descripción)

### Rutas (planta — doble espacio en `MANTENIMIENTO  OZLA`)

| Rol | Path |
|-----|------|
| Maestro (lectura) | `G:\Unidades compartidas\Mantenimiento\MANTENIMIENTO  OZLA 2024-2025\17. Pañol\pañol v5.0\master_codes.xlsx` |
| Escritura | `…\pañol v5.0\salidas_web\` (`master_salidas.xlsx`, `salidas_DD-MM-AAAA.xlsx`, caché SQLite) |

Env: `SALIDAS_MAESTRO_PATH`, `SALIDAS_WEB_PATH` / `SALIDAS_DATA_PATH`, `SALIDAS_PANOL_PATH`.  
Detalle: `backend/salidas/data_prueba/COMO_APUNTAR_PRODUCCION.md`.

**Capas:**
- IO: `excel_io.py`, `articulos_cache.py`
- Dominio: `store.py`, `service.py`
- Lectura reutilizable por Reportes: `movimientos.py`
- Firebase: `firebase_sync.py` — pull opcional; write al confirmar OFF

## Endpoints / API

Puerto **8018**. Detalle en [[03 - Documentacion Tecnica/Backend/API]].

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/health` | Estado + path maestro + path escritura + `maestro_writable` |
| GET | `/api/salidas/catalogos` | Comprobantes, sectores, operarios |
| GET | `/api/salidas/articulo/{codigo}` | Buscar en maestro |
| POST | `/api/salidas/proyectar` | Stock proyectado |
| POST | `/api/salidas/confirmar` | Batch salida → `salidas_web` |
| POST | `/api/salidas/devolucion` | Batch devolución |
| GET | `/api/salidas/movimientos` | Lectura historial (`salidas_web`) |
| POST | `/api/salidas/refresh` | Recargar maestro |
| POST | `/api/salidas/sync-firebase` | Forzar pull Firestore |

## Cómo probar en la UI

1. Levantar portal + Salidas (`INICIAR_TODO.bat` o `_start_salidas.bat` + Vite :5180).
2. Login con usuario con permiso **escritura** en salidas.
3. Ir a `/salidas`.
4. Buscar un código real del maestro (ej. `K0001FER`).
5. Completar comprobante / orden / sector / operario → Agregar → Finalizar.
6. Revisar archivos nuevos/actualizados en `salidas_web\`.

## Pendientes de este módulo

### Hecho en prueba avanzada 2026-08-07
- [x] Apuntar lectura a `master_codes` real (solo lectura).
- [x] Escribir egresos en `salidas_web` (no prod `master_salidas`).
- [x] Catálogos desde hoja `config`.
- [x] Default `SALIDAS_FIREBASE_WRITE=0`.
- [x] Limpieza filas de prueba en `salidas_web`.
- [x] Formato Excel consolidado (estilo diario escritorio).
- [x] Labels accesibles en formulario UI.

### Siguiente
- [ ] Cablear búsqueda ↔ sync Firestore solo lectura (patrón etiquetas) — aún no alimenta el GET.
- [ ] Credenciales Firebase solo lectura en PC pañol (si se usa pull).
- [ ] ⚠️ Alinear Reportes (:8017) para leer `salidas_web/master_salidas.xlsx` (hoy puede apuntar a `data_prueba`).
- [ ] ⚠️ Decidir cuándo (si alguna vez) el egreso web actualiza stock en `master_codes` / alimenta el historial que usan KPIs (hoy solo `salidas_web`).
- [ ] Auth token (:8015) en escritura API.
- [ ] Buscador F3 / por descripción; simulador de costo.
- [ ] Persistencia MariaDB + Excel export.

## Notas

- En `config` de producción el primer comprobante aparece como **`PAÑ`** (3 caracteres en el Excel), no `PAÑOL`. Se respeta lo leído.
- Puerto **8018** (Reportes ya ocupa **8017**).
- Sin Drive/pañol en `G:\`, cae a `backend/salidas/data_prueba/`.
