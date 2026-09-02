import { useCallback, useEffect, useState } from "react";
import {
  actualizarSesion,
  agregarNotaFila,
  abandonarSesion,
  API_URL,
  crearTema,
  fijarSeleccionReunion,
  getSesion,
  importarExcel,
  listarPedidos,
  toggleTemaResuelto,
} from "./api/client";
import EnviarMinutaModal from "./components/EnviarMinutaModal";
import HistorialPanel from "./components/HistorialPanel";
import ImportExcelPanel from "./components/ImportExcelPanel";
import PedidosReunionPanel from "./components/PedidosReunionPanel";
import TemasPanel from "./components/TemasPanel";
import { useMinutaSession } from "./hooks/useMinutaSession";
import type { PedidoGrupo, SesionDetalle, TemaForm } from "./types/minuta";

const SHELL_URL = import.meta.env.VITE_SHELL_URL;

export default function App() {
  const { sesion, setSesion, historial, cargando, error, setError, apiOk, refrescar, iniciar } =
    useMinutaSession();

  const [operador, setOperador] = useState(
    () => localStorage.getItem("minutas-operador") ?? localStorage.getItem("minutas-responsable") ?? ""
  );
  const [notas, setNotas] = useState("");
  const [modalEmail, setModalEmail] = useState(false);
  const [vistaHistorial, setVistaHistorial] = useState<SesionDetalle | null>(null);
  const [iniciando, setIniciando] = useState(false);
  const [pedidos, setPedidos] = useState<PedidoGrupo[]>([]);
  const [guardandoOperador, setGuardandoOperador] = useState(false);

  const activa = sesion?.estado === "abierta" ? sesion : null;
  const mostrar = vistaHistorial ?? activa;
  const readOnly = !activa || !!vistaHistorial;

  const cargarPedidos = useCallback(async (id: number) => {
    const lista = await listarPedidos(id, true);
    setPedidos(lista);
  }, []);

  useEffect(() => {
    if (activa) void cargarPedidos(activa.id);
  }, [activa, cargarPedidos]);

  async function handleIniciar() {
    setIniciando(true);
    localStorage.setItem("minutas-operador", operador);
    await iniciar(operador);
    setVistaHistorial(null);
    setIniciando(false);
  }

  async function guardarOperador() {
    if (!activa) return;
    const nombre = operador.trim();
    localStorage.setItem("minutas-operador", nombre);
    setGuardandoOperador(true);
    try {
      await actualizarSesion(activa.id, { responsable: nombre || undefined });
      await refrescar();
    } finally {
      setGuardandoOperador(false);
    }
  }

  async function reloadSesion(id: number) {
    const s = await getSesion(id);
    if (id === activa?.id) setSesion(s);
    else setVistaHistorial(s);
    await cargarPedidos(id);
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-icon">📋</span>
          <div>
            <h1>Solicitudes de pedido — Pañol</h1>
            <p className="brand-sub">
              Reuniones, seguimiento de compras/mantenimiento y minutas · SistemasPañol
            </p>
          </div>
        </div>
        <div className="top-meta">
          {!apiOk && <span className="badge warn">API desconectada</span>}
          {activa && !readOnly && (
            <label className="operador-top">
              Pañolero
              <input
                value={operador}
                onChange={(e) => setOperador(e.target.value)}
                onBlur={() => void guardarOperador()}
                placeholder="Tu nombre"
              />
              <button
                type="button"
                className="btn-sm btn-ghost"
                disabled={guardandoOperador}
                onClick={() => void guardarOperador()}
              >
                {guardandoOperador ? "…" : "Guardar"}
              </button>
            </label>
          )}
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
            <button type="button" className="btn-sm btn-ghost" onClick={() => void refrescar()}>
              Reintentar
            </button>
            <button type="button" onClick={() => setError(null)} aria-label="Cerrar">
              ×
            </button>
          </div>
        )}

        {cargando && !sesion && !vistaHistorial && (
          <section className="panel inicio">
            <p className="loading-inline">Cargando…</p>
          </section>
        )}

        {!cargando && !activa && (
          <div className="inicio-wrap">
            <section className="panel inicio">
              <h2>Iniciar reunión</h2>
              <p className="sub">
                Importá el Excel del día, elegí solicitudes a tratar, anotá cambios y cerrá con envío
                de mail.
              </p>
              <label>
                Tu nombre (pañolero — aparece en notas y mail)
                <input value={operador} onChange={(e) => setOperador(e.target.value)} />
              </label>
              <button
                type="button"
                className="btn-primary btn-lg"
                disabled={iniciando || !apiOk}
                onClick={() => void handleIniciar()}
              >
                {iniciando ? "Iniciando…" : "Comenzar reunión"}
              </button>
            </section>
          </div>
        )}

        {mostrar && (
          <div className="grid-main grid-main-wide">
            <div className="col-principal">
              {vistaHistorial && (
                <div className="banner info">
                  Viendo reunión pasada ({vistaHistorial.semana_iso})
                  <button
                    type="button"
                    className="btn-sm btn-ghost"
                    onClick={() => setVistaHistorial(null)}
                  >
                    {activa ? "Volver a reunión actual" : "Volver"}
                  </button>
                </div>
              )}

              <section className="panel sesion-head">
                <div>
                  <h2>Semana {mostrar.semana_iso}</h2>
                  <p className="sub">
                    {mostrar.fecha}
                    {mostrar.responsable ? ` · ${mostrar.responsable}` : ""}
                  </p>
                </div>
                {activa && !readOnly && (
                  <div className="head-actions">
                    <button
                      type="button"
                      className="btn-ghost btn-sm"
                      onClick={() => {
                        if (
                          window.confirm(
                            "¿Abandonar esta reunión sin enviar mail? Podrás comenzar una nueva."
                          )
                        ) {
                          void abandonarSesion(activa.id).then(() => {
                            setVistaHistorial(null);
                            setPedidos([]);
                            void refrescar();
                          });
                        }
                      }}
                    >
                      Abandonar reunión
                    </button>
                    <button type="button" className="btn-primary" onClick={() => setModalEmail(true)}>
                      Cerrar y enviar mail
                    </button>
                  </div>
                )}
              </section>

              {!readOnly && activa && (
                <>
                  <ImportExcelPanel
                    disabled={!apiOk}
                    onImportar={(file) => importarExcel(activa.id, file)}
                    onImportado={() => void cargarPedidos(activa.id)}
                  />
                  <PedidosReunionPanel
                    sesionId={activa.id}
                    pedidos={pedidos}
                    operador={operador}
                    readOnly={readOnly}
                    onConfirmarSeleccion={async (refs) => {
                      await fijarSeleccionReunion(activa.id, refs);
                      await cargarPedidos(activa.id);
                    }}
                    onNota={async (filaId, texto) => {
                      await agregarNotaFila(activa.id, filaId, {
                        texto,
                        autor: operador.trim() || undefined,
                      });
                      await cargarPedidos(activa.id);
                    }}
                  />
                </>
              )}

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

              {!readOnly && activa && (
                <section className="panel">
                  <h3>Notas generales</h3>
                  <textarea
                    rows={3}
                    value={notas || mostrar.notas_generales || ""}
                    onChange={(e) => setNotas(e.target.value)}
                  />
                  <button
                    type="button"
                    className="btn-sm btn-ghost"
                    onClick={() =>
                      void actualizarSesion(activa.id, { notas_generales: notas }).then(() =>
                        refrescar()
                      )
                    }
                  >
                    Guardar notas
                  </button>
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
        Mail: variables MINUTAS_SMTP_* en la PC servidor · ver COMO_MINUTAS.txt
      </footer>
    </div>
  );
}
