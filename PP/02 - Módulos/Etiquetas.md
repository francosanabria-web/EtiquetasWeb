# Etiquetas

**Estado:** ✅ Funcionando  
**Última actualización:** 2026-08-05

## Qué hace

Permite imprimir rótulos desde cualquier PC de la red del pañol:

- **Código** — búsqueda en catálogo (descripción, ubicación).
- **Mercadería nueva** — misma plantilla que código, pero campos manuales (sin master_codes / Firebase).
- **Rótulo simple** — texto libre con tamaño de letra ajustable y vista previa a escala real (50×20 mm).

La impresión la ejecuta un agente en la PC conectada a la impresora. Tras cada envío exitoso se guarda un **buffer de última impresión** en `localStorage` para rellenar o reimprimir sin volver a tipear.

**UI (2026-08-04):** sin campo «¿Quién imprime?» — `solicitado_por` fijo silencioso `"etiquetas-web"`. Tema claro/oscuro con toggle en el header, persistido en `localStorage` (`etiquetas_theme`). Estética alineada con AppPanolWeb (búsquedas).

## Cómo funciona (técnico)

| Componente | Ruta | Puerto |
|------------|------|--------|
| Web UI | `AppWebSalidas/services/etiquetas-web` | **5173** |
| API | `AppWebSalidas/services/etiquetas-api` | **8010** |
| Print agent | `AppWebSalidas/services/print-agent/print_agent_api.py` | polling → API |
| Supervisor | `AppWebSalidas/scripts/supervisor_impresion.ps1` | autostart PC impresora (tarea `RedImpresionPanol`) |

> El portal (KPIs/Minuta/etc.) tiene supervisor **aparte** (`PortalPanol` / `supervisor_panol.ps1`) y no controla impresión.

**Stack:** React + Vite (web), FastAPI + SQLite cola + Firestore lectura (API), Python (agent).

**Flujo:** Usuario encola en web → API guarda en `cola.db` (SQLite) → print-agent consulta pendientes → imprime → confirma resultado.

**Catálogo:** Firestore colección `articulos` — **solo lectura** vía `firebase_lectura.py` (listener diario + caché SQLite + índice en memoria). Solo lo usa el modo **Código**; mercadería nueva **no** llama a `/catalogo`.

**Regla dura:** el endpoint HTTP `GET /catalogo/{codigo}` **se mantiene**, pero **nunca** debe llamar a Firestore `.get()` / `where()` — solo lee memoria (ver incidente abajo).

**Shell:** enlace externo configurado con `VITE_ETIQUETAS_URL` (ej. `http://10.1.102.8:5173`). No se tocó nav del shell en 2026-08-04 (sigue siendo externo).

Runbook: `AppWebSalidas/COMO_IMPRIMIR.txt`

## Incidente — cuota Firestore (fin junio 2026)

**Síntoma (producción LAN):** al buscar códigos, mensaje *"Cuota de lecturas de Firebase agotada"*. Firestore respondía **429 ResourceExhausted**. Las etiquetas **simples** seguían funcionando (no usan catálogo).

**Causa real (no confundir con HTTP GET):**
- El problema **no** fue el método HTTP `GET`.
- Era que `buscar_catalogo` hacía lecturas Firestore **en cada búsqueda**: `document(...).get()` + fallback `where(codigo==...)`.
- Además, un warmup al arrancar la API disparaba más lecturas.
- Eso quemó la cuota gratuita/diaria → 429 → UI con mensaje de cuota.

**Fix (commits):**
1. **`a5a29e1` (2026-06-27)** — mitigación corta: caché en memoria + menos golpes a FS + mensaje 503 claro.
2. **`2da1b20` (2026-06-29)** — solución final: sync diaria con `on_snapshot` → SQLite + índice en memoria; `GET /catalogo/{codigo}` **solo memoria** (0 lecturas FS por búsqueda). Reinicio el mismo día → carga SQLite sin releer Firestore.

