# Delta for PermisosEstrictos

## ADDED Requirements

### Requirement: Exact Suffix Matching for :lectura

The system MUST enforce exact suffix matching for `:lectura` in `verificar_permiso`. When the required permission ends with `:lectura`, the user's nivel MUST be either `lectura` or `escritura` to grant access. No other nivel values are acceptable for this suffix. A generic catch-all that grants access based on `nivel != "sin_acceso"` is removed.

- GIVEN a request with `verificar_permiso(token, "cajas:lectura")`
- WHEN the user's nivel is `lectura`
- THEN the function returns the payload (access granted)
- AND when the user's nivel is `escritura`
- THEN the function returns the payload (access granted, because escritura encompasses lectura)
- WHEN the user's nivel is any other value (e.g., `admin`, `supervisor` without escritura)
- THEN the function returns `None` (access denied)
- AND the `nivel != "sin_acceso"` catch-all branch is eliminated from the code path

### Requirement: Exact Suffix Matching for :escritura

The system MUST enforce exact suffix matching for `:escritura` in `verificar_permiso`. When the required permission ends with `:escritura`, the user's nivel MUST be exactly `escritura` — no other nivel value grants access. The previous lenient fallback that allowed any non-`sin_acceso` nivel is removed.

- GIVEN a request with `verificar_permiso(token, "cajas:escritura")`
- WHEN the user's nivel is `escritura`
- THEN the function returns the payload (access granted)
- WHEN the user's nivel is `lectura` or any other value
- THEN the function returns `None` (access denied)
- AND the catch-all `if nivel != "sin_acceso": return payload` branch is eliminated

## MODIFIED Requirements

### Requirement: verificar_permiso Core Logic Overhaul

The `verificar_permiso` function in `backend/cajas/db.py` MUST be refactored to remove the generic catch-all and replace it with explicit, non-overlapping suffix checks. The new logic:

- `if permiso_requerido.endswith(":lectura") and nivel in ("lectura", "escritura"): return payload`
- `if permiso_requerido.endswith(":escritura") and nivel == "escritura": return payload`
- All other cases return `None`

The two existing `if` blocks for `:lectura` and `:escritura` remain, but the `if nivel != "sin_acceso": return payload` catch-all at lines 262-263 (JWT) and 273-274 (sesion opaca) is REMOVED. This ensures that unimpeded access based on generic nivel checks can no longer occur.

- GIVEN the original `verificar_permiso` with the catch-all fallback
- WHEN the function is refactored to remove `if nivel != "sin_acceso": return payload`
- THEN `:lectura` only grants when nivel is `lectura` or `escritura`
- THEN `:escritura` only grants when nivel is exactly `escritura`
- THEN any other combination returns `None`
- AND previously authorized flows with mismatched nivel/suffix are now rejected
- Previously: the catch-all at db.py:262-263 and db.py:273-274 granted any non-sin_acceso nivel for any suffix

## REMOVED Requirements

### Requirement: Lenient Catch-All Permission Fallback

The `if nivel != "sin_acceso": return payload` catch-all block in `verificar_permiso` (both JWT and sesion opaca code paths) IS REMOVED. This block previously allowed any user with a non-`sin_acceso` nivel to pass permission checks regardless of suffix matching, creating a security hole. Its removal closes the vulnerability but requires all call sites to use properly suffixed permiso strings (`:lectura` or `:escritura`).

- GIVEN the removal of the catch-all branch
- WHEN a call site previously relied on the lenient fallback
- THEN the call returns `None` instead of granting access
- AND the call site must be updated to use the correct `:lectura`/`:escritura` suffix
- The JWT path (db.py:262-263) and sesion opaca path (db.py:273-274) both lose this block

## RENAMED Requirements

No requirements renamed in this spec.