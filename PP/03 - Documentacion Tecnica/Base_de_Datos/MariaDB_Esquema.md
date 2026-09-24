# MariaDB — Esquema (planificado)

**Estado:** ⏳ Pendiente — no implementado  
**Última actualización:** 2026-06-26

## Situación actual

- **No hay MariaDB** en el código del monorepo hoy.
- Datos operativos en **Excel** (escritorio) y **SQLite** temporal (colas LAN, minutas).
- Espejo en **Firestore** para app móvil.
- Menciones de migración a MariaDB en:
  - `services/etiquetas-api/cola_repo.py`
  - Decisiones de arquitectura ([[01 - Estado del Proyecto/Decisiones]])

## Objetivo

MariaDB como base **central** en la PC Windows del pañol para:

| Dominio | Origen actual |
|---------|---------------|
| Catálogo artículos | `master_codes.xlsx` hoja ARTICULOS |
| Movimientos / salidas | `master_salidas.xlsx`, `salidas_*.xlsx` |
| Config / correos | hoja `config`, `correos` |
| Cola etiquetas | SQLite `cola.db` |
| Minutas históricas | SQLite `minutas.db` |
| Activos fuera planta | `salida_activos.xlsx` |

Firestore sigue como **capa de sync** hacia AppPanolWeb (Opción A).

## Esquema propuesto (borrador — ⚠️ no validado)

### `articulos`

| Columna | Tipo | Notas |
|---------|------|-------|
| codigo | VARCHAR PK | |
| descripcion | TEXT | |
| stock | DECIMAL | |
| ubicacion | VARCHAR | |
| categoria | VARCHAR | |
| importancia | ENUM | CRÍTICO / ALTA FRECUENCIA / BASE |
| alias | VARCHAR | sync desde Firestore |
| updated_at | DATETIME | |

### `movimientos_salida`

Basado en columnas de `master_salidas.xlsx`: FECHA, MES, AÑO, CODIGO, DESCRIPCION, CANTIDAD, TIPO_COMPROBANTE, NUMERO_ORDEN, PRECIO_UNITARIO, MONTO_TOTAL_SALIDA, OPERARIO, UBICACION, MAQUINA_SITIO, SECTOR.

### `correos`

remitente, password (cifrado), destinatario, tipo.

### `cola_etiquetas`

Migración desde SQLite — estados: pendiente, impreso, descartado.

### `minutas_sesiones`, `minutas_temas`, etc.

Migración desde SQLite minutas-api.

## Herramientas

- **HeidiSQL** — administración prevista (Windows)
- Scripts de migración: ⚠️ pendiente de crear

## Próximos pasos

1. Validar esquema con operación real del pañol
2. Script Excel → MariaDB (una vez)
3. Reimplementar `cola_repo.py` y `minutas-api/repo.py` contra MariaDB
4. Mantener job sync MariaDB → Firestore (`merge=True`)

## Nota sobre CockroachDB

`docs/ARQUITECTURA_DATOS.md` en el repo menciona CockroachDB para multi-sede. La **decisión acordada** sigue siendo MariaDB en PC local.
