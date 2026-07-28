# Arquitectura de datos — SistemasPañol

## Resumen

| Capa | Tecnología | Uso |
|------|------------|-----|
| **Servicios locales** (colas, minutas en LAN) | **SQLite** | Archivo `.db` en la PC servidor |
| **Datos permanentes / movimientos / multiusuario** | **CockroachDB** | Cuando integremos stock, salidas, historial central |

No conviene unificar **todo** en CockroachDB hoy: añade complejidad de red, credenciales y despliegue sin beneficio inmediato para minutas en 2–3 operadores.

## SQLite — ¿cuánto dura? ¿cuánto espacio?

- **Duración:** indefinida; el archivo no expira. Backup = copiar `minutas.db`.
- **Espacio:** muy bajo para minutas (texto + filas importadas). Orden de magnitud: **MB**, no GB.
- **Concurrencia:** bien para 2–3 usuarios si **una PC** concentra la API.

**Conclusión:** SQLite es **producción válida** para minutas y etiquetas en LAN.

## CockroachDB — cuándo

- Movimientos de stock, salidas, gastos consolidados
- Acceso desde varias sedes o muchos usuarios simultáneos

Migración futura: `repo.py` está aislado; se puede reimplementar sin cambiar la web.

## Minutas — fuente de verdad

1. **Excel diario** = snapshot del estado de pedidos.
2. **SQLite** = reuniones, selección, notas y minutas enviadas.
3. **Mail** = registro permanente para jefatura/compras.
