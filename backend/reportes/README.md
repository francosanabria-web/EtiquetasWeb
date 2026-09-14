# Reportes — backend

Consultas operativas de movimientos (listado, filtros, resumen, export Excel Table).

- Puerto: **8017**
- Stack: Starlette + uvicorn + pandas + openpyxl
- Datos: **solo lectura** de `master_salidas.xlsx` (hoja `Movimientos`)
- Por defecto: mismo Excel de **producción** que KPIs  
  `G:\Unidades compartidas\Mantenimiento\MANTENIMIENTO  OZLA 2024-2025\17. Pañol\pañol v5.0\master_salidas.xlsx`  
  (doble espacio en `MANTENIMIENTO  OZLA`)

## Variables de entorno

| Variable | Uso |
|----------|-----|
| `REPORTES_MOVIMIENTOS_FILE` | Override explícito (csv/xlsx concreto) |
| `REPORTES_DATA_PATH` | Carpeta; usa `master_salidas.xlsx` si existe |
| `KPIS_DATA_PATH` / `SALIDAS_DATA_PATH` | Si no hay override Reportes, busca `master_salidas.xlsx` ahí |
| `REPORTES_PORT` | Default 8017 |
| `REPORTES_CORS_ORIGINS` | Orígenes CORS |
| `REPORTES_MAIL_DIARIO_ENABLED` | `0` (default) — no envía diario |
| `REPORTES_MAIL_MENSUAL_ENABLED` | `0` (default) — no envía mensual |
| `REPORTES_MAIL_DESTINATARIOS` | Lista separada por comas |
| `REPORTES_MAIL_DIARIO_HORA` | Hint para tarea Windows (`07:30`) |
| `REPORTES_MAIL_MENSUAL_DIA` / `_HORA` | Hint mensual (día 1, `08:00`) |
| `PANOL_SMTP_*` | Credenciales SMTP (mismo patrón que `email_service`) |

**Nunca escribe** en el Excel. El store es intercambiable (SQL / API Salidas) sin cambiar el contrato HTTP.

## Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/health` | Estado del servicio + path + filas |
| GET | `/api/reportes/movimientos` | Listado filtrado |
| GET | `/api/reportes/resumen` | Agregaciones (sector, operario, comprobante, mes) |
| GET | `/api/reportes/filtros` | Valores para combos |
| POST | `/api/reportes/refresh` | Recargar archivo (solo lectura) |
| GET | `/api/reportes/export.xlsx` | Export Excel Table (layout diario de gastos) |
| GET | `/api/reportes/export.csv` | **Deprecated** — preferir xlsx |
| GET | `/api/reportes/mail/status` | Flags mail (sin enviar) |
| POST | `/api/reportes/mail/diario/dry-run` | Arma preview sin enviar |
| POST | `/api/reportes/mail/diario` | Envía solo si `DIARIO_ENABLED=1` |
| POST | `/api/reportes/mail/mensual` | Envía solo si `MENSUAL_ENABLED=1` |

### Columnas export / tabla (mail diario)

Orden del detalle de retiros del escritorio + `SECTOR` (listado unificado):

`FECHA`, `CODIGO`, `DESCRIPCION`, `CANTIDAD`, `PRECIO_UNITARIO`, `MONTO_TOTAL_SALIDA`, `TIPO_COMPROBANTE`, `NUMERO_ORDEN`, `MAQUINA_SITIO`, `OPERARIO`, `SECTOR`

## Mail (scaffold, desactivado)

Ver `mail_jobs.py`. No hay scheduler en el proceso. Para activar:

1. SMTP (`PANOL_SMTP_USER` / `PASSWORD`)
2. `REPORTES_MAIL_DESTINATARIOS=...`
3. `REPORTES_MAIL_*_ENABLED=1`
4. Tarea Windows / supervisor que llame dry-run o `POST .../mail/diario`

Filtros query: `fecha_desde`, `fecha_hasta`, `sector`, `operario`, `codigo`, `numero_orden`, `tipo_comprobante`, `q`, `limite`, `offset`.

## Arranque

```bat
scripts\_start_reportes.bat
```

Verificar: `GET http://localhost:8017/health` / `GET /api/reportes/mail/status`.

## UI

Portal: `http://localhost:5180/reportes` (proxy Vite `/api/reportes` → `:8017`).
