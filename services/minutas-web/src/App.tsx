import { useCallback, useState } from "react";
import {
  agregarActualizacion,
  agregarEntrega,
  actualizarSesion,
  cerrarSolicitud,
  crearSolicitud,
  crearTema,
  getSesion,
  toggleTemaResuelto,
  API_URL,
} from "./api/client";
import { ApiError } from "./api/client";
import EnviarMinutaModal from "./components/EnviarMinutaModal";
import HistorialPanel from "./components/HistorialPanel";
import SolicitudCard from "./components/SolicitudCard";
import SolicitudFormPanel from "./components/SolicitudFormPanel";
import TemasPanel from "./components/TemasPanel";
import { useMinutaSession } from "./hooks/useMinutaSession";
import type { SesionDetalle, SolicitudForm, TemaForm } from "./types/minuta";

const SHELL_URL = import.meta.env.VITE_SHELL_URL;

export default function App() {
  const {
    sesion,
    setSesion,
    historial,
    cargando,
    error,
    setError,
    apiOk,
    refrescar,
    iniciar,
  } = useMinutaSession();

  const [responsable, setResponsable] = useState(
    () => localStorage.getItem("minutas-responsable") ?? ""
  );
  const [notas, setNotas] = useState("");
  const [modalEmail, setModalEmail] = useState(false);
  const [vistaHistorial, setVistaHistorial] = useState<SesionDetalle | null>(null);
  const [iniciando, setIniciando] = useState(false);

  const activa = sesion?.estado === "abierta" ? sesion : null;
  const mostrar = vistaHistorial ?? activa;
  const readOnly = !activa || !!vistaHistorial;

  const guardarNotas = useCallback(async () => {
    if (!activa) return;
    try {
      await actualizarSesion(activa.id, { notas_generales: notas });
      localStorage.setItem("minutas-responsable", responsable);
      await refrescar();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Error al guardar notas.");
    }
  }, [activa, notas, responsable, refrescar, setError]);

  async function handleIniciar() {
    setIniciando(true);
    localStorage.setItem("minutas-responsable", responsable);
    await iniciar(responsable);
    setVistaHistorial(null);
    setIniciando(false);
  }

  async function reloadSesion(id: number) {
    const s = await getSesion(id);
    if (id === activa?.id) setSesion(s);
    else setVistaHistorial(s);
  }

  async function onNuevaSolicitud(form: SolicitudForm) {
    if (!activa) return;
    await crearSolicitud(activa.id, {
      numero_referencia: form.numero_referencia.trim(),
      solicitante: form.solicitante.trim(),
      urgencia: form.urgencia,
      cantidad_items: parseInt(form.cantidad_items, 10),
      descripcion: form.descripcion.trim() || undefined,
    });
    await reloadSesion(activa.id);
  }

  if (cargando && !sesion && !vistaHistorial) {
    return (
      <div className="app-shell">
        <p className="loading-center">Cargando minutas…</p>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-icon">📝</span>
          <div>
            <h1>Minutas — Reunión semanal</h1>
            <p className="brand-sub">Seguimiento de solicitudes a Compras · SistemasPañol</p>
          </div>
        </div>
        <div className="top-meta">
          {!apiOk && <span className="badge warn">API desconectada</span>}
          <span className="api-pill">API: {API_URL}</span>
        </div>
        {SHELL_URL && (
          <a className="btn-ghost btn-sm" href={SHELL_URL}>
            ← Portal
          </a>
        )}
      </header>

      <main className="layout">
        {error && (
          <div className="banner error">
            {error}
            <button type="button" onClick={() => setError(null)} aria-label="Cerrar">
              ×
            </button>
          </div>
        )}

        {!activa && !vistaHistorial && (
          <section className="panel inicio">
            <h2>Iniciar reunión de la semana</h2>
            <p className="sub">
              Se arrastran automáticamente las solicitudes abiertas y los temas pendientes de
              reuniones anteriores.
            </p>
            <label>
              Responsable de la minuta
              <input
                value={responsable}
                onChange={(e) => setResponsable(e.target.value)}
                placeholder="Nombre jefatura / pañol"
              />
            </label>
            <button
              type="button"
              className="btn-primary"
              disabled={iniciando || !apiOk}
              onClick={() => void handleIniciar()}
            >
              {iniciando ? "Iniciando…" : "Comenzar reunión"}
            </button>
          </section>
        )}

        {vistaHistorial && (
          <div className="banner info">
            Viendo reunión {vistaHistorial.semana_iso} ({vistaHistorial.estado})
            <button type="button" className="btn-sm btn-ghost" onClick={() => setVistaHistorial(null)}>
              Volver a reunión actual
            </button>
          </div>
        )}

        {mostrar && (
          <div className="grid-main">
            <div className="col-principal">
              <section className="panel sesion-head">
                <div>
                  <h2>Semana {mostrar.semana_iso}</h2>
                  <p className="sub">
                    {mostrar.fecha}
                    {mostrar.responsable ? ` · ${mostrar.responsable}` : ""}
                    {mostrar.email_enviado_en && " · Minuta enviada"}
                  </p>
                </div>
                {activa && !vistaHistorial && (
                  <div className="head-actions">
                    <button
                      type="button"
                      className="btn-primary"
                      onClick={() => setModalEmail(true)}
                    >
                      Finalizar y enviar mail
                    </button>
                  </div>
                )}
              </section>

              {!readOnly && (
                <SolicitudFormPanel onSubmit={onNuevaSolicitud} disabled={!apiOk} />
              )}

              <section className="panel">
                <h3>Solicitudes ({mostrar.solicitudes.length})</h3>
                <div className="sol-list">
                  {mostrar.solicitudes.map((s) => (
                    <SolicitudCard
                      key={s.id}
                      solicitud={s}
                      sesionId={mostrar.id}
                      autorDefault={responsable}
                      readOnly={readOnly}
                      onEntrega={async (sid, data) => {
                        await agregarEntrega(mostrar.id, sid, data);
                        await reloadSesion(mostrar.id);
                      }}
                      onActualizacion={async (sid, data) => {
                        await agregarActualizacion(mostrar.id, sid, data);
                        await reloadSesion(mostrar.id);
                      }}
                      onCerrar={async (sid) => {
                        if (!confirm("¿Dar de baja el seguimiento de esta solicitud?")) return;
                        await cerrarSolicitud(mostrar.id, sid);
                        await reloadSesion(mostrar.id);
                      }}
                    />
                  ))}
                  {!mostrar.solicitudes.length && (
                    <p className="muted">No hay solicitudes en seguimiento.</p>
                  )}
                </div>
              </section>

              <TemasPanel
                temas={mostrar.temas}
                readOnly={readOnly}
                onCrear={async (f: TemaForm) => {
                  if (!activa) return;
                  await crearTema(activa.id, {
                    titulo: f.titulo.trim(),
                    descripcion: f.descripcion.trim() || undefined,
                  });
                  await reloadSesion(activa.id);
                }}
                onToggle={async (id, resuelto) => {
                  await toggleTemaResuelto(id, resuelto);
                  await reloadSesion(mostrar.id);
                }}
              />

              {!readOnly && (
                <section className="panel">
                  <h3>Notas generales de la reunión</h3>
                  <textarea
                    rows={4}
                    value={notas || mostrar.notas_generales || ""}
                    onChange={(e) => setNotas(e.target.value)}
                    placeholder="Acuerdos, observaciones, pendientes globales…"
                  />
                  <button type="button" className="btn-sm btn-ghost" onClick={() => void guardarNotas()}>
                    Guardar notas
                  </button>
                </section>
              )}

              {readOnly && mostrar.notas_generales && (
                <section className="panel">
                  <h3>Notas generales</h3>
                  <p>{mostrar.notas_generales}</p>
                </section>
              )}
            </div>

            <HistorialPanel
              sesiones={historial}
              actualId={activa?.id ?? null}
              onSeleccionar={(id) => void getSesion(id).then(setVistaHistorial)}
            />
          </div>
        )}
      </main>

      {activa && (
        <EnviarMinutaModal
          sesionId={activa.id}
          open={modalEmail}
          onClose={() => setModalEmail(false)}
          onEnviado={() => void refrescar()}
        />
      )}

      <footer className="footer">
        Los datos persisten en SQLite (servidor). Al cerrar la semana con envío, iniciá una nueva
        reunión para continuar el seguimiento.
      </footer>
    </div>
  );
}