**Estado actual:** documentado en docstring de `services/etiquetas-api/firebase_lectura.py` y en `COMO_IMPRIMIR.txt` (~líneas 120–127). Chat de referencia: agent transcript `5c545e2f-cee6-4423-84b3-6d176611d098`. Decisión en [[01 - Estado del Proyecto/Decisiones]].

**Lección para otros módulos (p. ej. Salidas):** mismo patrón — pull/listener ≤1×/día → caché local; endpoints de búsqueda HTTP GET locales; **nunca** `.get()` por request.

## Mejoras 2026-08-04

1. **Buffer última impresión** (`ultimaImpresion.ts` + barra en UI): `Usar última` / `Reimprimir último`.
2. **Preview realista rótulo simple**: caja aspect 5:2 (50×20 mm), fuente relativa a la altura; aviso visual si el texto desborda al subir la escala.
3. **Tipo `mercaderia_nueva`**: POST `/etiquetas` con campos manuales; print-agent renderiza igual que `codigo`.
4. **Sin «¿Quién imprime?»**: se quitó la UI; `solicitado_por` fijo `"etiquetas-web"` (API lo acepta opcional; se limpia clave legacy `solicitado_por` en `localStorage` si existía).
5. **Tema claro/oscuro** + identidad AppPanolWeb: tokens en `index.css`, `data-theme` en `<html>`, persistencia `etiquetas_theme`, toggle en header.

## Endpoints / API

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/health` | Estado del servicio |
| GET | `/catalogo/{codigo}` | Resuelve código en caché Firestore |
| GET | `/catalogo/estado` | Estado sync del catálogo |
| POST | `/etiquetas` | Encola pedido (`simple` \| `codigo` \| `mercaderia_nueva`) |
| GET | `/etiquetas/pendientes` | Lista pendientes (print-agent) |
| POST | `/etiquetas/{id}/confirmar` | Confirma impreso/error |

## Pendientes de este módulo

- Integrar al shell central (ruta interna en lugar de link externo)
- Migrar cola SQLite → MariaDB (previsto en `cola_repo.py`)
- Archivar prototipo legacy `prueba_etiquetas_1/` (cola en Firestore)

### Hecho (UI / identidad)
- [x] Paralelizar diseño visual de `etiquetas-web` con el sistema de pañol (tema claro/oscuro + identidad AppPanolWeb) — 2026-08-04

### Próximos pasos — puente desde buscador (AppPanolWeb) — 2026-08-04

> Anotado tras consulta; **no implementar aún**. Backlog: [[01 - Estado del Proyecto/Pendientes]]. Cruzado: [[03 - Documentacion Tecnica/Frontend/AppPanolWeb]].

1. **etiquetas-web — deep link / query params**  
   Leer params para prellenar etiqueta tipo `codigo`: `tipo`, `codigo`, `descripcion`, `ubicacion`, `qr_data`. Opcional `auto=1` para enviar a imprimir al abrir. Hoy la UI **no** lee query params.

2. **AppPanolWeb — botón “Imprimir etiqueta”**  
   En resultados del buscador, abrir la URL de etiquetas-web con `codigo`, `descripcion` (= campo Firestore `desc`), `ubicacion` (fallback si vacía, ej. `SIN UBICAR`).  
   ⚠️ Requiere permiso explícito del usuario: frase exacta **"modificar AppPanolWeb"** (regla permanente del vault / Cursor).

3. **Obstáculo producción (mixed content)**  
   AppPanolWeb en HTTPS (Vercel) **no** puede `POST` directo a la API LAN HTTP. Preferir deep link a etiquetas-web HTTP en LAN. POST directo solo viable en LAN/local o con proxy HTTPS a futuro.

4. **Payload API de referencia**  
   `POST /etiquetas` tipo `codigo` con `codigo`, `descripcion`, `ubicacion`, `qr_data` (=codigo); opcionales `cantidad`, `solicitado_por`.

## Notas

- Prototipo antiguo `prueba_etiquetas_1/` usaba cola en Firestore — **supersedido** por arquitectura actual.
- CI ejecuta `test_etiquetas.py` en GitHub Actions.
