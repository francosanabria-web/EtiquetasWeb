# Infra — Shared API Conventions Specification

## Purpose

Minimal shared API conventions for the cajas hub change, ensuring consistent request/response patterns, error handling, and pagination across all new endpoints. Keeps changes isolated and avoids cross-module coupling.

## Requirements

### Requirement: Consistent Error Response Format

The system MUST return consistent error responses across all new /api/cajas/* endpoints. HTTP 400 for validation errors, 401 for missing/invalid auth, 404 for not found, and 409 for FK RESTRICT violations.

- GIVEN any new endpoint under /api/cajas/ideal, /api/cajas/tecnicos-cards, or /api/cajas/kpis
- WHEN the endpoint encounters a validation error
- THEN it returns JSON {"detail": "error message"} with status_code 400
- AND the detail message is human-readable and in Spanish (project convention)

### Requirement: Pagination Convention (limit/offset)

The system MUST use limit/offset pagination convention for all list endpoints. Default limit 50, max limit 100. All list endpoints accept ?limit&offset query parameters.

- GIVEN a list endpoint under /api/cajas/tecnicos-cards or /api/cajas/kpis/resumen
- WHEN the request includes limit and offset parameters
- THEN the endpoint respects the parameters and returns the correct page
- AND the response header includes total count for client-side pagination
- AND default limit is 50, maximum limit is 100

### Requirement: JWT Authorization Header

The system MUST use JWT Bearer token authorization convention. All new endpoints require Authorization: Bearer <token> header. Token verification follows existing verificar_permiso pattern with "cajas:lectura" or "cajas:escritura" permissions.

- GIVEN a request to any new /api/cajas/* endpoint
- WHEN the request lacks an Authorization header or has invalid token
- THEN the endpoint returns 401 Unauthorized with {"detail": "No autorizado"}
- AND the existing service.py permission check pattern is reused without modification
- AND the token is verified via _token(request) helper that extracts Bearer token from auth header

### Requirement: Response Model Consistency

The system MUST maintain response model consistency for ideal, tecnico-card, and KPI endpoints. Successful responses return the created/retrieved object structure matching the store layer output.

- GIVEN a successful GET /api/cajas/ideal request
- WHEN the endpoint returns a response
- THEN the JSON body matches the structure: {"id": int, "nombre": str, "activa": bool, "vigente_desde": datetime, "herramientas": [...]}
- AND successful GET /api/cajas/tecnicos-cards returns {"items": [...], "total": int} structure
- AND successful GET /api/cajas/kpis/resumen returns {"tecnicos": [...], "global": {...}} structure

## Scenarios

#### Scenario: Validation Error Returns 400

- GIVEN a POST /api/cajas/ideal request with invalid data (missing required fields)
- WHEN the service layer raises ValueError
- THEN the endpoint returns JSONResponse({"detail": "error message"}, status_code=400)
- AND the error message clearly describes what is missing or invalid

#### Scenario: FK RESTRICT Violation Returns 409

- GIVEN a DELETE or PUT operation that would violate FK RESTRICT on cajas_herramientas or cajas_caja_ideal
- WHEN the database raises IntegrityError
- THEN the service layer catches IntegrityError and returns (msg, 409)
- AND the response body includes {"detail": "No se puede eliminar: tiene registros asociados."} or similar

#### Scenario: Unauthorized Access Returns 401

- GIVEN a request to /api/cajas/kpis/resumen without Authorization header
- WHEN the endpoint processes the request
- THEN it returns JSONResponse({"detail": "No autorizado"}, status_code=401)
- AND the token verification flow (_verificar_jwt → _verificar_sesion_opaca) returns None

#### Scenario: Pagination Defaults Apply

- GIVEN a GET /api/cajas/tecnicos-cards request without limit/offset parameters
- WHEN the endpoint processes the request
- THEN it uses default limit = 50 and offset = 0
- AND returns the first 50 técnicos cards with total count available