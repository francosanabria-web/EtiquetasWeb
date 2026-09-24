# Changelog 2026-07-08

Última versión de prueba antes de continuar migración web.

## 1. Tipo de mail `compras`
En hoja `correos` de `master_codes.xlsx`, columna `tipo`:

| tipo | Recibe |
|---|---|
| `pañol` | Todos: reposición, gastos diarios, mensual, salida de activos |
| `supervisor` | Solo salida de activos |
| `compras` | **Reposición diaria + salida de activos** (no gastos ni mensual) |

Varios correos por fila o separados por coma/punto y coma en `destinatario`.

Función interna: `_correos_para_reporte(reporte)` con `reporte` ∈ `reposicion | gastos | mensual | activos`.

## 2. Propagación de precio al mes en curso
Al cargar/actualizar `precio_unitario` en `master_codes` (> 0):
- Busca el código en `master_salidas.xlsx`
- Busca en `salidas_DD-MM-YYYY.xlsx` del **mes en curso**
- Actualiza `PRECIO_UNITARIO` y recalcula `MONTO_TOTAL_SALIDA` (= cantidad × precio, respetando signo de devoluciones)

Se dispara desde:
- **Editar artículo** (campo precio manual)
- **Importación diaria/semanal** cuando el precio importado cambia y es > 0

Función: `_propagar_precio_movimientos_mes_curso(codigo, nuevo_precio)`.

## 3. Editar artículo — precio manual
Nuevo campo **Precio unitario** en ventana Editar artículo.
- Guarda en `master_codes` (columna `precio_unitario`)
- No lo pisa la importación si el archivo trae 0 (comportamiento ya existente)
- Al guardar con precio nuevo, propaga a movimientos del mes (punto 2)

## 4. Registro de salidas — carga sin Solicitud
**Flujo rápido (nuevo):**
1. Código → Cantidad → **Enter** registra en precarga y vuelve a Código
2. Repetir ítems sin tocar Solicitud
3. Completar Solicitud (comprobante, orden, sector, operario)
4. **Finalizar** — valida Solicitud, aplica datos a todos los ítems pendientes, graba Excel y descuenta stock

**Flujo clásico:** sigue funcionando (completar Solicitud antes de cargar ítems).

Enter en Cantidad ya **no** avanza a Solicitud; siempre registra y vuelve a Código.

Al finalizar se refresca precio desde master si estaba en 0 al momento del registro.
