# Migracion Solicitudes a MariaDB - Plan de redireccion

> **Base:** `panol` en `D:\xampp\mysql\data\panol` - MariaDB 10.4.32 - `utf8mb4_unicode_ci` - InnoDB
> **Fecha:** 2026-09-11
> **DDL:** `Server/docs/panol_solicitudes_migracion_v1.sql` (idempotente, ya ejecutado y verificado en XAMPP)
> **Principio:** Replica EXACTA de la logica `cajas_` - tablas GENERALES sin prefijo + tablas de modulo con prefijo `solicitudes_`

---

## 1. Resumen ejecutivo

| Antes (actual) | Despues (objetivo manana) |
|---|---|
| `config.EXCEL_PATH = G:\...\solicitudes_pedidos.xlsx` (Drive compartido) | `config.DB_HOST/DB_NAME = 127.0.0.1:3306/panol` (MariaDB XAMPP) |
| `config.UPLOADS_DIR = G:\...\solicitudes_adjuntos` | `config.UPLOADS_DIR = <local>/uploads/solicitudes` o `D:\xampp\...` pero **metadata en DB** |
| `db.py` usa `_FileLock` + `openpyxl` + escritura atomica `.tmp -> .bak -> .xlsx` | `db.py` usa `pymysql` + transacciones + `FOREIGN KEY` |
| 1 fila Excel por item (cabecera repetida) + hoja `CONTADORES` | Tablas normalizadas: `solicitudes_pedidos` + `solicitudes_items` + `solicitudes_adjuntos` |
| `REMITO_ARCHIVO` y `PRESUPUESTO_ARCHIVO` como texto en columna | Tabla `solicitudes_adjuntos` (1:N) con tipo, mime, tamanio, auditoria |

**No se modifica codigo hoy.** Solo documentacion. Manana: cambiar `import` en `main.py` y `db.py`.

---

## 2. Tablas creadas (verificadas con SHOW TABLES)

### A) GENERALES - reutilizables sin prefijo (shared)

Ya existian `areas` y `personal`. Se agregaron:

- **`proveedores`** (`id`, `nombre` UNIQUE, `cuit` UNIQUE NULL, `contacto`, `email`, `activo`, `creado_en`, `actualizado_en`)
  - Maestro general. Aprendido dinamico. `ON DELETE SET NULL` desde `solicitudes_pedidos` - no se borra historial.
- **`cuentas_contables`** (`id`, `codigo` UNIQUE, `nombre`, `activo`)
  - Split de `CATALOGOS_EDITABLES.json` `"7120001 - Conservacion..."` en `codigo`/`nombre`. 14 registros. Duplicado `7150002` corregido a `7150003` para `Refrigerios/Comidas`.
- **`unidades_medida`** (`id`, `codigo` UNIQUE, `nombre`, `activo`)
  - `UN/KG/MT/LT/CJ/PAR` con nombres completos. 6 registros.

### B) MODULO `solicitudes_` - solo solicitud de pedidos

- **`solicitudes_estados`** (`clave` UNIQUE: `borrador/en_proceso/parcial/cumplido/cancelado`, `orden`, `activo`) - 5 filas
- **`solicitudes_tipos`** (`clave` UNIQUE: `normal/urgente/tr`) - 3 filas
- **`solicitudes_pedidos`** - cabecera. `n_pedido` UNIQUE NULL (`P-0001`), `n_tr` UNIQUE NULL (`TR-0001`), FKs a `solicitudes_tipos/estados` (RESTRICT), `cuentas_contables/personal/proveedores` (SET NULL). Indices en `estado_id/tipo_id/cuenta_contable_id/solicitante_id/proveedor_id/creado_en`.
- **`solicitudes_items`** - detalle. `UNIQUE(solicitud_id, orden)`, FK `solicitud_id` CASCADE, `unidad_id` SET NULL, `area_maquina` snapshot texto.
- **`solicitudes_adjuntos`** - filesystem + metadata (ver seccion 5). `UNIQUE(nombre_guardado)`, FKs CASCADE.
- **`solicitudes_contadores`** (`clave` PK: `id_seq/pedido/tr`, `valor`) - compatibilidad Excel. `id_seq=13, pedido=4552, tr=3` (GREATEST on duplicate).

