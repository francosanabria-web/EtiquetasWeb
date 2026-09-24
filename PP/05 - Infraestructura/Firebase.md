# Firebase — Infraestructura

**Última actualización:** 2026-08-05

## Proyecto

| Campo | Valor |
|-------|-------|
| Project ID | `sistemapanol-a1bd4` |
| Auth domain | `sistemapanol-a1bd4.firebaseapp.com` |

## Servicios en uso

| Servicio Firebase | Uso en el ecosistema |
|-------------------|----------------------|
| **Firestore** | Catálogo `articulos`, config `catalogo` |
| **Hosting** | Deploy AppPanolWeb (`firebase.json`) |
| Realtime Database | **No usado** |

## Consumidores

| Cliente | Lectura | Escritura |
|---------|---------|-----------|
| almacen_gui (Admin SDK) | ✅ | ✅ articulos + config (merge) |
| AppPanolWeb (client SDK) | ✅ articulos | ✅ solo `alias` |
| etiquetas-api (Admin SDK) | ✅ articulos (sync diaria + caché; 0 FS por búsqueda) | ❌ prohibido en código |
| salidas-api (`backend/salidas`) | ✅ articulos (mismo patrón etiquetas; a cablear) | ❌ **prohibido** al confirmar baja (decisión 2026-08-05) |
| prueba_etiquetas_1 (legacy) | ✅ | ⚠️ escribía cola_impresion — obsoleto |

## Credenciales

| Archivo | Ubicación típica |
|---------|------------------|
| `serviceAccountKey.json` | Carpeta del `.exe` / `etiquetas-api/` |
| `firebaseConfig` (web) | Embebido en cliente AppPanolWeb (normal) |

**Regla:** nunca commitear credenciales — `.gitignore` en monorepo las excluye.

## Reglas de seguridad

Archivo: `LABORATORIO BASE/firestore.rules`

- `articulos`: read + write abiertos para clientes (uso interno)
- delete: bloqueado para clientes
- resto de colecciones: denegado para client SDK

Ver detalle: [[03 - Documentacion Tecnica/Base_de_Datos/Firestore_Contrato]]

## Estrategia de lecturas (etiquetas-api)

Para minimizar costo/cuota (post-incidente junio 2026 — ver [[02 - Módulos/Etiquetas#Incidente — cuota Firestore (fin junio 2026)|Etiquetas · Incidente cuota]]):

1. Sync Firestore **una vez al día** (~08:00) con `on_snapshot`
2. Caché SQLite + memoria para `GET /catalogo/{codigo}`
3. Reinicio API mismo día → 0 lecturas extra
4. ⚠️ El fallo histórico fue Firestore `.get()` / lecturas-por-búsqueda — **no** el método HTTP GET. El endpoint HTTP se mantiene; **nunca** debe llamar `.get()`.

Documentado en `firebase_lectura.py`. Commits: `a5a29e1` (mitigación) + `2da1b20` (patrón final).

**Salidas** debe copiar este patrón (decisión 2026-08-05): sync diaria → local; `GET /articulo/{codigo}` solo memoria; **sin write** en baja.

## Sync desde escritorio

```python
db.collection('articulos').document(codigo).set(payload, merge=True)
db.collection('config').document('catalogo').set({'version': timestamp}, merge=True)
```

## Deploy

| App | Comando típico |
|-----|----------------|
| AppPanolWeb | `firebase deploy` (Hosting) |
| Rules | deploy rules desde LABORATORIO BASE |

⚠️ **Pendiente de verificar:** URL producción final (Vercel `apppanol.vercel.app` vs Firebase Hosting URL).

## Futuro

- Backend MariaDB alimenta Firestore (mismo contrato)
- Posible Firebase Auth para shell central
- Endurecer rules cuando haya auth real (hoy modo prueba interno)

## Referencias

- [[03 - Documentacion Tecnica/Frontend/AppPanolWeb]]
- [[03 - Documentacion Tecnica/Base_de_Datos/Firestore_Contrato]]
- `REGLAS_FIREBASE.txt`
