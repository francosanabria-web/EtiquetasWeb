# APIs del monorepo AppWebSalidas

**Última actualización:** 2026-08-07

Resumen de microservicios con endpoints HTTP.

## Mapa de puertos

| Servicio | Puerto | Framework |
|----------|--------|-----------|
| **kpis** | **8001** | Starlette |
| etiquetas-api | **8010** | FastAPI |
| minutas-api (legado) | **8012** | FastAPI |
| **minuta_reunion (shell)** | **8013** | Starlette |
| **solicitudes (shell)** | **8014** | Starlette |
| **usuarios (shell)** | **8015** | Starlette |
| **activos (shell)** | **8016** | Starlette |
| **reportes (shell)** | **8017** | Starlette |
| **salidas (shell)** | **8018** | Starlette |
| email_service | **8020** | Starlette |
| etiquetas-web | 5173 | Vite (frontend) |
| minutas-web | 5175 | Vite (frontend) |
| shell | 5180 | Vite (frontend) |

---

## etiquetas-api

Base: `http://localhost:8010`

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/catalogo/{codigo}` | Artículo desde caché Firestore |
| GET | `/catalogo/estado` | Estado sincronización |
| POST | `/etiquetas` | Encolar impresión (`simple` \| `codigo` \| `mercaderia_nueva`) |
| GET | `/etiquetas/pendientes` | Pendientes (print-agent) |
| POST | `/etiquetas/{id}/confirmar` | Confirmar impreso/error |

### Tipos de pedido (`POST /etiquetas`)

| `tipo` | Campos obligatorios | Notas |
|--------|---------------------|-------|
| `simple` | `texto_libre` | Opcional: `escala_fuente` (0.5–4), `cantidad` |
| `codigo` | `codigo`, `descripcion`, `ubicacion`, `qr_data` | Frontend resuelve vía `/catalogo` |
| `mercaderia_nueva` | mismos que `codigo` | Campos manuales; **sin** lookup de catálogo. Print-agent usa la misma plantilla que `codigo`. |

---

## minutas-api

Base: `http://localhost:8012`

| Área | Endpoints (resumen) |
|------|---------------------|
| Health | GET `/health` |
| Sesiones | CRUD `/sesiones`, detalle, cierre |
| Solicitudes | CRUD `/solicitudes` |
| Temas | CRUD `/temas` |
| Import | POST `/import/excel` |
| Mail | POST `/mail/preview`, POST `/mail/enviar` |
| Entregas | POST entregas parciales |

Detalle completo en `services/minutas-api/main.py` y README del servicio.

---

## minuta_reunion (shell, :8013)

**Última actualización sección:** 2026-07-22

