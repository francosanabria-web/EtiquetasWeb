# AppPanolWeb

**Última actualización:** 2026-08-04

## Ruta del proyecto

```
C:\Users\Mantenimiento\Desktop\panol_movil\AppPanolWeb
```

## Stack (verificado en package.json)

| Paquete | Versión |
|---------|---------|
| Vite | ^6.3.5 |
| React | ^19.1.0 |
| TypeScript | ~5.9.2 |
| firebase (JS SDK) | ^12.12.1 |
| xlsx | ^0.18.5 |

## Proyecto Firebase

- **Project ID:** `sistemapanol-a1bd4`
- **Auth domain:** `sistemapanol-a1bd4.firebaseapp.com`

## Despliegue

- Build: `npm run build` (Vite)
- Producción activa: **Vercel** — `https://apppanol.vercel.app`
- `firebase.json` existe en el repo (hosting Firebase opcional / legacy)

## Qué hace la app (producción actual)

App web responsive (celular/tablet en navegador):

- Buscar artículos (Enter; catálogo en memoria + caché Firestore persistente)
- Artículos recientes (`localStorage`)
- Parseo de ubicación (`10065C`, `4000SP`, etc.)
- Modo pañolero (PIN): alias multilínea, Estanterías, **Conteo** (export `.xlsx`)
- Conteo: stock / conteo / diferencia; parcial / final / por estantería; compartir nativo
- **No tiene backend propio** — Firestore directo desde el cliente

## En desarrollo (solo local — no en Vercel aún)

- **Mapa 2D / pestaña Ubicación** — ver [[02 - Módulos/Mapa_Ubicacion]]
- Layout Pañol 1 en JSON v4 + preview HTML
- Modo editable del mapa (pañolero) — planificado

## Contrato de datos Firestore

### Colección `articulos` (id = código)

| Campo | Escrito por | Notas |
|-------|-------------|-------|
| `codigo` | Escritorio | |
| `desc` | Escritorio | |
| `stock` | Escritorio | |
| `ubicacion` | Escritorio | |
| `categoria` | Escritorio | Web no usa este campo |
| `alias` | **AppPanolWeb** | Única escritura de la web (multilínea) |

**Regla crítica:** el escritorio sincroniza con `merge=True` → **nunca pisa `alias`**.

Tipo leído en cliente: `{ id, codigo?, desc?, alias?, stock?, ubicacion? }`.

### Documento `config/catalogo`

| Campo | Escrito por | Uso |
|-------|-------------|-----|
| `version` | Escritorio (timestamp) | Señal de cambio de catálogo |
| `updatedAt` | Escritorio | server timestamp |

> La app web actual carga catálogo con `getDocs` + caché persistente (no fuerza `getDocsFromServer` en cada búsqueda).

## Lecturas Firestore (resumen)

- **Listeners:** no hay `onSnapshot`
- **Lectura:** `getDocs(articulos)` al primer uso del catálogo en sesión (búsqueda / estanterías / conteo)
- **Escritura:** `updateDoc` solo de `alias`
- Conteo y recientes: `localStorage` (0 lecturas)

## Regla de etapa migración shell

> Durante la migración del shell, evitar romper el contrato Firestore que usa AppPanolWeb (Opción A).

El mapa 2D se desarrolla en **local** y solo se sube a Vercel tras prueba en planta.

## Pendiente cruzado — puente a etiquetas (2026-08-04)

- [ ] Botón **“Imprimir etiqueta”** en resultados del buscador → deep link a `etiquetas-web` (LAN) con query params (`codigo`, `descripcion`=`desc`, `ubicacion`, etc.). Detalle y restricciones (mixed content HTTPS→HTTP, permiso **"modificar AppPanolWeb"**): [[01 - Estado del Proyecto/Pendientes]] · [[02 - Módulos/Etiquetas]].

## Referencias

- Contexto: `LABORATORIO BASE/CONTEXTO_TECNICO_MIGRACION.md`
- Contrato: [[03 - Documentacion Tecnica/Base_de_Datos/Firestore_Contrato]]
- Mapa: [[02 - Módulos/Mapa_Ubicacion]]
- Esquema JSON local: `AppPanolWeb/firebase-estructura.json`
- Reporte 2026-07-17: [[01 - Estado del Proyecto/Reportes Semanales/2026-07-17]]
- Etiquetas: [[02 - Módulos/Etiquetas]]
