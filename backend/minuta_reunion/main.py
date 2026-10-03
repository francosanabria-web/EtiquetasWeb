# -*- coding: utf-8 -*-
"""API de minutas por sector — pedidos, novedades e historial (Starlette)."""

from __future__ import annotations

import io
import json
import os
import re
import traceback
from datetime import date, datetime

from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Route

import db

try:
    import openpyxl
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Protection, Side

    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

db.init_db()


async def health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "minuta-reunion"})


async def get_sectores(_: Request) -> JSONResponse:
    return JSONResponse({"sectores": db.listar_sectores()})


async def get_pedidos(request: Request) -> JSONResponse:
    reunion_id = (request.query_params.get("reunion_id") or "").strip()
    sector = (request.query_params.get("sector") or "").strip()
    solo_activos = request.query_params.get("activos", "1") != "0"
    try:
        if reunion_id:
            pedidos = db.listar_pedidos_reunion(int(reunion_id), solo_activos=solo_activos)
        elif sector:
            pedidos = db.listar_pedidos_sector(sector, solo_activos=solo_activos)
        else:
            return JSONResponse(
                {"detail": "reunion_id o sector requerido."}, status_code=400
            )
        return JSONResponse({"pedidos": pedidos})
    except Exception as e:
        return JSONResponse({"detail": str(e)}, status_code=400)


async def get_pedido(request: Request) -> JSONResponse:
    pedido_id = int(request.path_params["id"])
    pedido = db.obtener_pedido(pedido_id)
    if not pedido:
        return JSONResponse({"detail": "Pedido no encontrado."}, status_code=404)
    return JSONResponse({"pedido": pedido})


async def post_pedido(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"detail": "JSON inválido."}, status_code=400)
    try:
        pedido = db.crear_pedido(body)
        return JSONResponse({"pedido": pedido}, status_code=201)
    except ValueError as e:
        return JSONResponse({"detail": str(e)}, status_code=400)


async def patch_pedido(request: Request) -> JSONResponse:
    pedido_id = int(request.path_params["id"])
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"detail": "JSON inválido."}, status_code=400)
    pedido = db.actualizar_pedido(pedido_id, body)
    if not pedido:
        return JSONResponse({"detail": "Pedido no encontrado."}, status_code=404)
    return JSONResponse({"pedido": pedido})


async def delete_pedido(request: Request) -> JSONResponse:
    pedido_id = int(request.path_params["id"])
    ok = db.eliminar_pedido(pedido_id)
    if not ok:
        return JSONResponse({"detail": "Pedido no encontrado."}, status_code=404)
    return JSONResponse({"ok": True})


async def post_novedad(request: Request) -> JSONResponse:
    pedido_id = int(request.path_params["id"])
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"detail": "JSON inválido."}, status_code=400)
    try:
        pedido = db.agregar_novedad(pedido_id, body)
    except ValueError as e:
        return JSONResponse({"detail": str(e)}, status_code=400)
    if not pedido:
        return JSONResponse({"detail": "Pedido no encontrado."}, status_code=404)
    return JSONResponse({"pedido": pedido}, status_code=201)


async def put_novedad(request: Request) -> JSONResponse:
    """Upsert de novedad de la fecha de reunion (sync multi-PC)."""
    pedido_id = int(request.path_params["id"])
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"detail": "JSON inválido."}, status_code=400)
    try:
        pedido = db.upsert_novedad(pedido_id, body)
    except ValueError as e:
        return JSONResponse({"detail": str(e)}, status_code=400)
    if not pedido:
        return JSONResponse({"detail": "Pedido no encontrado."}, status_code=404)
    return JSONResponse({"pedido": pedido})


async def post_reordenar(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"detail": "JSON inválido."}, status_code=400)
    reunion_id = body.get("reunion_id")
    ids = body.get("ids")
    if not reunion_id or not isinstance(ids, list):
        return JSONResponse(
            {"detail": "reunion_id e ids (lista) requeridos."}, status_code=400
        )
    try:
        pedidos = db.reordenar_pedidos(int(reunion_id), [int(i) for i in ids])
        return JSONResponse({"pedidos": pedidos})
    except (ValueError, TypeError) as e:
        return JSONResponse({"detail": str(e)}, status_code=400)