Verificacion:
```sql
SHOW TABLES FROM panol; -- 15 tablas (8 nuevas)
SELECT * FROM unidades_medida; -- 6
SELECT * FROM cuentas_contables; -- 14
SELECT * FROM solicitudes_estados; -- 5
SELECT * FROM solicitudes_tipos; -- 3
SELECT * FROM solicitudes_contadores; -- id_seq=13, pedido=4552, tr=3
```

---

## 3. Como cambia `config.py`

### Actual (`backend/solicitudes/config.py` - hoy)

```python
DRIVE_DIR = Path(r"G:\Unidades compartidas\Mantenimiento\...\17. Pañol\pañol v5.0")
EXCEL_PATH = Path(os.environ.get("SOLICITUDES_EXCEL_PATH", DRIVE_DIR / "solicitudes_pedidos.xlsx"))
UPLOADS_DIR = Path(os.environ.get("SOLICITUDES_UPLOADS_DIR", DRIVE_DIR / "solicitudes_adjuntos"))
DB_PATH = Path(os.environ.get("SOLICITUDES_DB_PATH", DATA_DIR / "solicitudes.db"))  # legacy SQLite
```

Problemas: lock archivo sobre Drive (12s timeout, stale 60s), copia `.bak`, cache por `mtime`, serializa a mano `groups by SOLICITUD_ID`.

### Propuesto (manana) - seguir patron `backend/personal/config.py`

```python
# -*- coding: utf-8 -*-
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PORT = int(os.environ.get("SOLICITUDES_PORT", "8014"))

# MariaDB - igual que backend/personal (panol en XAMPP)
DB_HOST = os.environ.get("SOLICITUDES_DB_HOST", "127.0.0.1")
DB_PORT = int(os.environ.get("SOLICITUDES_DB_PORT", "3306"))
DB_USER = os.environ.get("SOLICITUDES_DB_USER", "root")
DB_PASSWORD = os.environ.get("SOLICITUDES_DB_PASSWORD", "")
DB_NAME = os.environ.get("SOLICITUDES_DB_NAME", "panol")

# Adjuntos: local filesystem (NO Drive). Servidos por API.
# Produccion: D:\panol_uploads\solicitudes  o  Server/AppWebSalidas/backend/solicitudes/uploads
UPLOADS_DIR = Path(os.environ.get("SOLICITUDES_UPLOADS_DIR", BASE_DIR / "uploads" / "solicitudes"))
# o mantener Drive solo como backup: os.environ.get("SOLICITUDES_UPLOADS_DIR", r"G:\...\solicitudes_adjuntos")

def cors_origins_list() -> list[str]:
    raw = os.environ.get("SOLICITUDES_CORS_ORIGINS", "*").strip()
    return ["*"] if raw == "*" else [o.strip() for o in raw.split(",") if o.strip()]
```

Variables de entorno a documentar en `.env` o launcher:
```
SOLICITUDES_DB_HOST=127.0.0.1
SOLICITUDES_DB_PORT=3306
SOLICITUDES_DB_USER=root
SOLICITUDES_DB_PASSWORD=
SOLICITUDES_DB_NAME=panol
SOLICITUDES_UPLOADS_DIR=./uploads/solicitudes
```

---

## 4. Que cambiar en `db.py` - de `_FileLock + openpyxl` a `pymysql`

### Antes: patron Excel

```python
class _FileLock: ...  # os.open O_EXCL + stale 60s
def _leer_workbook(): ...  # load_workbook + agrupar por SOLICITUD_ID
def _escribir_workbook(): ... # Workbook + os.replace(tmp, EXCEL_PATH) + .bak
_cache = {"mtime": None, ...}
def crear(data): 
    with _FileLock(EXCEL_PATH):
        solicitudes, contadores = _load_all(force=True)
        sid = _next(contadores, "id_seq")
        n_pedido = f"P-{_next(contadores,'pedido'):04d}"
        solicitudes.append(sol)
        _escribir_workbook(solicitudes, contadores)
```

### Despues: patron MariaDB (igual que `backend/personal/db.py`)

```python
from pymysql.cursors import DictCursor
from pymysql import connections
from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

def get_connection():
    return connections.Connection(
        host=DB_HOST, port=DB_PORT, user=DB_USER,
        password=DB_PASSWORD, database=DB_NAME,
        charset="utf8mb4", cursorclass=DictCursor,
        autocommit=False,
    )

def init_db() -> None:
    # Ya no crea tablas aca - el DDL vive en Server/docs/*.sql
    # Solo verifica conexion. Idempotente.
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM solicitudes_pedidos LIMIT 1")
    finally:
        conn.close()
```

