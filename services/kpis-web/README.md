# kpis-web

Módulo **KPIs — Mantenimiento** de SistemasPañol. Importa planillas Excel de gastos
y las traduce a un panel ejecutivo: totales, evolución temporal, desglose por línea,
obra y categoría.

**Usuarios:** jefatura y gerencia del sector de mantenimiento.

## Acceso

| Desde | URL |
|-------|-----|
| Local | http://localhost:5174 |
| Red LAN | http://IP-PC:5174 (`npm run dev:lan`) |
| Portal | Shell SistemasPañol → tarjeta KPIs |

## Flujo de uso

1. Importar archivo `.xlsx` / `.xls` (arrastrar o elegir).
2. Primera vez: mapear columnas (fecha, importe, línea, obra, etc.). Se **guarda en caché**.
3. Reimportaciones del mismo formato: mapeo automático.
4. Filtrar por fechas, línea u obra; revisar gráficos y tabla.

Los datos y la configuración persisten en **IndexedDB + localStorage** del navegador
(no hace falta reconfigurar en cada visita). Reimportá cuando se actualice la planilla del mes.

## Desarrollo

```powershell
cd services\kpis-web
npm install
npm run dev        # localhost:5174
npm run dev:lan    # accesible desde otras PCs
```

## Columnas esperadas (flexible)

El asistente detecta sinónimos en español. Campos mínimos:

| Campo | Obligatorio |
|-------|-------------|
| Fecha | Sí |
| Importe | Sí |
| Línea | Recomendado |
| Obra | Recomendado |
| Concepto | Opcional |
| Categoría | Opcional |

## Integración shell

En `apps/web/.env.local`:

```
VITE_KPIS_URL=http://10.1.102.8:5174
```

En `kpis-web/.env.local` (opcional):

```
VITE_SHELL_URL=http://10.1.102.8:5180
```