async def post_limpiar_consultas(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"detail": "JSON inválido."}, status_code=400)
    reunion_id = body.get("reunion_id")
    sector = str(body.get("sector") or "").strip()
    if reunion_id:
        afectados = db.limpiar_consultas_reunion(int(reunion_id))
        return JSONResponse({"afectados": afectados})
    if not sector:
        return JSONResponse({"detail": "reunion_id o sector requerido."}, status_code=400)
    afectados = db.limpiar_consultas_sector(sector)
    return JSONResponse({"afectados": afectados})


async def post_finalizar(request: Request) -> JSONResponse:
    pedido_id = int(request.path_params["id"])
    try:
        body = await request.json()
    except json.JSONDecodeError:
        body = {}
    try:
        pedido = db.finalizar_pedido(pedido_id, body if isinstance(body, dict) else {})
    except ValueError as e:
        return JSONResponse({"detail": str(e)}, status_code=400)
    if not pedido:
        return JSONResponse({"detail": "Pedido no encontrado."}, status_code=404)
    return JSONResponse({"pedido": pedido})


async def post_reactivar(request: Request) -> JSONResponse:
    pedido_id = int(request.path_params["id"])
    pedido = db.reactivar_pedido(pedido_id)
    if not pedido:
        return JSONResponse({"detail": "Pedido no encontrado."}, status_code=404)
    return JSONResponse({"pedido": pedido})


async def get_reuniones(request: Request) -> JSONResponse:
    sector = (request.query_params.get("sector") or "").strip() or None
    owner = (request.query_params.get("owner") or "").strip() or None
    solo_enviadas = request.query_params.get("enviadas", "0") == "1"
    arch = (request.query_params.get("archivadas") or "0").strip().lower()
    if arch in ("1", "true", "yes"):
        archivadas: bool | None = True
    elif arch in ("all", "todas", "*"):
        archivadas = None
    else:
        archivadas = False
    limite = int(request.query_params.get("limite") or "50")
    reuniones = db.listar_reuniones(
        sector=sector,
        owner_email=owner,
        solo_enviadas=solo_enviadas,
        archivadas=archivadas,
        limite=limite,
    )
    return JSONResponse({"reuniones": reuniones})


async def get_reunion(request: Request) -> JSONResponse:
    reunion_id = int(request.path_params["id"])
    reunion = db.obtener_reunion(reunion_id)
    if not reunion:
        return JSONResponse({"detail": "Reunión no encontrada."}, status_code=404)
    return JSONResponse({"reunion": reunion})


async def post_reunion(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"detail": "JSON inválido."}, status_code=400)
    # Si vienen campos de reunión tipada → crear; si solo sector+fecha → obtener/crear legacy
    if body.get("titulo") or body.get("tipo") or body.get("visibilidad") or body.get("owner_email"):
        try:
            reunion = db.crear_reunion(body)
            reunion = _sanitizar_reunion(reunion) if isinstance(reunion, dict) else reunion
            return JSONResponse({"reunion": reunion}, status_code=201)
        except ValueError as e:
            return JSONResponse({"detail": str(e)}, status_code=400)
        except Exception as e:
            traceback.print_exc()
            return JSONResponse({"detail": f"Error interno al crear reunión: {e}"}, status_code=500)
    sector = str(body.get("sector") or "").strip()
    fecha = str(body.get("fecha") or "").strip()
    if not sector or not fecha:
        return JSONResponse({"detail": "sector y fecha requeridos."}, status_code=400)
    try:
        if hasattr(db, "obtener_o_crear_reunion"):
            reunion = db.obtener_o_crear_reunion(sector, fecha)
        else:
            # Fallback: buscar existente o crear una nueva con esos sector/fecha
            reuniones = db.listar_reuniones(sector=sector, limite=50)
            reunion = next((r for r in reuniones if str(r.get("fecha"))[:10] == fecha[:10]), None)
            if not reunion:
                reunion = db.crear_reunion({"sector": sector, "fecha": fecha, "titulo": f"Reunión {fecha}"})
        reunion = _sanitizar_reunion(reunion) if isinstance(reunion, dict) else reunion
        return JSONResponse({"reunion": reunion})
    except ValueError as e:
        return JSONResponse({"detail": str(e)}, status_code=400)
    except Exception as e:
        traceback.print_exc()
        return JSONResponse({"detail": str(e)}, status_code=500)


