# Solicitud de pedidos

**Última actualización:** 2026-08-05

## Resumen

Módulo del shell Sistemas Pañol para cargar pedidos **Normal / Urgente** y **TR** (Trabajo Realizado). Un pedido puede incluir **varios ítems** (con o sin código). Se descarga en **PDF o Excel**. Por ahora dentro del portal local; más adelante se publicará como servicio externo (URL) para la otra app de Mantenimiento.


## Nota 2026-08-05 — Import historial

- Se analizó importar el historial de pedidos viejos a la planilla operativa editable.
- **Decisión:** merge/import al Excel canónico; **no** pestaña Historial solo lectura.
- **Estado:** sin código de importación; mañana confirmar decisiones bloqueantes y seguir con dry-run + import.

## Cambios 2026-07-24

- **Fuente de verdad = Excel en Drive** (`G:\...\pañol v5.0\solicitudes_pedidos.xlsx`), igual que la app de escritorio. Todas las PC leen/escriben el mismo archivo → los datos no se pierden al actualizar el programa (lección del incidente de minutas). Ya **no** se usa SQLite como base viva; el SQLite viejo se migra una vez al Excel.
- **Nº de pedido automático `P-####`** (arranca en `P-0001`) para Normal/Urgente. TR conserva su `TR-####`. Contadores compartidos en la hoja `CONTADORES` del Excel.
- **Proveedor**: campo nuevo (texto libre con sugerencias que aprende de lo cargado). **Obligatorio en TR.**
- **Remito y presupuesto** los puede cargar/editar **cualquier usuario** (desde el detalle).
- **Panel TR** muestra a simple vista: Descripción, Máquina/línea, Cantidad, Proveedor, Nº presupuesto, Nº remito, Estado.
- **Descargas**: PDF (se quitó la etiqueta «(Compras)») y **Excel** de la plantilla del pedido.

## Rutas código

| Capa | Path |
|------|------|
| Frontend | `apps/web/src/modules/solicitudes/` |
| API client | `apps/web/src/api/solicitudesClient.ts` |
| Catálogo Firestore | `apps/web/src/lib/firebase.ts` + `articulosCatalog.ts` |
| Backend | `backend/solicitudes/` (Starlette :8014) |
| Store Excel | `backend/solicitudes/db.py` (openpyxl, lock + escritura atómica) |
| Export Excel plantilla | `backend/solicitudes/excel_solicitud.py` |
| PDF | `backend/solicitudes/pdf_solicitud.py` |
| Catálogos editables | `backend/solicitudes/CATALOGOS_EDITABLES.json` |

## URL

- Portal: `http://localhost:5180/solicitudes`
- API: `http://localhost:8014` — proxy Vite `/api/solicitudes`

## Datos (Excel fuente de verdad)

- Archivo: `G:\...\pañol v5.0\solicitudes_pedidos.xlsx` (env `SOLICITUDES_EXCEL_PATH` para cambiarlo)
- Hoja **`PEDIDOS`**: una fila por ítem; la cabecera del pedido se repite en cada ítem y se agrupa por `SOLICITUD_ID` al leer. Ver esquema en [[03 - Documentacion Tecnica/Base_de_Datos/Solicitudes_Excel]].
- Hoja **`CONTADORES`**: `id_seq`, `pedido` (P-####), `tr` (TR-####).
- Adjuntos (remito/presupuesto/imágenes): `G:\...\pañol v5.0\solicitudes_adjuntos\` (env `SOLICITUDES_UPLOADS_DIR`).
- Seguridad de escritura: lock de archivo (`.lock`) que coordina varias PC + archivo temporal `.tmp` + copia `.bak` previa. Lectura con caché por fecha de modificación (otra PC ve los cambios al recargar).
- ⚠️ **Import historial pendiente (pausado 2026-08-05):** merge al Excel canónico (no pestaña Historial). Operativo ya en **P-4545+** y **TR-0001..3**. Fuente: `docs/ejemplos/8.Registro solicitudes Pañol@Pedidos 2025.xlsx` (~2564 ítems; hojas Base/PP2026/PDP/TR; ignorar Tabla 26). Faltan decisiones bloqueantes + dry-run + import. Ver [[01 - Estado del Proyecto/Pendientes]].

## Roles

| Rol | Acceso |
|-----|--------|
| admin | Escritura completa + **borrar** pedidos + editar Nº pedido |
| panol | Escritura + editar Nº pedido; sin borrar |
| supervisor | Crear + editar estado / proveedor / remito / presupuesto |
| jefatura | Consulta + PDF/Excel |

> Remito y presupuesto: los puede cargar cualquier usuario con escritura (no está restringido a admin/pañol).

## Pendiente próximo

- [ ] 🔴 **Import historial** → merge a `solicitudes_pedidos.xlsx` (análisis hecho; sin código). Confirmar decisiones bloqueantes → dry-run → import → actualizar `CONTADORES`. Detalle en [[01 - Estado del Proyecto/Pendientes]].
- [ ] URL pública / servicio externo para la otra app de Mantenimiento.
- [ ] Migrar de Excel a **MariaDB/HeidiSQL** (fase siguiente).
- [ ] Auth real / token (:8015) en escritura (hoy LAN).
