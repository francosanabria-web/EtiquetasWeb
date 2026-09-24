# Delta for LimpiezaAsignaciones

## ADDED Requirements

### Requirement: cajas_limpieza_historial Table Creation

The system MUST CREATE TABLE `cajas_limpieza_historial` with the following schema, idempotent execution (IF NOT EXISTS), InnoDB engine, and utf8mb4 unicode collation:

- `id` INT AUTO_INCREMENT PRIMARY KEY
- `caja_id` INT NOT NULL, FK to `cajas_cajas(id)` ON DELETE RESTRICT
- `tecnico_id` INT NOT NULL, FK to `personal(id)` ON DELETE RESTRICT
- `fecha` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
- `estado` ENUM('pendiente', 'realizada', 'vencida') NOT NULL DEFAULT 'pendiente'
- `responsable_id` INT NULL, FK to `personal(id)` (who registered the event)
- `observaciones` TEXT NULL
- INDEX `idx_limpieza_caja_fecha` on (caja_id, fecha)
- INDEX `idx_limpieza_estado_fecha` on (estado, fecha)

The table creation DDL MUST be idempotent and follow the same patterns as `init_db()` in `backend/cajas/db.py`. Prefix all table and column names with `cajas_` convention. Engine=InnoDB, charset=utf8mb4, collate=utf8mb4_unicode_ci.

- GIVEN the table does not exist
- WHEN the DDL executes via `init_db()` or equivalent migration
- THEN the table is created with all columns, FKs, and indexes
- WHEN the DDL executes again (idempotent)
- THEN no error is thrown; table remains unchanged
- AND the RESTRICT FKs prevent deletion of referenced cajas or personal rows

### Requirement: cajas_asignaciones Table Creation

The system MUST CREATE TABLE `cajas_asignaciones` with the following schema, idempotent execution, InnoDB engine, and utf8mb4 collation:

- `id` INT AUTO_INCREMENT PRIMARY KEY
- `caja_id` INT NOT NULL, FK to `cajas_cajas(id)` ON DELETE RESTRICT
- `tecnico_id` INT NOT NULL, FK to `personal(id)` ON DELETE RESTRICT
- `desde` DATE NOT NULL (start date of assignment)
- `hasta` DATE NULL (end date; NULL = currently active)
- `activa` BOOLEAN NOT NULL DEFAULT 1
- UNIQUE KEY `uq_asig_caja_tecnico_desde` on (caja_id, tecnico_id, desde)
- INDEX `idx_asig_tecnico_abierta` on (tecnico_id, hasta)
- CONSTRAINT ensuring that only one active assignment (hasta IS NULL, activa=1) per caja_id exists via application logic or DB constraint

The table creation DDL MUST follow the same patterns as `init_db()`. Match `cajas_cajas.id` signedness (INT signed).

- GIVEN the table does not exist
- WHEN the DDL executes
- THEN the table is created with all columns, FKs, UNIQUE constraint, and indexes
- WHEN the DDL executes again (idempotent)
- THEN no error is thrown; table remains unchanged
- AND the UNIQUE constraint prevents duplicate active assignments

### Requirement: Limpieza CRUD API under /api/cajas/limpieza

The system MUST provide CRUD endpoints under `/api/cajas/limpieza`:

- **GET /api/cajas/limpieza** — List all limpieza events with optional filters (caja_id, tecnico_id, estado). Pagination: limit/offset, default limit 50, max 100. Requires `cajas:lectura` permission.
- **POST /api/cajas/limpieza** — Create a new limpieza event. Requires `cajas:escritura` permission. Body: `{ caja_id, tecnico_id, estado, responsable_id?, observaciones? }`. Returns created event with id, fecha DEFAULT CURRENT_TIMESTAMP.
- **PATCH /api/cajas/limpieza/{event_id}** — Update event estado and/or observaciones. Requires `cajas:escritura` permission. Only estado transition to 'realizada' or 'vencida' allowed from 'pendiente'.
- **DELETE /api/cajas/limpieza/{event_id}** — Delete event only if estado = 'pendiente'. Requires `cajas:escritura` permission. Returns 409 if event is not pending.

All endpoints MUST verify permissions via `verificar_permiso` with exact `:lectura`/`:escritura` suffix matching (per the permisos-estrictos spec).

- GIVEN a GET request with valid `cajas:lectura` token
- WHEN the endpoint lists events
- THEN it returns paginated items with total count
- AND filters by caja_id, tecnico_id, or estado when provided
- GIVEN a POST request with valid `cajas:escritura` token
- WHEN the body has required fields
- THEN the event is created with fecha = CURRENT_TIMESTAMP
- AND RESTRICT FKs enforce referential integrity
- GIVEN a PATCH request with estado='realizada'
- WHEN the event exists and is pending
- THEN estado is updated to 'realizada'
- GIVEN a DELETE request on a non-pending event
- WHEN the event estado is 'realizada' or 'vencida'
- THEN the endpoint returns 409 Conflict with detail "No se puede eliminar un evento de limpieza que no está en estado pendiente"

### Requirement: Asignaciones CRUD API under /api/cajas/asignaciones

The system MUST provide CRUD endpoints under `/api/cajas/asignaciones`:

- **GET /api/cajas/asignaciones** — List all assignments with optional filters (caja_id, tecnico_id, activa). Pagination: limit/offset, default limit 50, max 100. Requires `cajas:lectura` permission.
- **POST /api/cajas/asignaciones** — Assign a technician to a caja. Requires `cajas:escritura` permission. Body: `{ caja_id, tecnico_id, desde }`. Logic: if an active assignment (hasta IS NULL, activa=1) already exists for this caja_id, it MUST be closed (set hasta=NOW, activa=0) before the new assignment is recorded. Returns the new assignment record.
- **PATCH /api/cajas/asignaciones/{assign_id}** — Close an assignment. Sets `hasta=NOW`, `activa=0`. Requires `cajas:escritura` permission.
- **DELETE /api/cajas/asignaciones/{assign_id}** — Hard delete only if `activa=0` and `hasta` is not NULL. Returns 409 if the assignment is currently active (hasta IS NULL, activa=1).

Scenarios for assign behavior:

- **Assign caja to tecnico**: GIVEN no active assignment exists for the caja, WHEN POST creates the assignment, THEN the new row is inserted with `desde=NOW` date, `hasta=NULL`, `activa=1`
- **Reassign same caja → closes previous**: GIVEN an active assignment exists for the caja_id, WHEN POST creates a new assignment for the same caja, THEN the previous assignment is closed (hasta = NOW, activa = 0) and the new assignment is inserted
- **Duplicate active → 409**: GIVEN an active assignment (hasta IS NULL, activa=1) already exists for the same (caja_id, tecnico_id), WHEN POST attempts a new assignment, THEN the endpoint returns 409 Conflict with detail "Ya hay una asignación activa para esta caja y técnico"

- GIVEN a GET request with valid `cajas:lectura` token
- WHEN the endpoint lists assignments
- THEN it returns paginated items with total count
- AND filters by caja_id, tecnico_id, or activa when provided
- GIVEN a POST request with valid `cajas:escritura` token and no active assignment for the caja
- WHEN the body has required fields (caja_id, tecnico_id, desde)
- THEN the new assignment is inserted with desde, hasta=NULL, activa=1
- AND the previous (if any) active assignment for the same caja is closed first
- GIVEN a POST request with duplicate active assignment
- WHEN the same (caja_id, tecnico_id) already has an active assignment
- THEN the endpoint returns 409 Conflict "Ya hay una asignación activa para esta caja y técnico"

## MODIFIED Requirements

No modified requirements in this spec (new tables and APIs).