def _sanitizar_reunion(obj: dict) -> dict:
    """Asegura que date/datetime no rompan JSONResponse (defensa extra si DB devuelve date)."""
    out = {}
    for k, v in obj.items():
        if isinstance(v, (date, datetime)):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out

async def patch_reunion(request: Request) -> JSONResponse:
    reunion_id = int(request.path_params["id"])
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"detail": "JSON inválido."}, status_code=400)
    try:
        reunion = db.actualizar_reunion(reunion_id, body)
    except ValueError as e:
        return JSONResponse({"detail": str(e)}, status_code=400)
    except Exception as e:
        traceback.print_exc()
        return JSONResponse({"detail": f"Error interno al actualizar reunión: {e}"}, status_code=500)
    if not reunion:
        return JSONResponse({"detail": "Reunión no encontrada."}, status_code=404)
    try:
        reunion = _sanitizar_reunion(reunion)
        return JSONResponse({"reunion": reunion})
    except Exception as e:
        traceback.print_exc()
        return JSONResponse({"detail": f"Error serializando reunión: {e}"}, status_code=500)


async def delete_reunion(request: Request) -> JSONResponse:
    reunion_id = int(request.path_params["id"])
    if not db.eliminar_reunion(reunion_id):
        return JSONResponse({"detail": "Reunión no encontrada."}, status_code=404)
    return JSONResponse({"ok": True})


async def post_mover_pedidos(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"detail": "JSON inválido."}, status_code=400)
    try:
        origen = int(body.get("origen_id") or 0)
        destino = int(body.get("destino_id") or 0)
    except (TypeError, ValueError):
        return JSONResponse({"detail": "origen_id y destino_id requeridos."}, status_code=400)
    try:
        n = db.mover_pedidos_reunion(origen, destino)
        return JSONResponse({"movidos": n})
    except ValueError as e:
        return JSONResponse({"detail": str(e)}, status_code=400)


async def reunion_por_id(request: Request) -> JSONResponse:
    """GET / PATCH / DELETE sobre /api/minuta/reuniones/{id}."""
    if request.method == "GET":
        return await get_reunion(request)
    if request.method == "PATCH":
        return await patch_reunion(request)
    if request.method == "DELETE":
        return await delete_reunion(request)
    return JSONResponse({"detail": "Método no permitido."}, status_code=405)


async def get_novedades_reunion(request: Request) -> JSONResponse:
    sector = (request.query_params.get("sector") or "").strip()
    fecha = (request.query_params.get("fecha") or "").strip()
    if not sector or not fecha:
        return JSONResponse({"detail": "sector y fecha requeridos."}, status_code=400)
    novedades = db.novedades_reunion_sector(sector, fecha)
    return JSONResponse({"novedades": novedades})


# --- Export / Import Excel para 5180/minuta ---

# Columnas en orden UI, con clave -> header
_COLUMNAS_MINUTA = [
    ("orden", "Orden"),
    ("fecha", "Fecha solicitud"),
    ("n_pedido", "Nº solicitud"),
    ("oc", "Nº OC"),
    ("fecha_esperada", "Fecha esperada"),
    ("pedido", "Descripción"),
    ("estado", "Estado"),
    ("importancia", "Importancia"),
    ("ultima_novedad", "Última novedad"),
    ("consultas", "Consultas"),
    ("novedad_actual", "Novedad reunión actual"),
    # Novedades nueva (editable) se agrega como última visible
]

_NOVEDADES_COL_HEADER = "Novedades Compras (editable)"
_ID_OCULTO_HEADER = "pedido_id_hidden"


