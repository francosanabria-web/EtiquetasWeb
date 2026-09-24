# Caja Ideal Specification

## Purpose

Versioned Caja Ideal baseline toolkit editor with embedded catalog search, singleton-active invariant, and transactional versioning. Card A of the cajas hub provides CRUD via manual carga using BuscadorCatalogo over Firestore articulos, enforcing UNIQUE(caja_ideal_id, herramienta_id) and RESTRICT foreign keys.

## Requirements

### Requirement: Versioned Caja Ideal Exposure

The system MUST expose a versioned Caja Ideal (generic for any technician, not per-line/rubro) with singleton-active invariant — exactly one row with activa=1 at any time, historial preserved via versioned rows. Current implementation uses versioned table with `activa` flag and `vigente_desde` timestamp; all prior versions retained for point-in-time KPI comparability.

- GIVEN the Caja Ideal table exists with versioned rows
- WHEN a new ideal is activated transactionally
- THEN exactly one row has activa=1 and all prior rows are set to activa=0 within the same transaction
- AND previous versions are retained in the table for historical KPI queries

### Requimiento: CRUD via Manual Carga con BuscadorCatalogo

The system MUST allow CRUD via manual carga: select herramienta via BuscadorCatalogo (buscar por codigo/desc/alias over Firestore articulos), persist codigo + articulo_codigo if exists, cantidad_minima, etc.

- GIVEN the user opens the Caja Ideal editor modal
- WHEN the user searches for a herramienta using BuscadorCatalogo with codigo or alias
- THEN the catalog returns matching articulos from Firestore articulos collection
- AND the user can select a herramienta, persisting its codigo and articulo_codigo (if exists) to cajas_caja_ideal_detalle
- AND the system stores cantidad_minima from the selected herramienta record

### Requirement: UNIQUE Constraint and FK RESTRICT

The system MUST enforce UNIQUE(caja_ideal_id, herramienta_id) and FK RESTRICT to cajas_herramientas. Duplicate herramienta assignments to the same ideal must be rejected with HTTP 409 Conflict.

- GIVEN a Caja Ideal with existing herramienta assignments
- WHEN the user attempts to assign a herramienta already linked to the current ideal
- THEN the system rejects the operation and returns 409 Conflict with message "Herramienta ya asignada a esta Caja Ideal"
- AND the original assignment remains unchanged

### Requirement: Singleton-Active Invariant Transactional Enforcement

The system MUST enforce singleton-active invariant transactionally. Transaction must reset all prior activa=0 before inserting new activa=1, preventing concurrent activation race conditions.

- GIVEN multiple users attempting to activate different Caja Ideal versions simultaneously
- WHEN a transaction begins to activate a new ideal version
- THEN all existing rows have activa set to 0 atomically before the new row is inserted with activa=1
- AND the transaction completes with exactly one active row, or rolls back entirely

### Requirement: List Ideal Detalle

The system MUST allow listing the Caja Ideal detalle — all herramienta assignments with their current state.

- GIVEN the user requests the Caja Ideal detail view
- WHEN the system queries cajas_caja_ideal_detalle for the current ideal
- THEN each herramienta assignment is returned with herramienta_codigo, cantidad_minima, and assignment status
- AND the list includes historical versions if the user requests point-in-time view

## Scenarios

#### Scenario: Create Ideal with Buscador Pick

- GIVEN the Caja Ideal editor is open with no current ideal active
- WHEN the user clicks "Buscar herramienta" in BuscadorCatalogo and selects a herramienta by codigo
- THEN the selected herramienta's codigo and articulo_codigo are persisted to the ideal detail
- AND cantidad_minima is populated from the herramienta record
- AND the ideal row is created with activa=1 and vigente_desde = now

#### Scenario: Add Duplicate Herramienta -> 409

- GIVEN a Caja Ideal with herramienta A already assigned
- WHEN the user attempts to assign herramienta A again to the same ideal
- THEN the system returns 409 Conflict
- AND the error message indicates "Herramienta ya asignada a esta Caja Ideal"
- AND herramienta A remains as the only assignment

#### Scenario: Concurrent Activation

- GIVEN two users simultaneously attempt to activate different Caja Ideal versions
- WHEN both transactions begin the singleton-active reset sequence
- THEN one transaction completes first, setting its version as the active ideal
- AND the second transaction either waits or rolls back, ensuring exactly one activa=1 row remains
- AND the system never has zero or two active ideals simultaneously

#### Scenario: Update Ideal

- GIVEN an active Caja Ideal with existing herramienta assignments
- WHEN the user adds a new herramienta via BuscadorCatalogo and saves
- THEN the new herramienta is added to the detail with its codigo and articulo_codigo
- AND the singleton-active invariant is re-enforced (all activa=0, then new version activa=1)
- AND the update is transactionally consistent

#### Scenario: List Ideal Detalle

- GIVEN the user views the Caja Ideal detail page
- WHEN the system retrieves cajas_caja_ideal_detalle for the current ideal
- THEN each herramienta assignment displays codigo, descripcion, cantidad_minima, and status
- AND the list includes all currently assigned herramientas
- AND historical assignments from prior versions are available if querying point-in-time