**Reglas migradas:**
- `personal` no se borra si tiene historial -> `ON DELETE SET NULL` (pedido conserva `solicitante_id` nullificado, auditable)
- `proveedores` igual -> `SET NULL`
- `cuenta_contable` igual -> `SET NULL`
- `tipo/estado` no se borra si en uso -> `RESTRICT` (error FK si intentas DELETE)
- `solicitudes_items` se borra en cascada si borras cabecera -> `ON DELETE CASCADE`
- `solicitudes_adjuntos` idem -> `CASCADE` por pedido e item

---

## 5. Ejemplos de queries con las nuevas tablas

### Listar (reemplaza `db.listar()` que filtraba en memoria)

```sql
-- Listar ultimos 200, con JOIN a catalogos (antes: _load_all + loop Python)
SELECT 
  p.id, p.n_pedido, p.n_tr,
  t.clave AS tipo, t.nombre AS tipo_nombre,
  e.clave AS estado, e.nombre AS estado_nombre,
  cc.codigo AS cuenta_codigo, cc.nombre AS cuenta_nombre,
  per.nombre AS solicitante_nombre,
  prov.nombre AS proveedor_nombre,
  p.remito_nro, p.presupuesto_nro, p.notas,
  p.creado_por, p.creado_en, p.actualizado_en,
  COUNT(i.id) AS items_count
FROM solicitudes_pedidos p
JOIN solicitudes_tipos t ON t.id = p.tipo_id
JOIN solicitudes_estados e ON e.id = p.estado_id
LEFT JOIN cuentas_contables cc ON cc.id = p.cuenta_contable_id
LEFT JOIN personal per ON per.id = p.solicitante_id
LEFT JOIN proveedores prov ON prov.id = p.proveedor_id
LEFT JOIN solicitudes_items i ON i.solicitud_id = p.id
WHERE (p.estado_id = (SELECT id FROM solicitudes_estados WHERE clave='en_proceso') OR :estado IS NULL)
  AND (p.tipo_id = (SELECT id FROM solicitudes_tipos WHERE clave=:tipo) OR :tipo IS NULL)
  AND (:q IS NULL OR p.notas LIKE CONCAT('%',:q,'%') OR per.nombre LIKE CONCAT('%',:q,'%'))
GROUP BY p.id
ORDER BY p.creado_en DESC, p.id DESC
LIMIT 200;
```

Python equivalente:
```python
def listar(tipo=None, estado=None, q=None, limite=200):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            sql = """SELECT p.*, t.clave AS tipo, e.clave AS estado,
                            cc.codigo AS cuenta_codigo, per.nombre AS solicitante_nombre,
                            prov.nombre AS proveedor_nombre
                     FROM solicitudes_pedidos p
                     JOIN solicitudes_tipos t ON t.id=p.tipo_id
                     JOIN solicitudes_estados e ON e.id=p.estado_id
                     LEFT JOIN cuentas_contables cc ON cc.id=p.cuenta_contable_id
                     LEFT JOIN personal per ON per.id=p.solicitante_id
                     LEFT JOIN proveedores prov ON prov.id=p.proveedor_id
                     WHERE (%s IS NULL OR t.clave=%s)
                       AND (%s IS NULL OR e.clave=%s)
                     ORDER BY p.creado_en DESC LIMIT %s"""
            cur.execute(sql, (tipo, tipo, estado, estado, limite))
            pedidos = cur.fetchall()
            # Para cada pedido, cargar items + adjuntos en 2 queries mas (evita N+1 con IN)
            ...
            return pedidos
    finally:
        conn.close()
```

### Crear pedido con items (transaccion + contadores)