def _generar_excel_minuta(reunion: dict, pedidos: list[dict], visible_cols: list[str] | None = None) -> io.BytesIO:
    """Genera .xlsx legible: auto-width por contenido, wrap, solo Novedades editable, columnas ocultables."""
    if not HAS_OPENPYXL:
        raise RuntimeError("openpyxl no instalado")
    # visible_cols filtra _COLUMNAS_MINUTA keys; None = todas
    if visible_cols is not None:
        cols = [c for c in _COLUMNAS_MINUTA if c[0] in visible_cols]
    else:
        cols = list(_COLUMNAS_MINUTA)
    # Siempre agregar Novedades editable al final
    cols_con_novedades = cols + [("__novedades_compras", _NOVEDADES_COL_HEADER)]
    # Headers
    headers = [h for _, h in cols_con_novedades] + [_ID_OCULTO_HEADER]

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Minuta"

    header_fill = PatternFill("solid", fgColor="1F4E78")
    header_fill_editable = PatternFill("solid", fgColor="059669")
    header_font = Font(color="FFFFFF", bold=True, size=10)
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin_border = Border(
        left=Side(style="thin", color="999999"),
        right=Side(style="thin", color="999999"),
        top=Side(style="thin", color="999999"),
        bottom=Side(style="thin", color="999999"),
    )
    wrap_align = Alignment(vertical="center", wrap_text=True)
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    # Paleta pálida para importancia (no molestar visual)
    fill_critico = PatternFill("solid", fgColor="FECACA")
    fill_urgente = PatternFill("solid", fgColor="FEF3C7")

    # Escribir headers — editable con color distintivo
    for col_idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        is_editable_header = header == _NOVEDADES_COL_HEADER
        cell.fill = header_fill_editable if is_editable_header else header_fill
        cell.font = header_font
        cell.alignment = header_align
        cell.border = thin_border

    # Escribir filas
    for row_idx, p in enumerate(pedidos, start=2):
        for col_idx, (key, _) in enumerate(cols_con_novedades, start=1):
            if key == "__novedades_compras":
                # Columna editable vacía por defecto, pre-cargar si ya tiene novedad_actual? dejar vacía para que Compras complete
                val = ""
            elif key == "ultima_novedad":
                val = p.get("ultima_novedad") or ""
            elif key == "novedad_actual":
                val = p.get("novedad_actual") or ""
            else:
                val = p.get(key) or ""
                # Normalizar estado/importancia a label legible
                if key == "estado":
                    val = str(val).replace("_", " ")
                if key == "importancia":
                    val = str(val)
            cell = ws.cell(row=row_idx, column=col_idx, value=str(val) if val is not None else "")
            cell.border = thin_border
            # Descripción y novedades con wrap y altura
            if key in ("pedido", "ultima_novedad", "consultas", "novedad_actual", "__novedades_compras"):
                cell.alignment = wrap_align
            else:
                cell.alignment = center_align
            # Fuente legible
            cell.font = Font(size=10)
            # Color pálido para importancia (crítico/urgente)
            if key == "importancia":
                vnorm = str(val).strip().lower()
                if vnorm == "critico":
                    cell.fill = fill_critico
                elif vnorm == "urgente":
                    cell.fill = fill_urgente
        # ID oculto para re-import
        id_cell = ws.cell(row=1 + len(pedidos) + 1, column=1)  # dummy to keep col count? actually need per row
        # Correct: pedido_id hidden at last column per row
        hidden_cell = ws.cell(row=row_idx, column=len(headers), value=int(p.get("id", 0)))
        hidden_cell.font = Font(size=8, color="FFFFFF")
    # Corregir: re-escribir hidden id correctamente (arriba pusimos mal)
    # Re-iterar para fijar hidden ids (ya están, solo asegurar)
    for row_idx, p in enumerate(pedidos, start=2):
        ws.cell(row=row_idx, column=len(headers), value=int(p.get("id", 0)))

    max_row = len(pedidos) + 1
    max_col = len(headers)
    # Auto-width por contenido (legible sin agrandar)
    for col_idx, (key, header) in enumerate(cols_con_novedades, start=1):
        # Calcular max len entre header y valores
        max_len = len(str(header))
        for p in pedidos:
            if key == "__novedades_compras":
                v = ""
            elif key == "ultima_novedad":
                v = str(p.get("ultima_novedad") or "")
            elif key == "novedad_actual":
                v = str(p.get("novedad_actual") or "")
            else:
                v = str(p.get(key) or "")
            if len(v) > max_len:
                max_len = len(v)
        # Ajuste: descripción y novedades más anchas pero con wrap, no excesivo
        if key in ("pedido", "ultima_novedad", "consultas", "novedad_actual"):
            width = min(max_len * 0.9 + 4, 40)  # con wrap, no tan ancho
        elif key == "__novedades_compras":
            width = 32  # editable, ancho generoso
        elif key in ("fecha", "fecha_esperada"):
            width = 14
        elif key in ("n_pedido", "oc"):
            width = 16
        else:
            width = min(max_len + 4, 18)
        # No comprimir: mínimo legible
        width = max(width, 10)
        col_letter = openpyxl.utils.get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = width
    # Hidden id column
    hidden_letter = openpyxl.utils.get_column_letter(max_col)
    ws.column_dimensions[hidden_letter].width = 8
    ws.column_dimensions[hidden_letter].hidden = True
    # Header Novedades editable column width ya seteada

    # Ocultar columnas no visibles (si visible_cols filtra)
    if visible_cols is not None:
        # Mapear key -> col_idx
        visible_set = set(visible_cols) | {"__novedades_compras", _ID_OCULTO_HEADER}
        # cols_con_novedades + hidden id
        all_keys = [k for k, _ in cols_con_novedades] + [_ID_OCULTO_HEADER]
        for col_idx, (key, _) in enumerate([(k, h) for k, h in cols_con_novedades], start=1):
            if key not in visible_set:
                letter = openpyxl.utils.get_column_letter(col_idx)
                ws.column_dimensions[letter].hidden = True

    # AutoFilter y freeze
    ws.auto_filter.ref = f"A1:{openpyxl.utils.get_column_letter(max_col)}{max_row}"
    ws.freeze_panes = "A2"
    # Ajustar altura de filas para wrap (aprox)
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    for row_idx in range(2, max_row + 1):
        ws.row_dimensions[row_idx].height = 28

    # Protección: solo columna Novedades editable
    nov_col_idx = len(cols) + 1  # 1-based index de Novedades
    for col_idx in range(1, max_col + 1):
        for r in range(1, max_row + 1):
            cell = ws.cell(row=r, column=col_idx)
            # Header también bloqueado, datos bloqueados salvo nov_col
            is_novedades = col_idx == nov_col_idx and r > 1
            cell.protection = Protection(locked=not is_novedades)
    ws.protection.sheet = True
    ws.protection.password = ""

    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return out


