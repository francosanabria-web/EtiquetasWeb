# Solicitudes de pedidos — Esquema del Excel

**Última actualización:** 2026-07-24

Fuente de verdad del módulo Solicitud de pedidos (fase previa a MariaDB).

- **Archivo:** `G:\Unidades compartidas\Mantenimiento\MANTENIMIENTO  OZLA 2024-2025\17. Pañol\pañol v5.0\solicitudes_pedidos.xlsx`
  - Configurable con la variable de entorno `SOLICITUDES_EXCEL_PATH`.
- **Escritura segura:** lock de archivo `solicitudes_pedidos.xlsx.lock` (coordina varias PC sobre Drive) + archivo temporal `.tmp` + copia `.bak` antes de reemplazar. Reemplazo atómico con `os.replace`.
- **Lectura:** caché por fecha de modificación; si otra PC escribió, al recargar se relee.
- **Adjuntos:** `...\pañol v5.0\solicitudes_adjuntos\` (env `SOLICITUDES_UPLOADS_DIR`).

## Hoja `PEDIDOS` (una fila por ítem)

La cabecera del pedido se **repite** en cada ítem del mismo pedido; al leer se agrupa por `SOLICITUD_ID`.

| Columna | Ámbito | Descripción |
|---------|--------|-------------|
| `SOLICITUD_ID` | pedido | Id interno (entero, correlativo `id_seq`) |
| `N_PEDIDO` | pedido | `P-####` (Normal/Urgente). Vacío en TR |
| `N_TR` | pedido | `TR-####` (solo TR) |
| `TIPO` | pedido | `normal` / `urgente` / `tr` |
| `ESTADO` | pedido | `borrador`/`en_proceso`/`parcial`/`cumplido`/`cancelado` |
| `CUENTA_CONTABLE` | pedido | Lista fija del catálogo |
| `SOLICITANTE` | pedido | Texto libre |
| `PROVEEDOR` | pedido | Texto libre (obligatorio en TR) |
| `REMITO_NRO` | pedido | Nº remito |
| `REMITO_ARCHIVO` | pedido | Nombre de adjunto |
| `PRESUPUESTO_NRO` | pedido | Nº presupuesto |
| `PRESUPUESTO_ARCHIVO` | pedido | Nombre de adjunto |
| `NOTAS` | pedido | Texto libre |
| `ITEM_ORDEN` | ítem | Posición 0-based |
| `ITEM_CODIGO` | ítem | Código catálogo (opcional) |
| `ITEM_DESCRIPCION` | ítem | Descripción (obligatoria) |
| `ITEM_CANTIDAD` | ítem | Numérico (> 0) |
| `ITEM_UNIDAD` | ítem | UN/KG/… |
| `ITEM_AREA_MAQUINA` | ítem | Área / máquina / línea (texto libre) |
| `ITEM_IMAGEN` | ítem | Nombre de adjunto |
| `CREADO_POR` | pedido | Email del usuario |
| `CREADO_EN` | pedido | ISO UTC |
| `ACTUALIZADO_EN` | pedido | ISO UTC |

## Hoja `CONTADORES`

| CLAVE | VALOR | Uso |
|-------|-------|-----|
| `id_seq` | entero | Último id interno usado |
| `pedido` | entero | Último `P-####` (0 = primero será `P-0001`) |
| `tr` | entero | Último `TR-####` |

⚠️ **Continuar correlatividad del maestro:** para seguir desde `P-4317`, poner `pedido = 4316` en esta hoja (el próximo será `P-4317`). Idealmente se hará al importar el maestro histórico.

## Reinterpretación al cargar el maestro

La lectura mapea por **nombre de encabezado**, así que se puede reordenar/renombrar columnas al importar el maestro y ajustar el mapeo en `backend/solicitudes/db.py` (`COLUMNS` / `HEADER_TO_KEY`).