Base: `http://localhost:8013` — proxy Vite `/api/minuta`. Persistencia SQLite (`backend/minuta_reunion/data/minutas.db`) + export JSON por sector.

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/api/minuta/sectores` | Lista de sectores |
| GET | `/api/minuta/pedidos?sector=&activos=1\|0` | Pedidos (`1`=activos, `0`=todos) |
| POST | `/api/minuta/pedidos` | Crear pedido |
| POST | `/api/minuta/pedidos/reordenar` | Reordenar `{sector, ids[]}` |
| POST | `/api/minuta/pedidos/limpiar-consultas` | Vacía consultas del sector (al enviar mail) |
| GET | `/api/minuta/pedidos/{id}` | Detalle con novedades y movimientos |
| PATCH | `/api/minuta/pedidos/{id}` | Editar campos |
| DELETE | `/api/minuta/pedidos/{id}` | Eliminar pedido |
| POST | `/api/minuta/pedidos/{id}/novedades` | Insertar novedad (histórica / append) |
| PUT | `/api/minuta/pedidos/{id}/novedades` | Upsert novedad de la fecha de reunión (sync multi-PC; texto vacío borra) |
| POST | `/api/minuta/pedidos/{id}/finalizar` | `activo=0` + estado completado (mismo sector) |
| POST | `/api/minuta/pedidos/{id}/reactivar` | Vuelve a activos |
| GET | `/api/minuta/reuniones?owner=&sector=&enviadas=1&archivadas=0\|1\|all` | Listado (visibles para usuario demo) |
| POST | `/api/minuta/reuniones` | Crear tipada o obtener/crear legacy |
| GET | `/api/minuta/reuniones/{id}` | Detalle reunión |
| PATCH | `/api/minuta/reuniones/{id}` | Título, fecha, notas, archivada, visibilidad, sector, mail enviado, etc. |
| DELETE | `/api/minuta/reuniones/{id}` | Eliminar; pedidos → Histórico del sector |
| POST | `/api/minuta/reuniones/mover-pedidos` | Body `{origen_id, destino_id}` — mueve todos los pedidos (recuperación desde Histórico) |
| GET | `/api/minuta/novedades-reunion?sector=&fecha=` | Novedades de una fecha |

Campos `pedidos`: `importancia`, `estado`, `consultas`, `orden`, `activo`.

Campos `reuniones`: `titulo`, `tipo` (`semanal`/`diaria`/`ocasion`), `visibilidad` (`individual`/`compartida`), `owner_email`, `sectores_comprometidos`, `archivada`, `sector`.

---

## solicitudes (shell, :8014)

**Última actualización sección:** 2026-07-24

Base: `http://localhost:8014` — proxy Vite `/api/solicitudes`. **Fuente de verdad: Excel en Drive** `G:\...\pañol v5.0\solicitudes_pedidos.xlsx` (hojas `PEDIDOS` + `CONTADORES`); adjuntos en `solicitudes_adjuntos\`. Catálogos: `CATALOGOS_EDITABLES.json`. (El SQLite quedó solo como origen de migración inicial.)

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/api/solicitudes/catalogos` | Estados, tipos, áreas, cuentas, unidades, **proveedores** (sugerencias) |
| GET | `/api/solicitudes/resumen` | Totales por estado / urgentes / TR |
| GET | `/api/solicitudes?tipo=&estado=&q=` | Listado (`tipo=pedidos` = normal+urgente; `tipo=tr`) |
| POST | `/api/solicitudes` | Crear. Normal/Urgente → `n_pedido` `P-####` auto; TR → `n_tr` `TR-####` auto + **proveedor obligatorio** |
| GET | `/api/solicitudes/{id}` | Detalle |
| PATCH | `/api/solicitudes/{id}` | Actualizar. `proveedor`/`remito_nro`/`presupuesto_nro`/`estado` los edita cualquier rol con escritura; `n_pedido` solo admin/pañol |
| DELETE | `/api/solicitudes/{id}?rol=admin` | Borrar pedido (solo admin) |
| POST | `/api/solicitudes/upload` | Multipart `file` + `kind` → path relativo |
| GET | `/api/solicitudes/archivos/{name}` | Descargar archivo subido |
| GET | `/api/solicitudes/{id}/pdf` | PDF de la solicitud (cabecera con proveedor + tabla de ítems) |
| GET | `/api/solicitudes/{id}/excel` | Excel de la solicitud (plantilla prolija) |

Modelo: cabecera del pedido (con `proveedor`) + ítems (código opcional, descripción, cantidad, unidad, área/máquina libre, imagen). Esquema del Excel: [[03 - Documentacion Tecnica/Base_de_Datos/Solicitudes_Excel]].

Ver [[02 - Módulos/Solicitud_Pedidos]].

---

## usuarios (shell, :8015)

**Última actualización sección:** 2026-07-29

Base: `http://localhost:8015` — proxy Vite `/api/usuarios`. SQLite local `backend/usuarios/data/usuarios.db` (no se versiona). Contraseñas **PBKDF2-HMAC-SHA256 + salt**; sesión por **token opaco con vencimiento** (12 h). La gestión requiere sesión de un usuario **admin** (token en header `Authorization: Bearer <token>`). MVP en LAN: los demás servicios aún confían en la red interna.

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/api/usuarios/catalogo` | Módulos, roles, niveles y plantillas de permisos por rol |
| POST | `/api/usuarios/login` | `{usuario, clave}` → `{token, usuario}` |
| POST | `/api/usuarios/logout` | Cierra la sesión del token |
| GET | `/api/usuarios/me` | Usuario + permisos de la sesión |
| POST | `/api/usuarios/mi-password` | `{actual, nueva}` — cambio propio |
| GET | `/api/usuarios` | Listado (admin) |
| POST | `/api/usuarios` | Crear (admin) `{usuario, nombre, clave, rol, permisos?}` |
| PATCH | `/api/usuarios/{id}` | Editar nombre/rol/activo/permisos (admin) |
| POST | `/api/usuarios/{id}/password` | Resetear contraseña (admin) |
| DELETE | `/api/usuarios/{id}` | Eliminar usuario (admin) |

Permisos: matriz por usuario `modulo → sin_acceso|consulta|escritura`, sembrada de la plantilla del rol al crear. Salvaguarda: siempre debe quedar al menos un admin activo. Esquema: [[03 - Documentacion Tecnica/Base_de_Datos/Usuarios_Esquema]].

Ver [[02 - Módulos/Usuarios]].

---

## activos (shell, :8016)

Base: `http://localhost:8016`  
Proxy Vite: `/api/activos` → `:8016`.