```python
def crear(data, rol=""):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # 1) Resolver FKs por clave/texto
            cur.execute("SELECT id FROM solicitudes_tipos WHERE clave=%s", (data["tipo"],))
            tipo_id = cur.fetchone()["id"]
            cur.execute("SELECT id FROM solicitudes_estados WHERE clave=%s", (data.get("estado","en_proceso"),))
            estado_id = cur.fetchone()["id"]
            # cuenta_contable: "7120001 - Conservacion..." -> split codigo
            codigo = data["cuenta_contable"].split(" - ")[0].strip()
            cur.execute("SELECT id FROM cuentas_contables WHERE codigo=%s", (codigo,))
            cc_id = (cur.fetchone() or {}).get("id")
            # solicitante: buscar en personal por nombre o legajo
            cur.execute("SELECT id FROM personal WHERE nombre=%s LIMIT 1", (data["solicitante"],))
            sol_id = (cur.fetchone() or {}).get("id")
            # proveedor: INSERT IGNORE si no existe (aprendido dinamico)
            prov_id = None
            if data.get("proveedor"):
                cur.execute("INSERT IGNORE INTO proveedores (nombre) VALUES (%s)", (data["proveedor"],))
                cur.execute("SELECT id FROM proveedores WHERE nombre=%s", (data["proveedor"],))
                prov_id = cur.fetchone()["id"]

            # 2) Contadores con bloqueo (SELECT FOR UPDATE)
            cur.execute("SELECT valor FROM solicitudes_contadores WHERE clave='id_seq' FOR UPDATE")
            # Si usas AUTO_INCREMENT para p.id, no necesitas id_seq. Mantener por compat Excel:
            cur.execute("UPDATE solicitudes_contadores SET valor=valor+1 WHERE clave='id_seq'")
            cur.execute("SELECT valor FROM solicitudes_contadores WHERE clave='id_seq'")
            # Alternativa simple: dejar que p.id sea AUTO_INCREMENT y solo incrementar pedido/tr

            # 3) Generar n_pedido / n_tr
            n_pedido = n_tr = None
            if data["tipo"] in ("normal","urgente"):
                cur.execute("UPDATE solicitudes_contadores SET valor=valor+1 WHERE clave='pedido'")
                cur.execute("SELECT valor FROM solicitudes_contadores WHERE clave='pedido'")
                n_pedido = f"P-{cur.fetchone()['valor']:04d}"
            elif data["tipo"]=="tr":
                cur.execute("UPDATE solicitudes_contadores SET valor=valor+1 WHERE clave='tr'")
                cur.execute("SELECT valor FROM solicitudes_contadores WHERE clave='tr'")
                n_tr = f"TR-{cur.fetchone()['valor']:04d}"

            # 4) Insert cabecera
            cur.execute("""
                INSERT INTO solicitudes_pedidos
                  (n_pedido, n_tr, tipo_id, estado_id, cuenta_contable_id, solicitante_id, proveedor_id, remito_nro, presupuesto_nro, notas, creado_por)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (n_pedido, n_tr, tipo_id, estado_id, cc_id, sol_id, prov_id, data.get("remito_nro"), data.get("presupuesto_nro"), data.get("notas"), data.get("creado_por")))
            pedido_id = cur.lastrowid

            # 5) Insert items
            for idx, it in enumerate(data["items"]):
                cur.execute("SELECT id FROM unidades_medida WHERE codigo=%s", (it.get("unidad"),))
                unidad_id = (cur.fetchone() or {}).get("id")
                cur.execute("""
                    INSERT INTO solicitudes_items (solicitud_id, orden, codigo, descripcion, cantidad, unidad_id, area_maquina)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                """, (pedido_id, idx, it.get("codigo"), it["descripcion"], it["cantidad"], unidad_id, it["area"]))

            conn.commit()
            return obtener(pedido_id)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

### Obtener pedido completo (cabecera + items + adjuntos)

```sql
SELECT p.*, t.clave AS tipo, e.clave AS estado FROM solicitudes_pedidos p
JOIN solicitudes_tipos t ON t.id=p.tipo_id
JOIN solicitudes_estados e ON e.id=p.estado_id
WHERE p.id = %s;

SELECT i.*, um.codigo AS unidad_codigo FROM solicitudes_items i
LEFT JOIN unidades_medida um ON um.id=i.unidad_id
WHERE i.solicitud_id=%s ORDER BY i.orden;

