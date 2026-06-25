# etiquetas-api

Primer microservicio del proyecto **app_web_salidas** (futura migración web del
sistema de pañol). Es un proyecto independiente del programa de escritorio
(`almacen_gui.py`): no lo toca ni lo referencia.

Se encarga de:

1. **Resolver códigos** contra el catálogo de Firebase Firestore (**solo lectura**).
2. **Encolar pedidos de impresión** de etiquetas en una base local SQLite.
3. **Servir la cola al `print-agent`** por *polling* y recibir la confirmación de
   cada impresión.

## Modos de etiqueta

- **Rotulación simple (`simple`)**: sólo un texto libre. Sin búsqueda, sin QR, sin
  caja de código.
- **Código reconocido (`codigo`)**: descripción + código (caja negra, letra
  blanca) + ubicación + QR (con el código). La descripción y la ubicación se
  obtienen del catálogo (Firestore) vía `GET /catalogo/{codigo}`.

> El render visual de la etiqueta lo hace el `print-agent` (reutilizando
> `agente_impresion_etiquetas.py`). Esta API sólo gestiona el catálogo y la cola.

## Arquitectura (decisiones a respetar)

- **La cola NO vive en Firebase, a propósito.** Este servicio nunca escribe en
  Firebase; la cola de impresión va en SQLite (`cola.db`) y todo su acceso está
  aislado en `cola_repo.py` para poder migrarla a MariaDB más adelante sin tocar
  el resto del servicio.
- **Polling, no push.** El `print-agent` pregunta por los pendientes y confirma
  resultados. Así sólo necesita salida de red, sin IP fija ni puertos expuestos,
  corra donde corra este backend.
- **Firestore es solo lectura.** Ver `firebase_lectura.py`. Si alguna vez hiciera
  falta escribir en el catálogo, detenerse y avisar: no es parte de este servicio.

## Estructura

```
etiquetas-api/
├── main.py             # FastAPI: endpoints
├── models.py           # Esquemas Pydantic (validación por tipo de etiqueta)
├── firebase_lectura.py # Lectura de catálogo en Firestore (SOLO LECTURA)
├── cola_repo.py        # Acceso a la cola SQLite (aislado para migrar a MariaDB)
├── requirements.txt
└── README.md
```

## Estados de un pedido

- `pendiente`: esperando impresión.
- `impreso`: el print-agent confirmó impresión exitosa.
- `descartado`: superó `MAX_INTENTOS` (3) fallos; ya no se reintenta.

Cuando el print-agent reporta `error`, el pedido suma 1 intento y vuelve a
`pendiente` para reintentar, hasta alcanzar el máximo y pasar a `descartado`.

## Endpoints

| Método | Ruta                          | Descripción                                  |
| ------ | ----------------------------- | -------------------------------------------- |
| GET    | `/catalogo/{codigo}`          | Resuelve un código en Firestore (404 si no). |
| POST   | `/etiquetas`                  | Encola un pedido. Devuelve `{id, estado}`.   |
| GET    | `/etiquetas/pendientes`       | Lista pendientes (polling del print-agent).  |
| POST   | `/etiquetas/{id}/confirmar`   | Aplica `impreso` / `error` a un pedido.       |
| GET    | `/health`                     | Chequeo de vida.                             |

### Ejemplo de body — `POST /etiquetas`

Tipo simple:

```json
{ "tipo": "simple", "texto_libre": "ESTANTE EN MANTENIMIENTO", "cantidad": 1, "solicitado_por": "tablet-panol" }
```

Tipo código:

```json
{
  "tipo": "codigo",
  "codigo": "A-10543",
  "descripcion": "RODAMIENTO RIGIDO DE BOLAS 6204 2RS",
  "ubicacion": "10065C",
  "qr_data": "A-10543",
  "cantidad": 2,
  "solicitado_por": "tablet-panol"
}
```

### Ejemplo de body — `POST /etiquetas/{id}/confirmar`

```json
{ "resultado": "impreso" }
{ "resultado": "error", "error_msg": "Impresora sin papel" }
```

## Configuración

- **Credenciales Firestore**: variable `GOOGLE_APPLICATION_CREDENTIALS` apuntando
  al `serviceAccountKey.json`, o dejar ese archivo junto a `firebase_lectura.py`.
  El archivo de credenciales **no se versiona** (está en `.gitignore`).
- **Nombres de colección/campos del catálogo**: constantes editables al inicio de
  `firebase_lectura.py` (`COLECCION_CATALOGO`, `CAMPO_CODIGO`, `CAMPO_DESCRIPCION`,
  `CAMPO_UBICACION`). Todavía **sin confirmar** con el proyecto real.
- **Ruta de la base SQLite**: variable `ETIQUETAS_DB_PATH` (por defecto `cola.db`).

## Cómo correrlo

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Documentación interactiva en `http://localhost:8000/docs`.