Lectura **solo lectura** de `salida_activos.xlsx` (hojas `FUERA_DE_PLANTA` + `INGRESADO_A_PLANTA`). Independiente de KPIs.

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/health` | Estado carga / archivo |
| GET | `/api/activos/health` | Alias |
| GET | `/api/activos/resumen` | Cards + `lista_fuera` + `lista_ingresados` + por sector (`id` tipo `f-N`) |
| POST | `/api/activos/refresh` | Recarga Excel |
| POST | `/api/activos/marcar-regreso` | Body: `{ ids, fecha_regreso, estado_al_ingreso }` → mueve a ingresados |
| POST | `/api/activos/restablecer-fuera` | Body: `{ ids }` (`i-N`) → vuelve a fuera |
| POST | `/api/activos/reescribir-formato` | Reescribe Excel con formato escritorio (sin cambiar filas) |
| GET | `/api/activos/export.xlsx?vista=fuera\|ingresados` | Export Excel según pestaña |
| GET | `/api/activos/export.pdf?vista=fuera\|ingresados` | Export PDF según pestaña |

Ver [[02 - Módulos/Activos]].

---

## reportes (shell, :8017)

**Última actualización sección:** 2026-08-07

Base: `http://localhost:8017`  
Proxy Vite: `/api/reportes` → `:8017`.

Consultas operativas de movimientos (distinto de KPIs). Lee **`master_salidas.xlsx` de producción** (solo lectura; mismo path que KPIs). Overrides: `REPORTES_MOVIMIENTOS_FILE`, `REPORTES_DATA_PATH`, `KPIS_DATA_PATH`, `SALIDAS_DATA_PATH`. Store intercambiable para Salidas/SQL.

Export Excel Table = layout detalle del mail diario de gastos + `SECTOR`:
`FECHA, CODIGO, DESCRIPCION, CANTIDAD, PRECIO_UNITARIO, MONTO_TOTAL_SALIDA, TIPO_COMPROBANTE, NUMERO_ORDEN, MAQUINA_SITIO, OPERARIO, SECTOR`.

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/health` | Estado carga / path / filas |
| GET | `/api/reportes/health` | Alias |
| GET | `/api/reportes/movimientos` | Listado filtrado (`fecha_desde/hasta`, `sector`, `operario`, `codigo`, `numero_orden`, `tipo_comprobante`, `q`, `limite`, `offset`) |
| GET | `/api/reportes/resumen` | Totales + por sector/operario/comprobante/mes |
| GET | `/api/reportes/filtros` | Combos (sectores, operarios, tipos, rango fechas) |
| POST | `/api/reportes/refresh` | Recarga archivo (solo lectura) |
| GET | `/api/reportes/export.xlsx` | Excel Table (openpyxl `TablaGastos`) |
| GET | `/api/reportes/export.csv` | Deprecated — preferir xlsx |
| GET | `/api/reportes/mail/status` | Flags mail (sin enviar; defaults ENABLED=0) |
| POST | `/api/reportes/mail/diario/dry-run` | Arma preview sin SMTP |
| POST | `/api/reportes/mail/diario` | Envía solo si `REPORTES_MAIL_DIARIO_ENABLED=1` |
| POST | `/api/reportes/mail/mensual` | Envía solo si `REPORTES_MAIL_MENSUAL_ENABLED=1` |

Ver [[02 - Módulos/Reportes]].

---

## salidas (shell, :8018)

**Última actualización sección:** 2026-08-07

Base: `http://localhost:8018` — proxy Vite `/api/salidas` → `:8018`.

