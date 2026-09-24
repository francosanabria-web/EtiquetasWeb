# Catálogo / Config

**Estado:** 🔄 En desarrollo (web parcial) / ✅ Funcionando (escritorio)  
**Última actualización:** 2026-06-26

## Qué hace

Mantiene el maestro de artículos (código, descripción, stock, ubicación, criticidad/importancia), configuración de correos, sincronización con la app móvil ("Actualizar App Pañol") e importación semanal de stock.

## Cómo funciona (técnico)

**Escritorio:** pestaña **⚙️ Configuración y datos** en `almacen_gui.py`.

**Excel maestro:**
- `base_datos.xlsx` o `master_codes.xlsx` en `G:\...\pañol v5.0\`
- Hoja `ARTICULOS` — **6.988 filas**
- Hoja `correos` — SMTP y destinatarios
- Hoja `config` — 21 filas

**Firebase sync (escritorio):**
- Escribe `articulos/{codigo}` con `merge=True`
- Campos: `codigo`, `desc`, `stock`, `ubicacion`, `categoria`
- Bumpea `config/catalogo.version`

**Web:**
- **AppPanolWeb:** edita solo `alias` en `articulos`
- **etiquetas-api:** lectura catálogo para resolver códigos

## Endpoints / API

| Consumidor | Acceso |
|------------|--------|
| etiquetas-api | GET `/catalogo/{codigo}` (lectura) |
| AppPanolWeb | Firestore client SDK directo |
| email_service | Lee hoja `correos` (no catálogo) |

No hay API de administración de catálogo en el monorepo aún.

## Pendientes de este módulo

- Backend CRUD catálogo en MariaDB
- Sync bidireccional Excel ↔ MariaDB ↔ Firestore
- UI config en shell (correos, import stock)
- Preservar contrato `alias` (ver [[03 - Documentacion Tecnica/Base_de_Datos/Firestore_Contrato]])

## Notas

- **No modificar** `master_codes.xlsx` desde servicios web excepto lectura de `correos`.
- Criticidad: `CRÍTICO` / `ALTA FRECUENCIA` / `BASE` — lógica en escritorio.
