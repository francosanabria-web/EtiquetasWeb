# Delta for BuscadorShared

## ADDED Requirements

### Requirement: Shared Component Relocation

The system MUST relocate `BuscadorCatalogo` from `apps/web/src/modules/solicitudes/BuscadorCatalogo.tsx` to `apps/web/src/components/shared/BuscadorCatalogo.tsx`. The moved component MUST preserve the complete props API: `value`, `onCodigoChange`, `onPick`, and optional `disabled`. After relocation, all consumers (solicitudes and cajas modules) MUST import from the shared path. TypeScript compilation via `tsc --noEmit` MUST pass without errors.

- GIVEN the original `BuscadorCatalogo.tsx` exists in `modules/solicitudes/`
- WHEN the component is moved to `components/shared/BuscadorCatalogo.tsx` with identical source
- THEN the shared path import `import BuscadorCatalogo from "../shared/BuscadorCatalogo"` works in `IdealEditorModal.tsx`
- AND the re-export/update import `import BuscadorCatalogo from "../shared/BuscadorCatalogo"` works in solicitudes-consuming files
- AND `tsc --noEmit` completes with zero errors

### Requirement: ArticulosCatalog Behavior Preservation

The system MUST ensure `lib/articulosCatalog.ts` behavior remains identical after the move. Specifically, `ensureCatalogLoaded()` MUST resolve to the same cached Firestore `articulos` collection, and `filterArticulos(catalog, query)` MUST enforce `MAX_SEARCH_RESULTS = 100` and return `{ items, totalMatches }` with client-side query splitting on whitespace. No new dependencies or type changes are permitted.

- GIVEN the relocated `BuscadorCatalogo` imports from `../../lib/articulosCatalog`
- WHEN `ensureCatalogLoaded()` is called
- THEN it returns the same `memoryCatalog` cache or triggers Firestore `getDocs` on `articulos` collection
- AND `filterArticulos()` splits the query on whitespace, checks each palabra against `codigo + desc + alias`, and caps items at 100
- AND the component renders correctly with the same `ArticuloCatalogo` type

## MODIFIED Requirements

### Requirement: IdealEditorModal Import Re-Pointer

The IdealEditorModal import for `BuscadorCatalogo` MUST be modified to resolve from the shared path instead of the solicitudes-relative path. The import statement `import BuscadorCatalogo from "../solicitudes/BuscadorCatalogo"` MUST be replaced with `import BuscadorCatalogo from "../shared/BuscadorCatalogo"` while preserving the exact same prop usage: `value`, `onCodigoChange`, and `onPick` callbacks.

- GIVEN `IdealEditorModal.tsx` previously imported from `../solicitudes/BuscadorCatalogo`
- WHEN the import is changed to `../shared/BuscadorCatalogo`
- THEN the component renders identically with the BuscadorCatalogo modal
- AND `handlePick` and `handleCodigoChange` callbacks maintain their signatures
- AND the type `ArticuloCatalogo` import from `../../lib/articulosCatalog` remains valid
- Previously: imported from `../solicitudes/BuscadorCatalogo` (relative to cajas module)

## REMOVED Requirements

### Requirement: Duplicate Local BuscadorCatalogo

The local instance of `BuscadorCatalogo` within `modules/solicitudes/` that duplicated the shared catalog search logic IS REMOVED. Only the single shared version under `components/shared/` MUST exist. Any stale references that import from the old solicitudes-relative path are updated to the shared path.

- GIVEN the move to `components/shared/BuscadorCatalogo.tsx`
- WHEN the old file at `modules/solicitudes/BuscadorCatalogo.tsx` is deleted
- THEN no import from `../solicitudes/BuscadorCatalogo` should resolve
- AND the shared file at `components/shared/BuscadorCatalogo.tsx` is the canonical source
- AND `tsc --noEmit` confirms zero unresolved imports

## RENAMED Requirements

No requirements renamed in this spec.