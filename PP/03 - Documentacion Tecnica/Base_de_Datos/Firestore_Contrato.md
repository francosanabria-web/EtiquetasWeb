# Firestore — Contrato de datos

**Última actualización:** 2026-08-05  
**Proyecto Firebase:** `sistemapanol-a1bd4`

## Colecciones existentes

| Colección / Doc | Uso |
|-----------------|-----|
| `articulos/{codigo}` | Catálogo de artículos |
| `config/catalogo` | Versión del catálogo (señal de sync) |

⚠️ **Pendiente de verificar:** otras colecciones en producción (ej. `cola_impresion` del prototipo legacy — ya no usada por etiquetas-api).

---

## `articulos/{codigo}`

**ID del documento:** código del artículo (string).

### Esquema

| Campo | Tipo | Quién escribe | Quién lee |
|-------|------|---------------|-----------|
| `codigo` | string | Escritorio (ingreso Excel) / ⚠️ futuro HeidiSQL | Web, etiquetas-api, salidas (lectura) |
| `desc` | string | Escritorio / ⚠️ futuro HeidiSQL | Web, etiquetas-api, salidas |
| `stock` | string/number | Escritorio / ⚠️ futuro HeidiSQL — **no** salidas al egresar | Web, etiquetas-api, salidas |
| `ubicacion` | string | Escritorio / ⚠️ futuro HeidiSQL | Web, etiquetas-api, salidas |
| `categoria` | string | Escritorio / ⚠️ futuro HeidiSQL | ⚠️ Web no usa |
| `alias` | string | **AppPanolWeb** | Web |

### Reglas de escritura

1. **Escritorio** (`almacen_gui.py`, Admin SDK): sync completa de catálogo con **`merge=True`** — actualiza stock/desc/ubicacion/categoria **sin borrar `alias`** (ingreso Excel → FS).
2. **AppPanolWeb** (client SDK): **solo** `updateDoc` del campo `alias`.
3. **etiquetas-api**: **NUNCA escribe** — solo lectura vía listener + caché (`firebase_lectura.py`).
4. **salidas-api (`backend/salidas`, :8018):** **NUNCA escribe** Firestore al confirmar baja (decisión 2026-08-05). Solo lectura: pull ≤1×/día tras `SALIDAS_SYNC_HORA` (default 8) → SQLite + índice memoria (mismo patrón etiquetas). La baja escribe Excel/DB local. Código legacy de write queda deshabilitado / a retirar (`SALIDAS_FIREBASE_WRITE=0` por defecto operativo).
5. **Borrados:** solo Admin SDK (escritorio); reglas client impiden `delete`.

### Volumen

~7.000 documentos (6.988 filas en Excel maestro).

---

## `config/catalogo`

| Campo | Tipo | Quién escribe |
|-------|------|---------------|
| `version` | number (timestamp) | Escritorio (ingreso/sync). **No** salidas-api al egresar. |
| `updatedAt` | timestamp | Escritorio. **No** salidas-api al egresar. |

**Uso:** la app web puede detectar cambios de catálogo comparando `version`.

⚠️ **Pendiente de verificar:** reglas Firestore explícitas para `/config/catalogo` — `firestore.rules` actual solo detalla `articulos/{codigo}`; resto denegado para clientes.

---

## Reglas de seguridad (estado actual)

Archivo: `LABORATORIO BASE/firestore.rules`

```
articulos/{codigo}:
  allow read: if true;           // app móvil sin login
  allow create, update: if true; // escritura client (alias, etc.)
  allow delete: if false;

/{document=**}:
  allow read, write: if false;   // todo lo demás bloqueado para client
```

**Modo:** uso interno / prueba extendida. Comentario en rules: no publicar API key en internet.

**Admin SDK (escritorio / backends con service account):** no usa estas rules — bypass total.

---

## Flujo de datos

```
Excel (master_codes) ──► almacen_gui ──merge──► Firestore articulos
                              │
                              └── bump config/catalogo.version

(futuro) HeidiSQL/MariaDB ──► sync catálogo ──► Firestore (misma idea)

backend/salidas ──read only──► Firestore articulos (pull ≤1×/día + listener/caché)
                 └── baja escribe Excel/DB local (NO escribe FS)

AppPanolWeb ──update alias──► Firestore articulos
etiquetas-api ──read only──► Firestore articulos (caché)
```

## Referencias

- [[03 - Documentacion Tecnica/Frontend/AppPanolWeb]]
- [[02 - Módulos/Salidas]]
- `CONTEXTO_TECNICO_MIGRACION.md` (LABORATORIO BASE)
- `REGLAS_FIREBASE.txt` (LABORATORIO BASE)