SELECT a.* FROM solicitudes_adjuntos a WHERE a.solicitud_id=%s ORDER BY a.creado_en;
-- Adjuntos de un item especifico:
SELECT * FROM solicitudes_adjuntos WHERE item_id=%s;
```

---

## 6. Estrategia de adjuntos - filesystem + tabla (NO BLOB)

### Por que NO BLOB

| BLOB en DB | Filesystem + tabla (elegido) |
|---|---|
| Infla `ibdata1`, backups pesados, HeidiSQL lento | DB liviana, archivos en disco, backup diferencial |
| No se puede servir por streaming sin cargar en RAM | `FileResponse(path)` directo, `X-Sendfile` si se quiere |
| Migracion Drive -> BLOB requiere re-encode base64 | Migracion 1:1: copiar archivos, insertar metadata |
| Limite `max_allowed_packet` (16MB) rompe PDFs grandes | Sin limite DB, solo limite FS/nginx |

### Por que tabla aparte SI (no campos `REMITO_ARCHIVO` texto)

- **1 pedido puede tener N adjuntos**: Excel tenia `REMITO_ARCHIVO` y `PRESUPUESTO_ARCHIVO` (max 2). Realidad: un pedido puede tener 3 remitos parciales, 2 presupuestos comparativos, etc. Tabla permite `N`.
- **1 item puede tener N imagenes**: `ITEM_IMAGEN` era 1 path por item. Ahora `solicitudes_adjuntos.item_id` permite 0..N imagenes por item (foto del repuesto, captura datasheet).
- **Trazabilidad y auditoria**: `subido_por`, `creado_en`, `mime`, `tamanio`, `tipo` (`remito/presupuesto/imagen_item/otro`). Antes no habia quien subio ni cuando.
- **No limitar a 1 campo**: `REMITO_ARCHIVO` como VARCHAR(255) impedia versionado. Tabla permite `ruta` VARCHAR(500) con estructura de carpetas por fecha.
- **CASCADE correcto**: `ON DELETE CASCADE` - si borras pedido, se borran adjuntos; si borras item, se borran sus imagenes. Con campo texto quedaban huerfanos.

### Como guardar

```
UPLOADS_DIR/
  solicitudes/
    2026/
      09/
        remito_a3f9c1e2b4d5.pdf
        presupuesto_7e1a9f3c0b2d.jpg
        imagen_item_9c4e1a2f8d6b.png
```

Codigo sugerido (`main.py:post_upload` migrado):

```python
import uuid
from pathlib import Path
from datetime import datetime

ALLOWED_EXT = {".jpg",".jpeg",".png",".webp",".gif",".pdf",".xlsx"}
ALLOWED_MIME = {"image/jpeg","image/png","image/webp","image/gif","application/pdf","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
MAX_SIZE = 10 * 1024 * 1024  # 10 MB

def _safe_ext(filename: str) -> str:
    ext = Path(filename or "").suffix.lower()
    return ext if ext in ALLOWED_EXT else ".bin"

async def post_upload(request: Request) -> JSONResponse:
    form = await request.form()
    upload = form.get("file")
    if not upload or not hasattr(upload, "filename"):
        return JSONResponse({"detail": "Archivo requerido (campo file)."}, status_code=400)
    content = await upload.read()
    if len(content) > MAX_SIZE:
        return JSONResponse({"detail": f"Archivo excede {MAX_SIZE//1024//1024} MB."}, status_code=400)
    ext = _safe_ext(str(upload.filename))
    mime = str(upload.content_type or "")
    if mime and mime not in ALLOWED_MIME and ext != ".bin":
        # Opcional: rechazar mime no permitido
        pass
    kind = re.sub(r"[^a-z0-9_]+", "", str(form.get("kind") or "archivo").lower()) or "archivo"
    # tipo ENUM: remito/presupuesto/imagen_item/otro
    tipo = str(form.get("tipo") or "otro").lower()
    if tipo not in ("remito","presupuesto","imagen_item","otro"):
        tipo = "otro"
    solicitud_id = form.get("solicitud_id")  # opcional, para vincular ya
    item_id = form.get("item_id")  # opcional, si es imagen de item

    # Ruta con fecha
    now = datetime.now()
    subdir = Path(str(now.year)) / f"{now.month:02d}"
    (UPLOADS_DIR / subdir).mkdir(parents=True, exist_ok=True)
    nombre_guardado = f"{kind}_{uuid.uuid4().hex[:12]}{ext}"
    dest = UPLOADS_DIR / subdir / nombre_guardado
    dest.write_bytes(content)
    ruta_rel = str(subdir / nombre_guardado).replace("\\","/")  # solicitudes/2026/09/...

    # Insert metadata en DB (si hay solicitud_id)
    if solicitud_id:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO solicitudes_adjuntos
                      (solicitud_id, item_id, tipo, nombre_original, nombre_guardado, ruta, mime, tamanio, subido_por)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (int(solicitud_id), int(item_id) if item_id else None, tipo, str(upload.filename), nombre_guardado, ruta_rel, mime, len(content), str(request.headers.get("x-user") or "")))
            conn.commit()
        finally:
            conn.close()

    return JSONResponse({"nombre_original": str(upload.filename), "nombre_guardado": nombre_guardado, "ruta": ruta_rel, "url": f"/api/solicitudes/archivos/{nombre_guardado}", "mime": mime, "tamanio": len(content)})
