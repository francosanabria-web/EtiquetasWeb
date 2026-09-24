# Mapa / Ubicación 2D — AppPanolWeb

**Última actualización:** 2026-07-17  
**Estado:** 🧪 MVP en prueba local (LAN celular) — **no desplegado en Vercel**

## Objetivo

Guía gráfica interactiva del pañol: mapa 2D por sectores/estanterías, visible para todos los técnicos, con enlace desde el buscador (“📍 Mapa”).

## Relación con módulos existentes

| Módulo | Rol |
|--------|-----|
| Buscador | Consulta + botón **📍 Mapa** en cada tarjeta |
| Estanterías | Lista técnica (modo pañolero); sigue aparte |
| Conteo | Inventario (pañolero); no se reemplaza |
| Sync escritorio | Fuente de `ubicacion` / stock en Firestore |

## Cómo probar en el celu (LAN)

1. PC y celular en la misma red Wi‑Fi/Ethernet.
2. En la PC: `npm run dev` (puerto **5174**, `host: true`).
3. En el celular abrir: `http://IP-DE-LA-PC:5174`
4. Pestaña **Ubicación**: tocar una estantería → panel con artículos.
5. Desde **Buscador**: buscar artículo → **📍 Mapa** → la celda se marca en **amarillo** y el artículo queda resaltado en el panel.

## Layout Pañol 1 (confirmado 2026-07-17)

Fuente: croquis Excel + correcciones en planta.

```
Fila fondo:   56 → … → 69 → 70(piso)
Pasillo
Isla norte:   [81 varillero] 80 79 78 77 76 75 74 73 71(piso)   ← alineada a la DERECHA
Isla sur:     [81]           82 83 84 85 86 87 88 89 72(piso)
Pasillo
Frente:       ENTRADA | ESCRITORIOS(ocultos) | 99 … 91 90(piso)
```

- Columna derecha (`x=14`): **70, 71, 72, 90** alineados.
- Entrada abajo-izquierda; Pañol 2 queda afuera a la izquierda.
- Pisos en Firebase: hint `100070`, `100071`, `100072`, `100090`.
- Letras de posición: se leen de artículos reales (no fijas en el layout).

## Código en la app

```
src/data/mapaPanol1.json
src/mapa/UbicacionScreen.tsx
src/mapa/mapaUtils.ts
src/parseUbicacion.ts          ← letras opcionales + códigos piso
pestaña Ubicación en App.tsx
```

Docs / backup:

```
AppPanolWeb/docs/mapa-panol-p1.borrador.json
AppPanolWeb/docs/preview-panol1.html
AppPanolWeb/docs/PLAN-MAPA-UBICACION.md
AppPanolWeb/backups/2026-07-17-pre-mapa/
```

## Modo editable (planificado)

Solo **modo pañolero**:

- Agregar / quitar / mover celdas; títulos de sector; tipo (estantería / piso / varillero).
- **No** edita stock (rotación = sync escritorio → Firestore).
- Persistencia prevista: localStorage + export JSON; luego `config/mapa` en Firestore.

## Pendiente

- [x] Layout P1 + parser `100070`
- [x] Pestaña Ubicación local + highlight desde buscador
- [ ] Probar en celular (sesión actual)
- [ ] Croquis Pañol 2 (sueltas 11, 16, 21, 37)
- [ ] Modo editable pañolero
- [ ] Deploy a Vercel solo tras OK en planta

## Referencias

- [[03 - Documentacion Tecnica/Frontend/AppPanolWeb]]
- [[01 - Estado del Proyecto/Decisiones]]
- [[01 - Estado del Proyecto/Pendientes]]
- Changelog sesión: [[01 - Estado del Proyecto/Reportes Semanales/2026-07-17]]
