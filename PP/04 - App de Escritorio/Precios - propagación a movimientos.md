# Precios — propagación a movimientos

## Problema
Movimientos registrados sin costo (precio 0) por demora administrativa. El precio se carga después en `master_codes`.

## Solución
Cuando `precio_unitario` pasa a un valor **> 0** en el maestro, el sistema actualiza automáticamente los registros del **mes en curso** con ese código.

## Archivos afectados
- `master_salidas.xlsx`
- `salidas_DD-MM-YYYY.xlsx` (solo archivos del mes actual)

## Campos actualizados
- `PRECIO_UNITARIO` → nuevo precio
- `MONTO_TOTAL_SALIDA` → `CANTIDAD × PRECIO_UNITARIO` (devoluciones mantienen signo negativo)

## Origen del cambio de precio
1. Ventana **Editar artículo** → campo Precio unitario → GUARDAR
2. Importación desde carpeta `IMPORTAR` cuando el precio importado cambia y es > 0

## No afecta
- Meses anteriores (solo mes en curso según fecha de `FECHA` del movimiento)
- Ítems en precarga no finalizados (se refrescan al pulsar Finalizar)
