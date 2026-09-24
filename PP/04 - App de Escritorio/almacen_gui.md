# almacen_gui — App de escritorio

**Estado:** ✅ En uso en producción — **proyecto separado, NO tocar** hasta integración web  
**Última actualización:** 2026-07-08

## Documentación en este vault
- [[Sistema Pañol - Índice]]
- [[Changelog 2026-07-08]]
- [[Correos automáticos - tipos]]
- [[Precios - propagación a movimientos]]
- [[Registro de salidas - flujo de carga]]
- [[Ultima actualizacion stock]]

## Rutas

| Ubicación | Descripción |
|-----------|-------------|
| `C:\Users\Mantenimiento\Desktop\LABORATORIO BASE\almacen_gui.py` | Código fuente de desarrollo |
| `G:\Unidades compartidas\...\pañol v5.0\` | Carpeta operativa con `.exe`, Excel y datos |
| `AppWebSalidas/app_escritorio_referencia/almacen_gui.py` | Copia de referencia en monorepo (no es producción) |

**Tamaño:** ~4.800 líneas, ~245 KB — monolito en un solo archivo.

## Stack

| Componente | Tecnología |
|------------|------------|
| Lenguaje | Python **3.14** |
| GUI | **Tkinter** |
| Excel | pandas, openpyxl, xlsxwriter |
| Fechas UI | tkcalendar |
| Nube | firebase-admin (Firestore) |
| Mail | smtplib + email (Gmail :587, starttls) |
| Empaquetado | **PyInstaller** → `SistemasPañol.exe` |

## Pestañas funcionales

| Pestaña | Función |
|---------|---------|
| **📦 Registro de salidas** | Descuento stock, precarga salida, confirmación, simulador costos |
| **💸 Reportes** | Gasto diario/mensual por sector, reposición, mails auto (07:30) y manuales |
| **🔧 Salida de activos** | Equipos fuera de planta, reingreso, días fuera, mail recordatorio |
| **⚙️ Configuración y datos** | Carga maestro, edición artículos, sync Firebase, correos, import stock, **Última actualización** |

**Transversal:** búsqueda avanzada, críticos/reposición, clasificación sector/línea, automatización correos.

**No hay:** usuarios, permisos ni login — mono-usuario.

## Lógica de negocio crítica (preservar en migración)

| Regla | Detalle |
|-------|---------|
| Clasificación sector | Por `OPERARIO`: Producción directo; Proyectos = Maccaroni/Valenzuela; resto = Mantenimiento |
| Líneas Mantenimiento | L1–L7 / Pañol según tipo comprobante |
| Criticidad | `CRÍTICO` / `ALTA FRECUENCIA` / `BASE` |
| Reposición | Stock ≤ mínimo → críticos |
| Gastos | Agregaciones diarias/mensuales por sector y línea |
| Firebase sync | `merge=True` en `articulos`; bump `config/catalogo.version` |
| SMTP | Fila 1 hoja `correos`: remitente + password |

## Archivos Excel

| Archivo | Contenido | Volumen |
|---------|-----------|---------|
| `master_codes.xlsx` / `base_datos.xlsx` | hoja `ARTICULOS` | **6.988 filas** |
| `master_codes.xlsx` | hoja `config` | 21 filas |
| `master_codes.xlsx` | hoja `correos` | ⚠️ verificar filas actuales (doc 2026-06-24 decía 1 fila; API leyó 9 contactos en 2026-06-26) |
| `master_salidas.xlsx` | Movimientos históricos | **1.457 filas** |
| `salidas_DD-MM-AAAA.xlsx` | Salidas del día | decenas |
| `salida_activos.xlsx` | Seguimiento activos | decenas |
| `importar_stock/` | Importación semanal | carpeta |
| `ultima_actualizacion_stock.log` | Reporte detallado última importación | 1 archivo |

Columnas `master_salidas`: FECHA, MES, AÑO, CODIGO, DESCRIPCION, CANTIDAD, TIPO_COMPROBANTE, NUMERO_ORDEN, PRECIO_UNITARIO, MONTO_TOTAL_SALIDA, OPERARIO, UBICACION, MAQUINA_SITIO, SECTOR.

## Firebase

- Credenciales: `serviceAccountKey.json` junto al exe
- Colección `articulos` ~7.000 docs
- Botón "Actualizar App Pañol" / sync incremental

## Git y backups

| Aspecto | Estado |
|---------|--------|
| Git | **Sin Git** — backups manuales en `BACKUP .TXT/` (ej. `almacen_gui_BACKUP_2026-07-08.py`) |
| Producción | `.exe` en `dist/` |
| Tests | **Ninguno** — validación 100% manual |

## Relación con monorepo web

- El monorepo **no modifica** el ejecutable en uso
- Servicios web reutilizan patrones (SMTP, Excel correos, estilo HTML mail)
- Migración planificada pestaña por pestaña → ver [[01 - Estado del Proyecto/Roadmap]]

## Referencias

- [[03 - Documentacion Tecnica/CONTEXTO_TECNICO_MIGRACION]]
- `LABORATORIO BASE/firestore.rules`
- `LABORATORIO BASE/REGLAS_FIREBASE.txt`
