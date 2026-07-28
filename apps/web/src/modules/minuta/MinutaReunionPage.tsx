import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { enviarCorreo, fetchContactos, type Contacto } from "../../api/emailClient";
import {
  fetchNovedadesReunion,
  fetchReuniones,
  moverPedidosReunion,
  type Reunion,
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
  const [historicoOrigen, setHistoricoOrigen] = useState<Reunion | null>(null);
  const [recuperando, setRecuperando] = useState(false);

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
    pedidosFinalizados.length === 0 &&
    !String(reunion.titulo || "").startsWith("Histórico");

  useEffect(() => {
    if (!reunionVacia || !reunion?.sector) {
      setHistoricoOrigen(null);
      return;
    }
    let alive = true;
    fetchReuniones({ sector: reunion.sector, limite: 40 })
      .then((list) => {
        if (!alive) return;
        const hist = list.find(
          (r) =>
            r.id !== reunionId &&
            String(r.titulo || "").startsWith("Histórico") &&
            Number(r.archivada ?? 0) !== 1,
        );
        setHistoricoOrigen(hist ?? null);
      })
      .catch(() => {
        if (alive) setHistoricoOrigen(null);
      });
    return () => {
      alive = false;
    };
  }, [reunionVacia, reunion?.sector, reunionId]);

  const recuperarDesdeHistorico = useCallback(async () => {
    if (!historicoOrigen) return;
    if (
      !window.confirm(
        `¿Traer todos los pedidos de «${historicoOrigen.titulo}» a esta reunión?\n` +
          "Las novedades que escribiste en esta PC se mantienen si son de esos mismos ítems.",
      )
    ) {
      return;
    }
    setRecuperando(true);
    setMensaje(null);
    try {
      const n = await moverPedidosReunion(historicoOrigen.id, reunionId);
      setMensaje({
        tipo: "ok",
        texto: n > 0 ? `Se recuperaron ${n} pedidos del Histórico.` : "El Histórico no tenía pedidos.",
      });
      setHistoricoOrigen(null);
      await recargar();
    } catch (e: unknown) {
      setMensaje({
        tipo: "err",
        texto: e instanceof Error ? e.message : "No se pudieron recuperar los pedidos.",
      });
    } finally {
      setRecuperando(false);
    }
  }, [historicoOrigen, reunionId, recargar]);

  const seleccionarTodos = useCallback(() => {
    setDestinatarios(contactos.map((c) => c.email));
  }, [contactos, setDestinatarios]);

  const limpiarDestinatarios = useCallback(() => {
    setDestinatarios([]);
  }, [setDestinatarios]);

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
        texto:
          "No hay ítems en esta reunión en el servidor. Si los ves solo en esta PC, recargá o verificá que no estés en una reunión vacía (los ítems pueden estar en Histórico).",
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
        /* el mail igual lleva borradores locales */
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
      const extra =
        avisos.length > 0
          ? ` Avisos: ${avisos.slice(0, 3).join(" ")}${avisos.length > 3 ? "…" : ""}`
          : "";
      setMensaje({ tipo: "ok", texto: `Minuta enviada y reunión registrada.${extra}` });
      await recargar();
    } catch (e: unknown) {
      setMensaje({
        tipo: "err",
        texto: e instanceof Error ? e.message : "Error al enviar el correo.",
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
    recargar,
    setError,
  ]);

  const abandonar = useCallback(() => {
    if (
      window.confirm(
        "¿Abandonar borrador local? Los pedidos en servidor permanecen; se pierde el cache de esta sesión.",
      )
    ) {
      limpiarSesionLocal(scope, reunionId);
      resetBorradoresTrasEnvio();
      setMensaje(null);
    }
  }, [scope, reunionId, resetBorradoresTrasEnvio]);

  if (!Number.isFinite(reunionId) || reunionId <= 0) {
    return (
      <div className="minuta-page">
        <p className="error">Reunión inválida.</p>
        <Link to="/minuta">Volver al listado</Link>
      </div>
    );
  }

  return (
    <div className="minuta-page">
      <header className="page-header">
        <p className="minuta-back">
          <Link to="/minuta">← Reuniones</Link>
        </p>
        <h1>{reunion?.titulo || "Minuta de reunión"}</h1>
        <p className="sub">
          Los cambios se guardan en cache hasta enviar el mail. Las consultas se persisten al
          escribir.
        </p>
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
          <p className="error">
            Esta reunión no tiene ítems en el servidor. Si los borraste o migramos una reunión, los
            pedidos suelen estar en el Histórico del sector.
          </p>
          {historicoOrigen ? (
            <p className="minuta-hint">
              <button
                type="button"
                className="btn-primary"
                disabled={recuperando}
                onClick={() => void recuperarDesdeHistorico()}
              >
                {recuperando
                  ? "Recuperando…"
                  : `Traer pedidos de «${historicoOrigen.titulo}»`}
              </button>{" "}
              o{" "}
              <Link to={`/minuta/${historicoOrigen.id}`}>abrir el Histórico</Link> y enviar desde
              ahí.
            </p>
          ) : (
            <p className="minuta-hint">
              En el listado abrí <strong>Históricos</strong> y entrá al del sector.
            </p>
          )}
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
              onChange={(e) => setSesionParcial({ sectoresComprometidos: e.target.value })}
              placeholder="Ej: Mantenimiento - Compras"
            />
          </label>
          <label>
            Fecha de reunión
            <input
              type="date"
              value={sesion.fecha}
              onChange={(e) => setSesionParcial({ fecha: e.target.value })}
            />
          </label>
        </div>
      </section>

      {cargando ? (
        <p className="minuta-hint">Cargando pedidos…</p>
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
          />

          <details className="minuta-finalizados">
            <summary>
              Finalizados ({pedidosFinalizados.length})
            </summary>
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

      <EnviarMinutaBar enviando={enviando} onEnviar={enviar} onAbandonar={abandonar} />
    </div>
  );
}