async def exportar_excel_reunion(request: Request) -> StreamingResponse:
    if not HAS_OPENPYXL:
        return JSONResponse({"detail": "openpyxl no instalado en el servidor."}, status_code=500)
    reunion_id = request.path_params.get("id")
    try:
        reunion_id = int(reunion_id)
    except (TypeError, ValueError):
        return JSONResponse({"detail": "reunion_id inválido."}, status_code=400)
    reunion = db.obtener_reunion(reunion_id)
    if not reunion:
        return JSONResponse({"detail": "Reunión no encontrada."}, status_code=404)
    # Filtro ids opcional: ?ids=1,2,3 o ?pedido_ids=...
    ids_param = request.query_params.get("ids") or request.query_params.get("pedido_ids") or ""
    ids_filtro: set[int] | None = None
    if ids_param:
        try:
            ids_filtro = {int(x.strip()) for x in ids_param.split(",") if x.strip()}
        except ValueError:
            ids_filtro = None
    cols_param = request.query_params.get("cols") or ""
    visible_cols: list[str] | None = None
    if cols_param:
        visible_cols = [c.strip() for c in cols_param.split(",") if c.strip()]

    pedidos = db.listar_pedidos_reunion(reunion_id, solo_activos=False)
    # Respetar orden manual (ya viene orden ASC) — no reordenar por fecha salvo que se pida
    # Filtrar por ids si se pasó
    if ids_filtro is not None:
        pedidos = [p for p in pedidos if int(p.get("id", 0)) in ids_filtro]
    # Para reunión parcial: solo activos por defecto? Pero respetamos lo que elige el usuario vía ids
    try:
        out = _generar_excel_minuta(reunion, pedidos, visible_cols)
    except Exception as e:
        return JSONResponse({"detail": f"Error generando Excel: {e}"}, status_code=500)
    filename = f"Minuta_{reunion.get('sector','')}_{reunion.get('fecha','')}_R{reunion_id}.xlsx"
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", filename)
    return StreamingResponse(
        out,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{safe}"'},
    )


