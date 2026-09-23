# Datos Salidas — prueba local vs planta

## Modo planta (default en PC del pañol)

El servicio (`backend/salidas`, puerto **8018**) por defecto:

| Rol | Ruta |
|-----|------|
| **Lee** (solo lectura) | `…\pañol v5.0\master_codes.xlsx` — hojas `ARTICULOS` + `config` |
| **Escribe** | `…\pañol v5.0\salidas_web\` — `master_salidas.xlsx` + `salidas_DD-MM-AAAA.xlsx` |

⚠️ Hay **doble espacio** en `MANTENIMIENTO  OZLA`. Confirmado en disco.

**No escribe** en:
- `master_codes.xlsx` de producción
- `master_salidas.xlsx` de producción (raíz del pañol; lo sigue usando el escritorio / KPIs)

El stock del maestro se actualiza **solo en memoria** durante la sesión web (proyección de carga). La persistencia del egreso es el Excel en `salidas_web`.

## Variables de entorno

| Variable | Efecto |
|----------|--------|
| `SALIDAS_PANOL_PATH` | Carpeta base del pañol v5.0 |
| `SALIDAS_MAESTRO_PATH` | Ruta absoluta al maestro (`master_codes.xlsx`) |
| `SALIDAS_WEB_PATH` | Carpeta de escritura (historial + diarios) |
| `SALIDAS_DATA_PATH` | Alias de `SALIDAS_WEB_PATH` (compat) |
| `SALIDAS_MAESTRO_WRITABLE` | `1` solo para demos locales que deban mutar el Excel maestro |
| `SALIDAS_PORT` | Puerto (default 8018) |
| `SALIDAS_CACHE_DB` | Ruta del SQLite de caché |
| `SALIDAS_SYNC_HORA` | Hora local mínima para pull Firestore (default 8) |
| `SALIDAS_FIREBASE_WRITE` | Default `0` — no escribir Firestore al confirmar |
| `GOOGLE_APPLICATION_CREDENTIALS` | JSON de cuenta de servicio |

`scripts/_start_salidas.bat` ya setea las rutas de planta.

## Modo prueba local (`data_prueba/`)

Si no existe la carpeta del pañol en `G:\`, cae a `backend/salidas/data_prueba/`.

Para forzar demo aunque exista Drive:

```bat
set SALIDAS_MAESTRO_PATH=%CD%\backend\salidas\data_prueba\base_datos.xlsx
set SALIDAS_WEB_PATH=%CD%\backend\salidas\data_prueba
set SALIDAS_MAESTRO_WRITABLE=1
```

Al primer arranque en demo, si faltan archivos, crea `base_datos.xlsx` + historial vacío.

Códigos demo: `DEMO-001` / `002` / `003`.

## Capas (migración SQL futura)

- `excel_io.py` / `articulos_cache.py` = IO
- `store.py` / `service.py` = dominio
- `movimientos.py` = lectura reutilizable por Reportes
- La UI nunca lee rutas Excel: solo `/api/salidas/*`
