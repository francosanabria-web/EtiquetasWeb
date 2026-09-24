# Activos fuera de planta

**Estado:** 🔄 En desarrollo (web Fase 2 OK; Fase 3 pendiente) / ✅ Funcionando (escritorio)  
**Última actualización:** 2026-08-07

## Qué hace

Centraliza el seguimiento de equipos/repuestos fuera de planta: días fuera, sector, proveedor, estado y trazabilidad por número de remito/pedido/OC.

## Cambios 2026-08-01 — Fase 1 + Fase 2

### Fase 1 (lectura)
- **Servicio propio** `backend/activos` puerto **8016** (independiente de KPIs `:8001`).
- Lee **ambas hojas** de `salida_activos.xlsx`: `FUERA_DE_PLANTA` e `INGRESADO_A_PLANTA`.
- UI: cards, tabs, filtros, badges, dark, layout ancho; insights antigüedad + top proveedores.

### Fase 2 (marcar regreso + restablecer + formato)
- `POST /api/activos/marcar-regreso` y `POST /api/activos/restablecer-fuera`.
- Escritura Excel con **lock** + `.tmp` + `.bak`.
- Formato Excel = escritorio (`xlsxwriter`: encabezado azul, bordes, fechas `dd/mm/yyyy`, colores por días en FUERA, autofilter, freeze).
- `POST /api/activos/reescribir-formato` reaplica formato sin cambiar datos.
- UI: checkboxes; en Fuera → Marcar regreso; en Ingresados → Restablecer a fuera.
- ⚠️ No editar el mismo Excel en escritorio y web a la vez.

## UX móvil (2026-08-07)

- En el shell: módulo incluido en **bottom quick nav** (campo).
- Listado: vista en **cards** por debajo de **768px** (`activos.css`) — checkbox, equipo, días, sector, proveedor.
- Desktop: tabla/layout previos sin cambio de comportamiento de colapso del sidebar.

## Web (shell)

Ruta: `/activos` en `apps/web`.

Incluye:

- Cards: fuera, promedio días, críticos (>30), ingresados.
- Tabs **Fuera | Ingresados**, búsqueda y filtro por sector.
- Colores por antigüedad (umbrales mail escritorio): ≤21 / 22–30 / >30.
- Export PDF/Excel (vista fuera).
- Modo oscuro alineado a variables del shell.

## Fuente de datos

- Archivo: `salida_activos.xlsx` en carpeta pañol v5.0 (`G:\...`).
- Servicio: `backend/activos` `:8016`.
- Env: `ACTIVOS_DATA_PATH` (opcional; fallback `KPIS_DATA_PATH`).

## Troubleshooting

- Error al abrir `/activos`: verificar `estado_panol.ps1` → Activos (:8016). Crear venv una vez con `scripts\_start_activos.bat` si el supervisor dice SKIP.
- Requisito: unidad `G:` montada con `salida_activos.xlsx`.

## Pendientes de este módulo

### Fase 3 (orden acordado)
1. **Editar** ítems aún fuera de planta.
2. **Alta nueva** de salida (CTA "Registrar salida" solo cuando la escritura esté lista).
- Restablecer a fuera: ya hecho en Fase 2.

### Fase 4
- Auditoría de cambios.
- Mail diario desde web; un solo dueño (apagar solo el bloque activos del `.exe` 07:30).
- Marcador anti-duplicado compartido con escritorio.

### UX
- Rediseñar indicador L1–L7 (retirado 2026-08 por poco claro).


## Indicador L1–L7 (ingresados)

⚠️ Retirado de la UI (poco claro). Queda pendiente rediseñar una vista más entendible por línea de producción.

## Notas

- El escritorio sigue con la pestaña (contingencia); operación diaria prevista en web tras fases de edición.
- Un solo dueño del mail diario de seguimiento para no duplicar envíos.
