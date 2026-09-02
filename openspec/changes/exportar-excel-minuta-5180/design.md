# Design: Exportar Excel Minuta 5180

## Technical Approach

Fresh `openpyxl.Workbook()` driven entirely from SQLite — no source workbook bytes. Export uses Starlette `StreamingResponse` over `BytesIO` (not FastAPI). Content-based column widths (`min(max_len + 2, 60)`), `wrapText=True`, computed row heights, hideable columns via `column_dimensions.hidden`, and sheet protection on the Novedades column only. Merge endpoint parses the "Novedades" sheet, matches by `pedido_id`, applies duplicate/consulta/no_reconocidas logic. Reuses existing `pedidos`/`novedades` tables with additive DB functions.

## Architecture Decisions

| Decision | Tradeoff | Resolution |
|----------|----------|------------|
| StreamingResponse over BytesIO vs temp file | BytesIO keeps it in-memory; temp file scales better | BytesIO — typical reunion <200 rows, memory is fine |
| openpyxl fresh workbook vs copy from template | No source workbook exists; template copy is impossible | Fresh workbook; data from SQLite, widths from content |
| Content-based auto-width vs fixed widths | Fixed widths fail "todo legible sin agrandar" requirement | Content-based: `min(max_content_len + 2, 60)` |
| Sheet protection Y-only vs workbook-level | Workbook protection locks everything; Y-only lets compras edit Novedades | Y-only (novedad_nueva_reunion unlocked, empty password) |
| No new DB table for consultas | New table adds migration overhead; merge summary suffices for this slice | Reuse existing `consultas` field on `pedidos`; consultas reported in merge summary only |
| unittest vs pytest | config.yaml mandates `python -m unittest -v`; no pytest in deps | unittest with Starlette `TestClient` |

## Data Flow

```
Frontend (TablaPedidosReunion)
  → minutaClient.exportarMinuta(reunionId, visibleCols)
    → GET /api/minuta/pedidos/exportar-excel?reunion_id=...&cols=orden,fecha,...
      → main.py: endpoint handler
        → db.listar_pedidos_reunion_export(reunion_id)  [ORDER BY orden ASC]
        → openpyxl.Workbook() → write rows → auto-width → wrapText → protection
        → StreamingResponse(BytesIO, media_type=..., headers={Content-Disposition})
    → Blob download → localStorage column-visibility persists

Import flow:
  Frontend → POST /api/minuta/pedidos/importar-novedades (multipart archivo)
    → main.py: parse "Novedades" sheet
      → db.importar_novedades_reunion(reunion_id, rows)
        → match by pedido_id → duplicate / consulta / no_reconocidas
        → return {procesadas, omitidas_duplicadas, pendientes_consulta, no_reconocidas, total_importadas}
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `backend/minuta_reunion/requirements.txt` | Modify | Add `openpyxl==3.1.5` |
| `backend/minuta_reunion/db.py` | Modify | Add `listar_pedidos_reunion_export(reunion_id)` and `importar_novedades_reunion(reunion_id, rows)` |
| `backend/minuta_reunion/main.py` | Modify | Add `GET /api/minuta/pedidos/exportar-excel` and `POST /api/minuta/pedidos/importar-novedades` routes |
| `backend/minuta_reunion/tests/test_export.py` | Create | unittest suite: export endpoint, import merge, protection, auto-width |
| `apps/web/src/modules/minuta/types.ts` | Modify | Add `ColumnVisibility` type and `ExportColumn` enum |
| `apps/web/src/modules/minuta/TablaPedidosReunion.tsx` | Modify | Add column-visibility checkbox panel in toolbar |
| `apps/web/src/modules/minuta/useMinutaSession.ts` | Modify | Add `columnVisibility` state persisted via localStorage |
| `apps/web/src/api/minutaClient.ts` | Modify | Add `exportarMinuta()` returning `Promise<Blob>` and `importarNovedadesMinuta()` |
| `apps/web/src/modules/minuta/MinutaReunionPage.tsx` | Modify | Add "Exportar Excel" button + column-visibility toggle UI |

## Interfaces / Contracts

### DB functions (db.py)

```python
def listar_pedidos_reunion_export(reunion_id: int) -> list[dict[str, Any]]:
    """Returns pedidos ordered by orden ASC with ultima_novedad, novedad_actual."""

def importar_novedades_reunion(reunion_id: int, rows: list[dict]) -> dict[str, int]:
    """Merge by pedido_id. Returns {procesadas, omitidas_duplicadas, pendientes_consulta, no_reconocidas, total_importadas}."""
```

### API contracts (main.py)

- `GET /api/minuta/pedidos/exportar-excel?reunion_id={id}&cols={comma-separated}` → `.xlsx` attachment, `Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- `POST /api/minuta/pedidos/importar-novedades` (multipart `archivo`) → `{procesadas, omitidas_duplicadas, pendientes_consulta, no_reconocidas, total_importadas}`

### Frontend types (types.ts)

```typescript
export type ExportColumn = "orden" | "fecha" | "n_pedido" | "oc" | "fecha_esperada" | "pedido" | "ultima_novedad" | "consultas" | "novedad_nueva_reunion" | "importancia" | "estado";
export type ColumnVisibility = Record<ExportColumn, boolean>;
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `listar_pedidos_reunion_export` returns rows ordered by orden | `unittest` + `TestClient` against in-memory SQLite |
| Unit | `importar_novedades_reunion` duplicate/consulta/no_reconocidas | Seed DB, call merge, assert counts |
| Unit | `importar_novedades_reunion` no_reconocidas for unknown pedido_id | Assert 0 new rows, correct count |
| Integration | Export endpoint returns valid `.xlsx` with correct Content-Type | `TestClient` GET → validate with `openpyxl.load_workbook(BytesIO(...))` |
| Integration | Export endpoint 404 for missing/archived reunion | `TestClient` GET → assert 404 |
| Integration | Import endpoint 400 without "Novedades" sheet | Upload wrong sheet → assert 400 |
| Unit | Column-width calculation `min(max_len + 2, 60)` | Direct function call |

No pytest available; all tests use `python -m unittest -v` per config.yaml.

## Threat Matrix

N/A — no routing boundary changes that introduce shell commands, subprocess calls, VCS/PR automation, executable-file classification, or process-integration boundaries. The new endpoints are pure HTTP GET/POST with DB reads and openpyxl generation.

## Migration / Rollout

No migration required. DB functions are additive (safe to leave). `openpyxl` added to `requirements.txt`. Frontend changes are behind the existing component tree — no feature flag needed since the Exportar Excel button is a natural extension. Rollback: remove new routes from `main.py` routing, revert `requirements.txt`; DB functions remain harmless.

## Open Questions

- [ ] Confirm `cols` query param uses column keys matching `ExportColumn` enum exactly
- [ ] Confirm row-height formula: `row_dimensions.height = max_lines * 15` (15pt default line height) vs other factor
- [ ] Confirm whether archived reuniones (`archivada=1`) should be blocked (spec says 404) or allowed
