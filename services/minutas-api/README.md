# minutas-api

Backend del módulo **Minutas** — reuniones semanales de seguimiento de solicitudes a compras.

## Puerto

**8012** (por convención SistemasPañol)

## Arranque

```powershell
cd services\minutas-api
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8012 --reload
```

## Variables de entorno

| Variable | Descripción |
|----------|-------------|
| `MINUTAS_DB_PATH` | Ruta SQLite (default: `./minutas.db`) |
| `MINUTAS_CORS_ORIGINS` | Orígenes CORS (default `*`) |
| `MINUTAS_SMTP_HOST` | Servidor SMTP |
| `MINUTAS_SMTP_PORT` | Puerto (default 587) |
| `MINUTAS_SMTP_USER` / `MINUTAS_SMTP_PASSWORD` | Credenciales |
| `MINUTAS_SMTP_FROM` | Remitente |
| `MINUTAS_SMTP_TLS` | `true` / `false` |
| `MINUTAS_EMAIL_DEFAULT_TO` | Destinatarios por defecto (coma) |

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest test_minutas -v
```

## Persistencia

SQLite local: sesiones semanales, solicitudes (arrastre entre reuniones), entregas parciales, temas y actualizaciones.