async def importar_novedades_reunion(request: Request) -> JSONResponse:
    if not HAS_OPENPYXL:
        return JSONResponse({"detail": "openpyxl no instalado."}, status_code=500)
    reunion_id = request.path_params.get("id")
    try:
        reunion_id = int(reunion_id)
    except (TypeError, ValueError):
        return JSONResponse({"detail": "reunion_id inválido."}, status_code=400)
    reunion = db.obtener_reunion(reunion_id)
    if not reunion:
        return JSONResponse({"detail": "Reunión no encontrada."}, status_code=404)
    try:
        form = await request.form()
    except Exception:
        return JSONResponse({"detail": "Error leyendo formulario."}, status_code=400)
    file = form.get("archivo") or form.get("file")
    if not file or not hasattr(file, "read"):
        return JSONResponse({"detail": "Archivo 'archivo' requerido."}, status_code=400)
    try:
        raw = await file.read()
        if not raw:
            return JSONResponse({"detail": "Archivo vacío."}, status_code=400)
        wb = openpyxl.load_workbook(io.BytesIO(raw), data_only=True, read_only=True)
    except Exception as e:
        return JSONResponse({"detail": f"Error leyendo Excel: {e}"}, status_code=400)

    # Buscar hoja Minuta
    ws = None
    for name in wb.sheetnames:
        if name.lower() == "minuta":
            ws = wb[name]
            break
    if ws is None:
        # fallback primera hoja
        ws = wb[wb.sheetnames[0]]
        # verificar header
        try:
            header = [str(c.value or "").strip().lower() for c in next(ws.iter_rows(min_row=1, max_row=1))]
            if "novedades compras (editable)" not in header and "pedido_id_hidden" not in header:
                wb.close()
                return JSONResponse({"detail": "No se encontró la hoja 'Minuta' con formato esperado."}, status_code=400)
        except StopIteration:
            pass

    # Mapear headers
    header_row = None
    for row in ws.iter_rows(min_row=1, max_row=1, values_only=True):
        header_row = row
        break
    if not header_row:
        wb.close()
        return JSONResponse({"detail": "Hoja vacía."}, status_code=400)
    header_map: dict[str, int] = {}
    for idx, h in enumerate(header_row):
        if h:
            header_map[str(h).strip().lower()] = idx
    idx_novedades = header_map.get("novedades compras (editable)", header_map.get("novedades", None))
    idx_id_hidden = header_map.get("pedido_id_hidden", None)
    # fallback: última columna es id hidden, penúltima es novedades
    if idx_novedades is None:
        idx_novedades = len(header_row) - 2
    if idx_id_hidden is None:
        idx_id_hidden = len(header_row) - 1

    # Procesar filas
    resumen = {"procesadas": 0, "omitidas_duplicadas": 0, "pendientes_consulta": 0, "no_reconocidas": 0, "total_leidas": 0}
    fecha_reunion = str(reunion.get("fecha") or "")
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or all(v is None or str(v).strip() == "" for v in row):
            continue
        resumen["total_leidas"] += 1
        try:
            pedido_id_raw = row[idx_id_hidden] if idx_id_hidden < len(row) else None
            pedido_id = int(str(pedido_id_raw).strip()) if pedido_id_raw is not None and str(pedido_id_raw).strip() != "" else 0
        except (ValueError, TypeError):
            pedido_id = 0
        novedades_texto = str(row[idx_novedades] or "").strip() if idx_novedades < len(row) else ""
        if pedido_id == 0:
            resumen["no_reconocidas"] += 1
            continue
        # Verificar pedido existe y pertenece a la reunion
        pedido = db.obtener_pedido(pedido_id)
        if not pedido or int(pedido.get("reunion_id", 0)) != reunion_id:
            resumen["no_reconocidas"] += 1
            continue
        if not novedades_texto:
            resumen["omitidas_duplicadas"] += 1
            continue
        # Obtener existente real para esa fecha (debe revisar todas las novedades de esa fecha, no solo la última)
        existente = ""
        existente_norm_match = False
        try:
            with db._conectar() as _conn:
                _rows = _conn.execute(
                    "SELECT texto FROM novedades WHERE pedido_id = ? AND fecha_reunion = ?",
                    (pedido_id, fecha_reunion),
                ).fetchall()
                for _r in _rows:
                    txt = (_r["texto"] or "").strip()
                    if txt:
                        # Guardar el primero como existente para mensaje de consulta
                        if not existente:
                            existente = txt
                        if re.sub(r"\s+", " ", txt.strip().lower()) == re.sub(r"\s+", " ", novedades_texto.strip().lower()):
                            existente_norm_match = True
                            existente = txt
                            break
        except Exception:
            existente = ""

        def norm(s: str) -> str:
            return re.sub(r"\s+", " ", s.strip().lower())
        if existente and norm(existente) == norm(novedades_texto):
            resumen["omitidas_duplicadas"] += 1
            continue
        if existente and existente.strip() != "" and norm(existente) != norm(novedades_texto):
            # Conflicto: ya había texto distinto para esa fecha -> crear consulta pendiente? Por ahora lo registramos como pendiente y no pisamos
            # Guardamos en consultas (campo consultas) + bloqueamos? Para 5180, usamos tabla novedades con entrada de consulta? Simplificado: insertamos en novedades pero marcamos como pendiente en resumen
            # Decisión actual: NO pisar, crear registro en novedades con prefijo [Consulta] y contar como pendiente
            # Para respetar "sin borrar ni pisar, abrir consulta caso por caso", lo contamos como pendiente
            resumen["pendientes_consulta"] += 1
            # Guardar como novedad con marca para revisión manual
            try:
                db.agregar_novedad(pedido_id, {"fecha_reunion": fecha_reunion, "texto": f"[CONSULTA] {novedades_texto} (existía: {existente})"})
            except Exception:
                pass
            continue
        # Caso normal: upsert
        try:
            db.upsert_novedad(pedido_id, {"fecha_reunion": fecha_reunion, "texto": novedades_texto})
            resumen["procesadas"] += 1
        except Exception as e:
            resumen["no_reconocidas"] += 1

    wb.close()
    # Compat: total_importadas = procesadas + omitidas + pendientes + no_reconocidas? Mantener alias
    resumen["total_importadas"] = resumen["total_leidas"]
    return JSONResponse(resumen)