```

### Como servir

```python
from starlette.responses import FileResponse

async def get_archivo(request: Request) -> Response:
    name = request.path_params["name"]
    if ".." in name or "/" in name or "\\" in name:
        return JSONResponse({"detail": "Nombre invalido."}, status_code=400)
    # Buscar ruta real en DB (no confiar solo en FS - evita path traversal)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT ruta, mime FROM solicitudes_adjuntos WHERE nombre_guardado=%s LIMIT 1", (name,))
            row = cur.fetchone()
            if not row:
                # Fallback legacy: buscar directo en UPLOADS_DIR (para archivos pre-migracion)
                path = UPLOADS_DIR / name
                if not path.is_file():
                    # Buscar recursivo en subcarpetas por fecha
                    path = next(UPLOADS_DIR.rglob(name), None)
                    if not path or not path.is_file():
                        return JSONResponse({"detail": "Archivo no encontrado."}, status_code=404)
                return FileResponse(path)
            ruta = row["ruta"]
            # ruta es "2026/09/archivo.pdf" relativo a UPLOADS_DIR
            path = UPLOADS_DIR / ruta
            if not path.is_file():
                # compat: buscar por nombre_guardado en cualquier subdir
                path = next(UPLOADS_DIR.rglob(name), None)
                if not path:
                    return JSONResponse({"detail": "Archivo no encontrado en disco."}, status_code=404)
            return FileResponse(path, media_type=row["mime"] or None)
    finally:
        conn.close()
```

- **Validacion mimetype:** whitelist `image/jpeg, image/png, image/webp, image/gif, application/pdf, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`. Rechazar `application/x-msdownload`, `text/html` con JS, etc. Validar no solo por extension sino por `magic bytes` si se quiere (usar `python-magic`).
- **Tamano maximo:** 10 MB por archivo (configurable `SOLICITUDES_MAX_UPLOAD_MB`). Error 400 si excede.
- **Nombre guardado UNICO:** `UNIQUE(nombre_guardado)` evita colisiones. UUID 12 hex + ext garantiza unicidad sin exponer nombre original.
- **Ruta relativa:** `ruta` guarda `2026/09/<uuid>.ext` - portable entre `D:\` y `G:\`, no paths absolutos. Backup es `robocopy UPLOADS_DIR`.

---

## 7. Plan de migracion de datos Excel -> MariaDB (cuando se decida)

No ejecutar hoy. Pasos para manana/tarde:

1. **Backup:** copiar `solicitudes_pedidos.xlsx` y `solicitudes_adjuntos/` a `backup_2026-09-11/`
2. **Script:** reutilizar `db._leer_workbook()` para leer Excel y por cada `sol` hacer `crear()` via MariaDB (o script `migrar_excel_a_mariadb.py`)
   ```python
   solicitudes, contadores = _leer_workbook()  # existente
   for sol in solicitudes:
       # Adaptar: sol["cuenta_contable"] string -> codigo
       # sol["solicitante"] texto -> lookup personal.id (o crear generico si no existe)
       # sol["proveedor"] texto -> INSERT IGNORE proveedores
       # sol["items"] -> iterar
       # sol["remito_archivo"] / "presupuesto_archivo" -> si no vacio, copiar archivo G: -> UPLOADS_DIR y INSERT en solicitudes_adjuntos con tipo remito/presupuesto
       # sol["items"][i]["imagen_path"] -> copiar y INSERT con tipo imagen_item + item_id
   ```
3. **Verificar:** `SELECT COUNT(*) FROM solicitudes_pedidos` debe igualar `len(solicitudes)` Excel. `SHOW TABLES` + `SELECT` adjuntos.
4. **Corte:** cambiar `main.py` para importar `db_mariadb` en vez de `db_excel`. Mantener `db_excel.py` renombrado como backup.
5. **Rollback:** si falla, revertir import a `db_excel` y seguir con Excel. MariaDB queda con datos pero no en uso.

---

## 8. Next steps manana (checklist)

- [ ] Verificar en HeidiSQL/phpMyAdmin que las 8 tablas nuevas existen (ya hecho - ver `SHOW TABLES` abajo)
- [ ] Copiar `MIGRACION_A_MARIADB.md` a la wiki/docs y compartir con equipo
- [ ] Crear rama `feature/solicitudes-mariadb` - no tocar `main` aun
- [ ] Duplicar `backend/solicitudes/db.py` a `db_excel.py` (backup) y crear `db_mariadb.py` con funciones `listar/obtener/crear/actualizar/eliminar` usando `pymysql`
- [ ] Actualizar `backend/solicitudes/config.py` para agregar `DB_*` y mantener `EXCEL_PATH` como fallback con flag `SOLICITUDES_USE_DB=1`
- [ ] En `main.py` agregar `try: import db_mariadb as db except: import db as db` o flag
- [ ] Probar `python -m backend.solicitudes.db_mariadb` crea conexion ok (`SELECT 1`)
- [ ] Ejecutar migracion de datos Excel -> MariaDB en staging (copia local de Excel, no Drive productivo)
- [ ] Probar flujo completo: listar, crear pedido normal, crear TR con proveedor, subir remito PDF, subir imagen item, generar PDF/Excel, cambiar estado
- [ ] Cuando este verde, deploy: `SET SOLICITUDES_USE_DB=1` y reiniciar servicio puerto 8014

---

## 9. Comandos ejecutados (evidencia)

```powershell
# 1) Generar SQL
# C:\Users\Pañol\Desktop\sistemas_panol\Server\docs\panol_solicitudes_migracion_v1.sql (232 lineas, 14007 bytes)

