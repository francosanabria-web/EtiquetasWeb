import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { enviarCorreo, fetchContactos, type Contacto } from "../../api/emailClient";
import {
  actualizarReunion,
  descargarBlob,
  exportarMinutaExcel,
  fetchNovedadesReunion,
  importarNovedadesMinuta,
} from "../../api/minutaClient";
import { useAuth } from "../../auth/AuthContext";
import { buildMinutaMail } from "./buildMinutaMail";
import EnviarMinutaBar from "./EnviarMinutaBar";
import NotasLibres from "./NotasLibres";
import PanelReunionesAnteriores from "./PanelReunionesAnteriores";
import SelectorDestinatarios from "./SelectorDestinatarios";
import TablaPedidosReunion from "./TablaPedidosReunion";
import { limpiarSesionLocal } from "./types";
import { useMinutaSession } from "./useMinutaSession";
import VistaIndicadores from "./VistaIndicadores";

export default function MinutaReunionPage() {
  const { reunionId: idParam } = useParams();
  const reunionId = Number(idParam);
  const { usuario } = useAuth();
  const scope = (usuario?.email ?? "anon").toLowerCase();

  const {
    reunion,
    sesion,
    pedidosActivos,
    pedidosFinalizados,
    reunionesEnviadas,
    cargando,
    error,
    setError,
    expandidoId,
    expandirPedido,
    setNotasGenerales,
    setDestinatarios,
    toggleDestinatario,
    setBorradorNovedad,
    setVistoPedido,
    guardarCampoPedido,
    reordenarLocal,
    addPedido,
    ejecutarFinalizar,
    ejecutarReactivar,
    ejecutarEliminar,
    persistirAlEnviar,
    setSesionParcial,
    resetBorradoresTrasEnvio,
    recargar,
  } = useMinutaSession(reunionId);

  const [contactos, setContactos] = useState<Contacto[]>([]);
  const [cargandoContactos, setCargandoContactos] = useState(true);
  const [errorContactos, setErrorContactos] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [mensaje, setMensaje] = useState<{ tipo: "ok" | "err"; texto: string } | null>(null);
  const [verIndicadores, setVerIndicadores] = useState(false);
  const [exportando, setExportando] = useState(false);
  const [importandoNovedades, setImportandoNovedades] = useState(false);
  // Columnas visibles para export (por defecto todas). Guardado local para no irse de ancho.
  const COLUMNAS_OPCIONES: { key: string; label: string }[] = [
    { key: "fecha", label: "Fecha solicitud" },
    { key: "n_pedido", label: "Nº solicitud" },
    { key: "oc", label: "Nº OC" },
    { key: "fecha_esperada", label: "Fecha esperada" },
    { key: "pedido", label: "Descripción" },
    { key: "estado", label: "Estado" },
    { key: "importancia", label: "Importancia" },
    { key: "ultima_novedad", label: "Última novedad" },
    { key: "consultas", label: "Consultas" },
    { key: "novedad_actual", label: "Novedad actual" },
  ];
  const [colsVisibles, setColsVisibles] = useState<string[]>(() => {
    try {
      const raw = localStorage.getItem(`minuta-cols-${reunionId}`);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed) && parsed.length) return parsed as string[];
      }
    } catch {}
    return COLUMNAS_OPCIONES.map((c) => c.key);
  });
  useEffect(() => {
    try {
      localStorage.setItem(`minuta-cols-${reunionId}`, JSON.stringify(colsVisibles));
    } catch {}
  }, [colsVisibles, reunionId]);
  const [mostrarColumnas, setMostrarColumnas] = useState(false);
  // Selección para export parcial: ids de pedidos activos a exportar (vacío = todos)
  const [idsExport, setIdsExport] = useState<Set<number>>(new Set());
  const toggleExportId = useCallback((id: number, checked: boolean) => {
    setIdsExport((prev) => {
      const next = new Set(prev);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  }, []);
  const toggleSeleccionarTodoExport = useCallback(() => {
    if (idsExport.size === pedidosActivos.length) {
      setIdsExport(new Set());
    } else {
      setIdsExport(new Set(pedidosActivos.map((p) => p.id)));
    }
  }, [idsExport.size, pedidosActivos]);

  useEffect(() => {
    let alive = true;
    fetchContactos()
      .then((list) => {
        if (alive) setContactos(list);
      })
      .catch((e: unknown) => {
        if (alive) {
          setErrorContactos(e instanceof Error ? e.message : "No se pudieron cargar los contactos.");
        }
      })
      .finally(() => {
        if (alive) setCargandoContactos(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  const reunionVacia =
    !cargando &&
    !!reunion &&
    pedidosActivos.length === 0 &&
    pedidosFinalizados.length === 0;

  const seleccionarTodos = useCallback(() => {
    setDestinatarios(contactos.map((c) => c.email));
  }, [contactos, setDestinatarios]);

  const limpiarDestinatarios = useCallback(() => {
    setDestinatarios([]);
  }, [setDestinatarios]);

  const persistirMetaReunion = useCallback(
    (patch: { fecha?: string; sectores_comprometidos?: string }) => {
      void actualizarReunion(reunionId, patch)
        .then(() => recargar({ silencioso: true }))
        .catch(() => {});
    },
    [reunionId, recargar],
  );

  const enviar = useCallback(async () => {
    setMensaje(null);
    setError(null);
    if (!reunion) return;
    if (sesion.destinatarios.length === 0) {
      setMensaje({ tipo: "err", texto: "Seleccioná al menos un destinatario." });
      return;
    }
    if (pedidosActivos.length === 0 && pedidosFinalizados.length === 0) {
      setMensaje({
        tipo: "err",
        texto: "No hay ítems en esta reunión. Agregá pedidos antes de enviar.",
      });
      return;
    }
    setEnviando(true);
    try {
      const avisos = await persistirAlEnviar();
      let novedades: { pedido_id: number; texto: string }[] = [];
      try {
        novedades = await fetchNovedadesReunion(reunion.sector, sesion.fecha);
      } catch {
        /* el mail igual lleva novedad_actual de los pedidos */
      }
      const mail = buildMinutaMail(sesion, [...pedidosActivos, ...pedidosFinalizados], novedades, {
        titulo: reunion.titulo,
        sector: reunion.sector,
      });
      await enviarCorreo({
        destinatarios: sesion.destinatarios,
        asunto: mail.asunto,
        cuerpo_html: mail.cuerpo_html,
        cuerpo_texto: mail.cuerpo_texto,
      });
      resetBorradoresTrasEnvio();
      limpiarSesionLocal(scope, reunionId);
      const extra = avisos.length ? ` Avisos: ${avisos.join(" ")}` : "";
      setMensaje({ tipo: "ok", texto: `Minuta enviada correctamente.${extra}` });
      await recargar();
    } catch (e: unknown) {
      setMensaje({
        tipo: "err",
        texto: e instanceof Error ? e.message : "No se pudo enviar la minuta.",
      });
    } finally {
      setEnviando(false);
    }
  }, [
    reunion,
    sesion,
    pedidosActivos,
    pedidosFinalizados,
    persistirAlEnviar,
    resetBorradoresTrasEnvio,
    scope,
    reunionId,
    recargar,
    setError,
  ]);

  const abandonar = useCallback(() => {
    if (
      !window.confirm(
        "¿Salir sin enviar? Los cambios de ítems y novedades ya están en el servidor.",
      )
    ) {
      return;
    }
    window.location.href = "/minuta";
  }, []);

  const handleExportarExcel = useCallback(async () => {
    if (!reunion) return;
    setMensaje(null);
    setExportando(true);
    try {
      const ids = idsExport.size > 0 ? Array.from(idsExport) : undefined;
      // colsVisibles ya incluye todas por defecto; si quiere ocultar, des tilda
      const blob = await exportarMinutaExcel(reunion.id, { ids, cols: colsVisibles });
      const filename = `Minuta_${reunion.sector}_${sesion.fecha}_R${reunion.id}.xlsx`;
      descargarBlob(blob, filename);
      setMensaje({ tipo: "ok", texto: `Excel exportado: ${pedidosActivos.length} pedidos (orden preserved, solo Novedades editable, ocultables aplicadas).` });
    } catch (e: unknown) {
      setMensaje({ tipo: "err", texto: e instanceof Error ? e.message : "No se pudo exportar." });
    } finally {
      setExportando(false);
    }
  }, [reunion, idsExport, colsVisibles, pedidosActivos.length, sesion.fecha]);

  const handleImportarNovedades = useCallback(async (file: File | null) => {
    if (!file || !reunion) return;
    setMensaje(null);
    setImportandoNovedades(true);
    try {
      const res = await importarNovedadesMinuta(reunion.id, file);
      const msg = `Novedades: ${res.procesadas} nuevas, ${res.omitidas_duplicadas} duplicadas, ${res.pendientes_consulta} en consulta, ${res.no_reconocidas} no reconocidas.`;
      setMensaje({ tipo: "ok", texto: msg });
      await recargar();
    } catch (e: unknown) {
      setMensaje({ tipo: "err", texto: e instanceof Error ? e.message : "No se pudo importar novedades." });
    } finally {
      setImportandoNovedades(false);
    }
  }, [reunion, recargar]);

  if (!Number.isFinite(reunionId) || reunionId <= 0) {
    return (
      <div className="page minuta-page">
        <p className="error">Reunión inválida.</p>
        <Link to="/minuta">Volver al listado</Link>
      </div>
    );
  }

  return (
    <div className="page minuta-page">
      <header className="page-header">
        <p className="minuta-back">
          <Link to="/minuta">← Reuniones</Link>
        </p>
        <h1>{reunion?.titulo || "Minuta de reunión"}</h1>
        <p className="sub">
          Los cambios se guardan en el servidor al editar (visibles en todas las PC). El mail usa
          esas novedades al enviar.
        </p>
        <label className="minuta-ind-switch">
          <input
            type="checkbox"
            checked={verIndicadores}
            onChange={(e) => setVerIndicadores(e.target.checked)}
          />
          <span className="minuta-ind-switch-label">Indicadores</span>
        </label>
      </header>

      {mensaje && (
        <p className={mensaje.tipo === "ok" ? "minuta-ok" : "error"} role="status">
          {mensaje.texto}
        </p>
      )}
      {!mensaje && error && (
        <p className="error" role="status">
          {error}
        </p>
      )}

      {reunionVacia && (
        <div className="minuta-section" role="status">
          <p className="minuta-hint">
            Esta reunión todavía no tiene ítems. Usá <strong>+ Pedido</strong> para cargar el
            primero.
          </p>
        </div>
      )}

      <section className="minuta-section minuta-encabezado">
        <h2>Reunión</h2>
        <div className="minuta-grid-2">
          <label>
            Sectores comprometidos
            <input
              type="text"
              value={sesion.sectoresComprometidos}
              onChange={(e) => {
                const v = e.target.value;
                setSesionParcial({ sectoresComprometidos: v });
                persistirMetaReunion({ sectores_comprometidos: v });
              }}
              placeholder="Ej: Mantenimiento - Compras"
            />
          </label>
          <label>
            Fecha de reunión
            <input
              type="date"
              value={sesion.fecha}
              onChange={(e) => {
                const v = e.target.value;
                setSesionParcial({ fecha: v });
                persistirMetaReunion({ fecha: v });
              }}
            />
          </label>
        </div>
      </section>

      {/* Export / Import + columnas ocultables + selección parcial */}
      <section className="minuta-section">
        <h2>Exportar para Compras</h2>
        <p className="sub">
          Exporta un Excel legible (auto-ancho por contenido, wrap, solo columna Novedades editable, orden preservado). Podés ocultar columnas para que no quede ancho/comprimido.
        </p>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginTop: 8 }}>
          <button type="button" className="btn-primary" disabled={exportando || cargando} onClick={() => void handleExportarExcel()}>
            {exportando ? "Exportando…" : "Exportar Excel"}
          </button>
          <label className="btn-ghost btn-sm" style={{ cursor: "pointer" }}>
            {importandoNovedades ? "Importando…" : "Importar Novedades"}
            <input
              type="file"
              accept=".xlsx,.xlsm"
              hidden
              disabled={importandoNovedades}
              onChange={(e) => {
                const f = e.target.files?.[0] ?? null;
                if (f) void handleImportarNovedades(f);
                e.target.value = "";
              }}
            />
          </label>
          <button type="button" className="btn-ghost btn-sm" onClick={() => setMostrarColumnas((v) => !v)}>
            {mostrarColumnas ? "Ocultar columnas ▲" : "Elegir columnas ▼"}
          </button>
          {pedidosActivos.length > 0 && (
            <button type="button" className="btn-ghost btn-sm" onClick={toggleSeleccionarTodoExport}>
              {idsExport.size === pedidosActivos.length ? "Deseleccionar todo" : "Seleccionar todo para export"}
            </button>
          )}
        </div>
        {mostrarColumnas && (
          <div style={{ marginTop: 12, display: "flex", flexWrap: "wrap", gap: 8 }}>
            {COLUMNAS_OPCIONES.map((c) => (
              <label key={c.key} style={{ display: "flex", gap: 4, alignItems: "center", fontSize: 13 }}>
                <input
                  type="checkbox"
                  checked={colsVisibles.includes(c.key)}
                  onChange={(e) => {
                    const checked = e.target.checked;
                    setColsVisibles((prev) => {
                      if (checked) return [...prev, c.key];
                      return prev.filter((k) => k !== c.key);
                    });
                  }}
                />
                {c.label}
              </label>
            ))}
            <button
              type="button"
              className="btn-ghost btn-sm"
              onClick={() => setColsVisibles(COLUMNAS_OPCIONES.map((c) => c.key))}
            >
              Todas
            </button>
            <button
              type="button"
              className="btn-ghost btn-sm"
              onClick={() => setColsVisibles(["n_pedido", "pedido", "estado", "ultima_novedad"])}
            >
              Solo clave
            </button>
          </div>
        )}
        {idsExport.size > 0 && <p className="minuta-hint" style={{ marginTop: 8 }}>{idsExport.size} pedidos seleccionados para exportar (vacío = todos).</p>}
      </section>

      {cargando ? (
        <p className="minuta-hint">Cargando pedidos…</p>
      ) : verIndicadores ? (
        <VistaIndicadores pedidos={pedidosActivos} />
      ) : (
        <>
          <TablaPedidosReunion
            pedidos={pedidosActivos}
            fechaReunion={sesion.fecha}
            borradores={sesion.borradoresNovedad}
            vistos={sesion.vistosEnReunion}
            expandidoId={expandidoId}
            modo="activos"
            onExpand={expandirPedido}
            onCampo={guardarCampoPedido}
            onBorrador={setBorradorNovedad}
            onVisto={setVistoPedido}
            onFinalizar={ejecutarFinalizar}
            onEliminar={ejecutarEliminar}
            onReordenar={reordenarLocal}
            onAdd={addPedido}
            idsExport={idsExport}
            onToggleExport={toggleExportId}
            columnasVisibles={colsVisibles}
          />

          <details className="minuta-finalizados">
            <summary>Finalizados ({pedidosFinalizados.length})</summary>
            <TablaPedidosReunion
              pedidos={pedidosFinalizados}
              fechaReunion={sesion.fecha}
              borradores={sesion.borradoresNovedad}
              expandidoId={expandidoId}
              modo="finalizados"
              onExpand={expandirPedido}
              onCampo={guardarCampoPedido}
              onBorrador={setBorradorNovedad}
              onReactivar={ejecutarReactivar}
              onEliminar={ejecutarEliminar}
            />
          </details>
        </>
      )}

      <NotasLibres notas={sesion.notasGenerales} onChange={setNotasGenerales} />

      <PanelReunionesAnteriores
        reuniones={reunionesEnviadas}
        sector={reunion?.sector ?? ""}
        fechaActual={sesion.fecha}
      />

      <SelectorDestinatarios
        contactos={contactos}
        seleccionados={sesion.destinatarios}
        cargando={cargandoContactos}
        error={errorContactos}
        onToggle={toggleDestinatario}
        onSeleccionarTodos={seleccionarTodos}
        onLimpiar={limpiarDestinatarios}
      />

      <EnviarMinutaBar
        enviando={enviando}
        onEnviar={() => void enviar()}
        onAbandonar={abandonar}
      />
    </div>
  );
}