_origins = os.environ.get("MINUTA_CORS_ORIGINS", "*").strip()
_allow = ["*"] if _origins == "*" else [o.strip() for o in _origins.split(",") if o.strip()]

app = Starlette(
    routes=[
        Route("/health", health, methods=["GET"]),
        Route("/api/minuta/sectores", get_sectores, methods=["GET"]),
        Route("/api/minuta/pedidos", get_pedidos, methods=["GET"]),
        Route("/api/minuta/pedidos", post_pedido, methods=["POST"]),
        Route("/api/minuta/pedidos/reordenar", post_reordenar, methods=["POST"]),
        Route("/api/minuta/pedidos/limpiar-consultas", post_limpiar_consultas, methods=["POST"]),
        Route("/api/minuta/pedidos/{id:int}", get_pedido, methods=["GET"]),
        Route("/api/minuta/pedidos/{id:int}", patch_pedido, methods=["PATCH"]),
        Route("/api/minuta/pedidos/{id:int}", delete_pedido, methods=["DELETE"]),
        Route("/api/minuta/pedidos/{id:int}/novedades", post_novedad, methods=["POST"]),
        Route("/api/minuta/pedidos/{id:int}/novedades", put_novedad, methods=["PUT"]),
        Route("/api/minuta/pedidos/{id:int}/finalizar", post_finalizar, methods=["POST"]),
        Route("/api/minuta/pedidos/{id:int}/reactivar", post_reactivar, methods=["POST"]),
        Route("/api/minuta/reuniones", get_reuniones, methods=["GET"]),
        Route("/api/minuta/reuniones", post_reunion, methods=["POST"]),
        Route("/api/minuta/reuniones/mover-pedidos", post_mover_pedidos, methods=["POST"]),
        Route(
            "/api/minuta/reuniones/{id:int}",
            reunion_por_id,
            methods=["GET", "PATCH", "DELETE"],
        ),
        Route("/api/minuta/novedades-reunion", get_novedades_reunion, methods=["GET"]),
        Route("/api/minuta/reuniones/{id:int}/exportar-excel", exportar_excel_reunion, methods=["GET"]),
        Route("/api/minuta/reuniones/{id:int}/importar-novedades", importar_novedades_reunion, methods=["POST"]),
    ],
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow,
    allow_methods=["*"],
    allow_headers=["*"],
)