# 2) Ejecutar idempotente (2 veces)
& "D:\xampp\mysql\bin\mysql.exe" -u root panol --default-character-set=utf8mb4 -e "SOURCE C:/Users/Pañol/Desktop/sistemas_panol/Server/docs/panol_solicitudes_migracion_v1.sql"
# EXIT_CODE: 0 (ambas veces)

# 3) Verificar
& "D:\xampp\mysql\bin\mysql.exe" -u root -N -e "SHOW TABLES FROM panol;"
# areas, cajas_cajas, cajas_herramientas, cajas_inventario_detalle, cajas_inventarios,
# cuentas_contables, personal, proveedores, solicitudes_adjuntos, solicitudes_contadores,
# solicitudes_estados, solicitudes_items, solicitudes_pedidos, solicitudes_tipos, unidades_medida (15)

& "D:\xampp\mysql\bin\mysql.exe" -u root -N -e "SELECT 'unidades_medida', COUNT(*) FROM panol.unidades_medida UNION ALL SELECT 'cuentas_contables', COUNT(*) FROM panol.cuentas_contables ...;"
# unidades_medida 6, cuentas_contables 14, solicitudes_estados 5, solicitudes_tipos 3, solicitudes_contadores 3, proveedores 0

& "D:\xampp\mysql\bin\mysql.exe" -u root -N -e "SHOW CREATE TABLE panol.solicitudes_pedidos\G"  # FKs OK
& "D:\xampp\mysql\bin\mysql.exe" -u root -N -e "SELECT TABLE_NAME, CONSTRAINT_NAME, REFERENCED_TABLE_NAME FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA='panol' AND REFERENCED_TABLE_NAME IS NOT NULL;"
# 9 FKs solicitudes_* verificadas (tipo/estado/cuenta/solicitante/proveedor/cascade)
```

---

## 10. Referencias

- `docs/cajas_esquema.md` - principio GENERALES vs `cajas_` (base del diseno)
- `backend/personal/db.py` + `backend/personal/config.py` - patron MariaDB ya migrado (puerto 8019)
- `backend/solicitudes/CATALOGOS_EDITABLES.json` - fuente de seeds (estados/tipos/cuentas/unidades)
- `backend/solicitudes/config.py` (EXCEL_PATH/UPLOADS_DIR en G:\)
- `backend/solicitudes/db.py` (715 lineas, `_FileLock`, `_escribir_workbook`)
- `backend/solicitudes/main.py` (upload con `_safe_ext`, rutas `/api/solicitudes/*`)