Egreso de material del pañol. **Prueba avanzada (2026-08-07):**
- **Lee** `master_codes.xlsx` del pañol (solo lectura) — artículos + hoja `config` (comprobantes/sectores/operarios).
- **Escribe** en `…\pañol v5.0\salidas_web\` (`master_salidas.xlsx` + `salidas_DD-MM-AAAA.xlsx`).
- **No** escribe `master_codes` / `master_salidas` de producción ni Firestore al confirmar (`SALIDAS_FIREBASE_WRITE=0` por default).
- Health incluye `path`, `path_escritura`, `path_historial`, `maestro_writable`.

Env: `SALIDAS_MAESTRO_PATH`, `SALIDAS_WEB_PATH` / `SALIDAS_DATA_PATH`, `SALIDAS_PANOL_PATH`. Fallback local: `backend/salidas/data_prueba/`.

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/health` | Estado + paths + `maestro_writable` + firebase |
| GET | `/api/salidas/health` | Alias |
| GET | `/api/salidas/catalogos` | Comprobantes, sectores, mapa sector→operarios |
| GET | `/api/salidas/articulo/{codigo}` | Buscar artículo en maestro |
| POST | `/api/salidas/proyectar` | Body: `{codigo, cantidad, es_devolucion?, pendientes[]}` |
| POST | `/api/salidas/confirmar` | Body: `{items[], forzar_negativos?}` — batch → `salidas_web` |
| POST | `/api/salidas/devolucion` | Body: `{items[]}` — fuerza cantidades negativas |
| GET | `/api/salidas/movimientos?desde=&hasta=&limite=` | Lectura historial (`salidas_web`) |
| POST | `/api/salidas/refresh` | Recarga maestro Excel |
| POST | `/api/salidas/sync-firebase` | Forzar pull Firestore → caché |

Helpers de lectura para Reportes: `backend/salidas/movimientos.py`.

Ver [[02 - Módulos/Salidas]].

---

## kpis-api

Base: `http://localhost:8001`

Lectura **solo lectura** de Excel en `G:\...\pañol v5.0\`. Caché en memoria; `GET /api/kpis/refresh` recarga.

`GET /api/kpis/health` (y `/health`): `estado` = `ok` \| `cargando` \| `parcial` \| `error`. `parcial` = maestro OK pero `master_salidas` u otro archivo ilegible; puede incluir `avisos[]`. Archivos se marcan OK solo si el xlsx es zip válido (no basta con existir / 0 bytes).

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/kpis/health` | Estado + archivos accesibles + sectores (+ `avisos` si parcial) |
| GET | `/api/kpis/refresh` | Fuerza recarga desde disco |
| GET | `/api/kpis/stock/resumen` | Totales stock, bajo mínimo, valorizado, por criticidad |
| GET | `/api/kpis/stock/bajo-minimo` | Lista bajo mínimo (`?criticidad=CRÍTICO` opcional) |
| GET | `/api/kpis/stock/en-cero` | Top artículos stock cero (`?top=20`) |
| GET | `/api/kpis/consumo/mensual` | Gasto por mes (`?meses=12`) |
| GET | `/api/kpis/consumo/por-sector` | Gasto por sector (`?mes=YYYY-MM`, default mes actual) |
| GET | `/api/kpis/consumo/por-linea` | Gasto por línea L1–L7/Pañol solo Mantenimiento |
| GET | `/api/kpis/consumo/top-articulos` | Top por monto y cantidad (`?mes=&top=10`) |
| GET | `/api/kpis/consumo/tendencia-anual` | Serie 12 meses × sector |
| GET | `/api/kpis/reposicion/resumen` | Artículos a reponer + valor |
| GET | `/api/kpis/activos/*` | ⚠️ Legacy — preferir servicio `:8016` |
| GET | `/health` | Alias de health |

Ver [[03 - Documentacion Tecnica/Backend/KPIs_Service]] (pendiente) o `backend/kpis/`.

---

## email_service

Base: `http://localhost:8020`

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/api/email/contacts` | Lista contactos |
| POST | `/api/email/send` | Envío genérico |

Ver [[03 - Documentacion Tecnica/Backend/Email_Service]].

---

## print-agent

No expone HTTP — **polling** a etiquetas-api:

- GET `/etiquetas/pendientes`
- POST `/etiquetas/{id}/confirmar`

---

## Firestore (AppPanolWeb)

Sin API REST — acceso directo SDK cliente. Ver [[03 - Documentacion Tecnica/Frontend/AppPanolWeb]].

---

## CI (GitHub Actions)

`.github/workflows/ci.yml`:

- `services/etiquetas-api` → `test_etiquetas.py`
- `services/minutas-api` → `test_minutas.py`

## ⚠️ Pendiente de verificar

- OpenAPI/Swagger URLs en producción LAN (FastAPI las expone en dev)
