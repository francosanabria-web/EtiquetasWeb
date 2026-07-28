import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  TIPOS_REUNION,
  actualizarReunion,
  crearReunion,
  eliminarReunion,
  fetchReuniones,
  fetchSectores,
  labelTipo,
  type Reunion,
  type TipoReunion,
  type VisibilidadReunion,
} from "../../api/minutaClient";
import { useAuth } from "../../auth/AuthContext";
import { fechaHoyIso, fmtFecha } from "./types";

export default function MinutaListadoPage() {
  const { usuario } = useAuth();
  const navigate = useNavigate();
  const email = (usuario?.email ?? "").toLowerCase();
  const [reuniones, setReuniones] = useState<Reunion[]>([]);
  const [archivadas, setArchivadas] = useState<Reunion[]>([]);
  const [historicos, setHistoricos] = useState<Reunion[]>([]);
  const [mostrarArchivadas, setMostrarArchivadas] = useState(false);
  const [mostrarHistoricos, setMostrarHistoricos] = useState(false);
  const [sectores, setSectores] = useState<string[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mostrarCrear, setMostrarCrear] = useState(false);
  const [creando, setCreando] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState({
    titulo: "",
    visibilidad: "individual" as VisibilidadReunion,
    sector: "MANTENIMIENTO",
  });
  const [busyId, setBusyId] = useState<number | null>(null);
  const [form, setForm] = useState({
    titulo: "",
    fecha: fechaHoyIso(),
    tipo: "semanal" as TipoReunion,
    visibilidad: "individual" as VisibilidadReunion,
    sector: "MANTENIMIENTO",
    sectores_comprometidos: "Mantenimiento",
  });

  const cargar = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      const [list, arch, secs] = await Promise.all([
        fetchReuniones({ owner: email, limite: 80 }),
        fetchReuniones({ owner: email, archivadas: true, limite: 80 }),
        fetchSectores(),
      ]);
      const noHist = (r: Reunion) => !String(r.titulo || "").startsWith("Histórico");
      const esArchivada = (r: Reunion) => Number(r.archivada ?? 0) === 1;
      const esHistorico = (r: Reunion) => String(r.titulo || "").startsWith("Histórico");
      // Activas sin históricos; archivadas reales; históricos aparte (recuperación / envío)
      setReuniones(list.filter((r) => noHist(r) && !esArchivada(r)));
      setArchivadas(arch.filter((r) => noHist(r) && esArchivada(r)));
      setHistoricos(
        [...list, ...arch].filter((r) => esHistorico(r) && !esArchivada(r)),
      );
      setSectores(secs);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudieron cargar las reuniones.");
    } finally {
      setCargando(false);
    }
  }, [email]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  const crear = async () => {
    setCreando(true);
    setError(null);
    try {
      const r = await crearReunion({
        ...form,
        titulo: form.titulo.trim() || `Reunión ${form.fecha}`,
        owner_email: email,
      });
      setMostrarCrear(false);
      navigate(`/minuta/${r.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo crear la reunión.");
    } finally {
      setCreando(false);
    }
  };

  const guardarEdicion = async (id: number) => {
    const titulo = editForm.titulo.trim();
    if (!titulo) {
      setError("El título no puede quedar vacío.");
      return;
    }
    setBusyId(id);
    try {
      const r = await actualizarReunion(id, {
        titulo,
        visibilidad: editForm.visibilidad,
        sector: editForm.sector,
      });
      setReuniones((list) => list.map((x) => (x.id === id ? { ...x, ...r } : x)));
      setArchivadas((list) => list.map((x) => (x.id === id ? { ...x, ...r } : x)));
      setEditId(null);
      await cargar();
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo guardar.");
    } finally {
      setBusyId(null);
    }
  };

  const archivar = async (r: Reunion, valor: boolean) => {
    setBusyId(r.id);
    try {
      await actualizarReunion(r.id, { archivada: valor ? 1 : 0 });
      await cargar();
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo archivar.");
    } finally {
      setBusyId(null);
    }
  };

  const borrar = async (r: Reunion) => {
    const ok = window.confirm(
      `¿Eliminar «${r.titulo || fmtFecha(r.fecha)}»?\nLos pedidos se mueven al Histórico del sector (no se pierden).`,
    );
    if (!ok) return;
    setBusyId(r.id);
    try {
      await eliminarReunion(r.id);
      await cargar();
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo eliminar.");
    } finally {
      setBusyId(null);
    }
  };

  const porTipo = (lista: Reunion[], tipo: TipoReunion) =>
    lista.filter((r) => (r.tipo || "semanal") === tipo);

  const renderCard = (r: Reunion, esArchivada: boolean) => (
    <li key={r.id} className="minuta-reunion-li">
      <div className="minuta-reunion-card">
        {editId === r.id ? (
          <div className="minuta-rename-row">
            <label>
              Título
              <input
                value={editForm.titulo}
                onChange={(e) => setEditForm((f) => ({ ...f, titulo: e.target.value }))}
                autoFocus
              />
            </label>
            <label>
              Visibilidad
              <select
                value={editForm.visibilidad}
                onChange={(e) =>
                  setEditForm((f) => ({
                    ...f,
                    visibilidad: e.target.value as VisibilidadReunion,
                  }))
                }
              >
                <option value="individual">Individual (solo vos)</option>
                <option value="compartida">Compartida / grupal (sector)</option>
              </select>
            </label>
            <label>
              Sector
              <select
                value={editForm.sector}
                onChange={(e) =>
                  setEditForm((f) => ({ ...f, sector: e.target.value.toUpperCase() }))
                }
              >
                {(sectores.length ? sectores : ["MANTENIMIENTO", "PAÑOL"]).map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </label>
            <div className="minuta-rename-actions">
              <button
                type="button"
                className="btn-primary btn-sm"
                disabled={busyId === r.id}
                onClick={() => void guardarEdicion(r.id)}
              >
                Guardar
              </button>
              <button type="button" className="btn-ghost btn-sm" onClick={() => setEditId(null)}>
                Cancelar
              </button>
            </div>
          </div>
        ) : (
          <Link to={`/minuta/${r.id}`}>
            <strong>{r.titulo || `Reunión ${fmtFecha(r.fecha)}`}</strong>
          </Link>
        )}
        {editId !== r.id && (
          <>
            <span>{fmtFecha(r.fecha)}</span>
            <span className="minuta-reunion-meta">
              {labelTipo(r.tipo)} ·{" "}
              {r.visibilidad === "compartida" ? "Compartida" : "Individual"} · {r.sector}
            </span>
            {r.email_enviado_en && <span className="minuta-enviada-badge">Mail enviado</span>}
            <div className="minuta-reunion-actions">
              <button
                type="button"
                className="btn-ghost btn-sm"
                disabled={busyId === r.id}
                onClick={() => {
                  setEditId(r.id);
                  setEditForm({
                    titulo: r.titulo || "",
                    visibilidad: (r.visibilidad || "individual") as VisibilidadReunion,
                    sector: r.sector || "MANTENIMIENTO",
                  });
                }}
              >
                Editar
              </button>
              {esArchivada ? (
                <button
                  type="button"
                  className="btn-ghost btn-sm"
                  disabled={busyId === r.id}
                  onClick={() => void archivar(r, false)}
                >
                  Restaurar
                </button>
              ) : (
                <button
                  type="button"
                  className="btn-ghost btn-sm"
                  disabled={busyId === r.id}
                  onClick={() => void archivar(r, true)}
                >
                  Archivar
                </button>
              )}
              <button
                type="button"
                className="btn-ghost btn-sm minuta-btn-danger"
                disabled={busyId === r.id}
                onClick={() => void borrar(r)}
              >
                Eliminar
              </button>
            </div>
          </>
        )}
      </div>
    </li>
  );

  return (
    <div className="minuta-page">
      <header className="page-header">
        <h1>Minutas de reunión</h1>
        <p className="sub">
          Elegí la reunión del día o creá una nueva. Podés renombrar, archivar o eliminar reuniones
          viejas.
        </p>
      </header>

      {error && (
        <p className="error" role="status">
          {error}
        </p>
      )}

      <div className="minuta-section-head">
        <h2>Mis reuniones</h2>
        <div className="minuta-actions-inline">
          <button
            type="button"
            className="btn-ghost btn-sm"
            onClick={() => setMostrarHistoricos((v) => !v)}
          >
            {mostrarHistoricos ? "Ocultar históricos" : `Históricos (${historicos.length})`}
          </button>
          <button
            type="button"
            className="btn-ghost btn-sm"
            onClick={() => setMostrarArchivadas((v) => !v)}
          >
            {mostrarArchivadas ? "Ocultar archivadas" : `Archivadas (${archivadas.length})`}
          </button>
          <button type="button" className="btn-primary btn-sm" onClick={() => setMostrarCrear(true)}>
            + Nueva reunión
          </button>
        </div>
      </div>

      {cargando ? (
        <p className="minuta-hint">Cargando…</p>
      ) : reuniones.length === 0 ? (
        <p className="minuta-hint">Todavía no hay reuniones activas. Creá la primera.</p>
      ) : (
        TIPOS_REUNION.map((t) => {
          const items = porTipo(reuniones, t.value);
          if (items.length === 0) return null;
          return (
            <section key={t.value} className="minuta-section">
              <h3 className="minuta-tipo-title">{t.label}</h3>
              <ul className="minuta-reuniones-grid">{items.map((r) => renderCard(r, false))}</ul>
            </section>
          );
        })
      )}

      {mostrarHistoricos && (
        <section className="minuta-section">
          <h3 className="minuta-tipo-title">Históricos (ítems migrados / reunión eliminada)</h3>
          <p className="minuta-hint">
            Si al enviar falla o la reunión nueva está vacía, abrí acá el histórico del sector: ahí
            suelen estar los pedidos con las novedades.
          </p>
          {historicos.length === 0 ? (
            <p className="minuta-hint">No hay reuniones históricas visibles.</p>
          ) : (
            <ul className="minuta-reuniones-grid">
              {historicos.map((r) => renderCard(r, false))}
            </ul>
          )}
        </section>
      )}

      {mostrarArchivadas && (
        <section className="minuta-section">
          <h3 className="minuta-tipo-title">Archivadas</h3>
          {archivadas.length === 0 ? (
            <p className="minuta-hint">No hay reuniones archivadas.</p>
          ) : (
            <ul className="minuta-reuniones-grid">
              {archivadas.map((r) => renderCard(r, true))}
            </ul>
          )}
        </section>
      )}

      {mostrarCrear && (
        <div className="minuta-modal-backdrop" role="dialog" aria-modal="true">
          <div className="minuta-modal">
            <h3>Nueva reunión</h3>
            <label>
              Título
              <input
                value={form.titulo}
                onChange={(e) => setForm((f) => ({ ...f, titulo: e.target.value }))}
                placeholder="Ej: Semanal mantenimiento"
              />
            </label>
            <label>
              Fecha
              <input
                type="date"
                value={form.fecha}
                onChange={(e) => setForm((f) => ({ ...f, fecha: e.target.value }))}
              />
            </label>
            <label>
              Tipo
              <select
                value={form.tipo}
                onChange={(e) =>
                  setForm((f) => ({ ...f, tipo: e.target.value as TipoReunion }))
                }
              >
                {TIPOS_REUNION.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Visibilidad
              <select
                value={form.visibilidad}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    visibilidad: e.target.value as VisibilidadReunion,
                  }))
                }
              >
                <option value="individual">Individual (solo vos)</option>
                <option value="compartida">Compartida (sector)</option>
              </select>
            </label>
            <label>
              Sector
              <select
                value={form.sector}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    sector: e.target.value.toUpperCase(),
                    sectores_comprometidos: f.sectores_comprometidos || e.target.value,
                  }))
                }
              >
                {(sectores.length ? sectores : ["MANTENIMIENTO", "PAÑOL"]).map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Sectores comprometidos
              <input
                value={form.sectores_comprometidos}
                onChange={(e) =>
                  setForm((f) => ({ ...f, sectores_comprometidos: e.target.value }))
                }
                placeholder="Ej: Mantenimiento - Compras"
              />
            </label>
            <div className="minuta-modal-actions">
              <button
                type="button"
                className="btn-ghost"
                onClick={() => setMostrarCrear(false)}
                disabled={creando}
              >
                Cancelar
              </button>
              <button type="button" className="btn-primary" disabled={creando} onClick={crear}>
                {creando ? "Creando…" : "Crear e ingresar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
