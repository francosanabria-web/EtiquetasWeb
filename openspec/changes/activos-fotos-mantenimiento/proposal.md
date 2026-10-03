# Proposal: activos-fotos-mantenimiento

## Intent

Fix Fuera de Planta gaps: no photos, no sector isolation, no approval/audit, late alerts. Pañol creates (`POST /api/activos/salida`); supervisors edit/return cross-sector. Add DB photos, sector-scoped return + approval, encargado tracking, mail hooks. No QR.

## Scope

### In Scope
- DB photos: `salida_activos_fotos` (MEDIUMBLOB/LONGTEXT base64 + `hash_sha256`), 1-3 at withdrawal (+remito), 1 at return; WebP 1280px, 5 MB, `GET /api/activos/{id}/fotos` auth.
- Permissions: VIEW all; WRITE own sector only; approval `pendiente`→`aprobado` (pañol/jefatura).
- Encargado: `encargado_salida_id` FK→`personal.id` (dropdown supervisores/jefes, sector chained).
- Ingreso: Fecha+Estado+Foto+checkbox "Confirmo recepción conforme" + audit `usuario_id`.
- Notifications: mail to pañol on create/edit; overdue alert to encargado; parallel `PanolMailActivos0800_LV` hook.

### Out of Scope
- QR; filesystem/G: storage; new roles (reuse `personal`); OCR/barcode.

## Capabilities

### New Capabilities
- `activos-fotos`: DB photo evidence + validation/hash/auth retrieval.
- `activos-permisos-sector`: sector-scoped write + approval + encargado chaining.
- `activos-notificaciones`: event + overdue mails (hook).

### Modified Capabilities
- None.

## Approach

**Phase 1 — Data & Permissions:** migration v2 (`docs/activos_migracion_v1.sql` successor: `encargado_salida_id`, approval cols, `salida_activos_fotos`); extend `backend/activos/db.py`, `store.py`, `write_ops.py`, `main.py` (`POST/GET /{id}/fotos`, `POST /{id}/aprobar`); frontend `ActivosPanel.tsx` (WebP uploader, chained selector, ingreso modal, gate via `backend/usuarios/config.py`+`backend/personal`).

**Phase 2 — Notifications:** hook `mail_activos.py` (reuse `DIAS_AVISO=21`/`DIAS_ALERTA=30`); parallel daily 08:00.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `backend/activos/db.py` | Modified | New table init |
| `backend/activos/write_ops.py` | Modified | Photo validate/hash/BLOB, FK, approval |
| `backend/activos/store.py`+`main.py` | Modified | Photo endpoints, sector filter, approval |
| `docs/activos_migracion_v1.sql` | Modified | Migration v2 |
| `apps/web/src/components/activos/ActivosPanel.tsx` | Modified | Upload/compress, selector, modal |
| `backend/activos/mail_activos.py` | Modified | Immediate + overdue hooks |
| `backend/personal/*` | Read | Encargado dropdown |
| `backend/usuarios/config.py` | Read | Permission gate |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| DB bloat (1-3×5 MB/row) | High | 5 MB cap, WebP, max 3, separate endpoint, monitor |
| List perf (BLOB) | Med | Never embed in list; index `salida_activo_id` |
| `personal`→sector map | Med | `area_id`→`areas.nombre`; manual fallback |
| Sector spoof | Low | Server-side `personal` check |

## Rollback Plan

Flag `ACTIVOS_FOTOS_ENABLED` off. Rollback: `DROP TABLE salida_activos_fotos` + `ALTER DROP COLUMN`, redeploy prev, disable hook. Backup BLOBs.

## Dependencies

- MariaDB `panol` DDL; `personal`/`areas` seeded; SMTP `PANOL_SMTP_*`; `canvas` WebP.

## Success Criteria

- [ ] Withdrawal enforces 1-3 WebP + hash; `GET /{id}/fotos` auth OK
- [ ] View all, write own-sector only; approval by pañol/jefatura
- [ ] `encargado_salida_id` + chained sector + audit logged
- [ ] Mail on create/edit + overdue to encargado; daily 08:00 still fires
- [ ] No QR/filesystem shipped

## Open Questions

- Confirm `personal.area_id` as sector truth? Handle `tecnico/produccion`?
