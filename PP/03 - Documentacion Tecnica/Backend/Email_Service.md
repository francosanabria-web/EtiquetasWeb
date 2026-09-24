# Email Service

**Última actualización:** 2026-06-26

## Ruta

```
C:\Users\Mantenimiento\Desktop\AppWebSalidas\backend\email_service
```

## Stack

| Componente | Tecnología |
|------------|------------|
| Framework | **Starlette** (no FastAPI — compatibilidad Python 3.14) |
| Servidor | uvicorn |
| Excel | openpyxl (solo lectura) |
| SMTP | smtplib — Gmail :587 + starttls (como `almacen_gui.py`) |

## Puerto

**8020** — `scripts/INICIAR_EMAIL.bat`

## Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/health` | `{ status: "ok", service: "email-service" }` |
| GET | `/api/email/contacts` | Contactos hoja `correos` de master_codes |
| POST | `/api/email/send` | Envío multipart texto + HTML |

### POST `/api/email/send` — body JSON

```json
{
  "destinatarios": ["email@dominio.com"],
  "asunto": "Asunto",
  "cuerpo_html": "<html>...</html>",
  "cuerpo_texto": "opcional"
}
```

## Configuración SMTP

Prioridad:

1. Variables `.env`: `PANOL_SMTP_USER`, `PANOL_SMTP_PASSWORD`, `PANOL_SMTP_FROM`, `PANOL_SMTP_HOST`, `PANOL_SMTP_PORT`
2. Fallback: fila 1 hoja `correos` (`remitente` + `password`)

## Excel (solo lectura)

| Variable | Default |
|----------|---------|
| `PANOL_DATA_DIR` | `G:\...\pañol v5.0\` |
| `MASTER_CODES_PATH` | ruta directa al `.xlsx` (opcional) |

Archivos buscados: `master_codes.xlsx`, `base_datos.xlsx`.

**Columnas hoja `correos`:** `remitente`, `password`, `destinatario`, `tipo`.

## Archivos

| Archivo | Rol |
|---------|-----|
| `main.py` | App Starlette + CORS |
| `contacts_reader.py` | Lectura Excel |
| `smtp_config.py` | Resolución credenciales |
| `mailer.py` | Envío MIME |
| `models.py` | Dataclass `Contacto` |

## Consumidores

- Shell minuta: `apps/web/src/api/emailClient.ts`

## Pendientes

- Tests automatizados
- Supervisor/autostart (como etiquetas)
- **Objetivo operativo:** eliminar necesidad de proceso aparte — SMTP embebido como escritorio
- Usuario reportó envío sin servicio levantado — ⚠️ verificar si había instancia previa en background

## CI

No incluido en GitHub Actions actual.
