# Registro de salidas — flujo de carga

## Precarga + Finalizar
- **Registrar salida**: solo agrega a "Carga Actual" (tree + `_salidas_pendientes`). No escribe Excel ni descuenta stock.
- **Finalizar**: valida Solicitud, aplica a todos los ítems, descuenta stock, escribe `master_salidas` + diario, sync Firebase.

## Flujo rápido (varios ítems sin Solicitud)
```
Código → Enter → Cantidad → Enter → [registra] → Código → ...
(completar Solicitud cuando quieras)
Finalizar → valida Solicitud → graba
```

## Solicitud obligatoria al Finalizar
- Comprobante
- N° Orden
- Sector + Operario (Producción puede usar operario por defecto)

## Flujo clásico (sin cambios)
Completar Solicitud primero → cargar ítems uno a uno → Finalizar.

## Atajos
- Enter en Cantidad: registrar y volver a Código
- Supr/Delete: eliminar ítem seleccionado de precarga
- F3: búsqueda avanzada
