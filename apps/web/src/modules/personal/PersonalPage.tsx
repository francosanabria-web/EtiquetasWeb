/**
 * PersonalPage — Módulo completo de gestión de personal con datagrid, filtros y modales.
 */

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../../auth/AuthContext";
import { permisoDe } from "../../config/navegacion";
import {
  getPersonal,
  getAreas,
  deletePersonal,
  type Personal,
  type Area,
} from "../../api/personalClient";
import PersonalTabla from "./PersonalTabla";
import PersonalFormModal from "./PersonalFormModal";
import PersonalMailPrefs from "./PersonalMailPrefs";

const PAGE_SIZE = 25;

export default function PersonalPage() {
  const { usuario, token } = useAuth();
  const puedeEscribir = permisoDe(usuario, "personal") === "escritura";

  const [items, setItems] = useState<Personal[]>([]);
  const [total, setTotal] = useState(0);
  const [areas, setAreas] = useState<Area[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  // Filtros
  const [q, setQ] = useState("");
  const [areaIdFiltro, setAreaIdFiltro] = useState<number | "">("");
  const [tipoFiltro, setTipoFiltro] = useState("");
  const [activoFiltro, setActivoFiltro] = useState<boolean | "">("");

  // Paginación
  const [offset, setOffset] = useState(0);

  // Modal
  const [sel, setSel] = useState<Personal | null>(null);
  const [creando, setCreando] = useState(false);
  const [eliminando, setEliminando] = useState<number | null>(null);

  const cargar = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string | number | boolean> = { limit: PAGE_SIZE, offset, include_prefs: 1 };
      if (q) params.q = q;
      if (areaIdFiltro !== "") params.area_id = areaIdFiltro;
      if (tipoFiltro) params.tipo = tipoFiltro;
      if (activoFiltro !== "") params.activo = activoFiltro;
      const data = await getPersonal(token, params as any);
      setItems(data.items);
      setTotal(data.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudieron cargar los registros.");
    } finally {
      setLoading(false);
    }
  }, [token, q, areaIdFiltro, tipoFiltro, activoFiltro, offset]);

  const cargarAreas = useCallback(async () => {
    if (!token) return;
    try {
      const areasData = await getAreas(token);
      setAreas(areasData);
    } catch {
      // Silencioso
    }
  }, [token]);

  useEffect(() => { void cargar(); }, [cargar]);
  useEffect(() => { void cargarAreas(); }, [cargarAreas]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  const handleGuardado = async (p: Personal) => {
    setSel(null);
    setCreando(false);
    setAviso(p.id ? `Personal "${p.nombre}" actualizado.` : `Personal "${p.nombre}" creado.`);
    await cargar();
  };

  const handleDelete = async (id: number) => {
    if (!window.confirm("¿Desactivar este registro de personal? (soft delete)")) return;
    setEliminando(id);
    try {
      await deletePersonal(token!, id);
      setAviso("Personal desactivado correctamente.");
      await cargar();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al desactivar.");
    } finally {
      setEliminando(null);
    }
  };

  return (
    <div className="page-content sol-page">
      <header className="page-header sol-header">
        <div>
          <h1>Personal</h1>
          <p className="sub">Gestión de personal y áreas. Busca, filtra y administra registros.</p>
        </div>
        {puedeEscribir && (
          <button type="button" className="btn-primary" onClick={() => { setSel(null); setCreando(true); }}>
            + Nuevo Personal
          </button>
        )}
      </header>

      {error && <p className="error" role="status">{error}</p>}
      {aviso && <p className="minuta-ok" role="status">{aviso}</p>}

      {/* Filtros */}
      <div className="sol-filters">
        <label>
          Buscar
          <input value={q} onChange={(e) => { setQ(e.target.value); setOffset(0); }} placeholder="Nombre…" />
        </label>
        <label>
          Área
          <select value={areaIdFiltro} onChange={(e) => { setAreaIdFiltro(Number(e.target.value) || ""); setOffset(0); }}>
            <option value="">Todas</option>
            {areas.map((a) => (
              <option key={a.id} value={a.id}>{a.nombre}</option>
            ))}
          </select>
        </label>
        <label>
          Tipo
          <select value={tipoFiltro} onChange={(e) => { setTipoFiltro(e.target.value); setOffset(0); }}>
            <option value="">Todos</option>
            <option value="tecnico">Técnico</option>
            <option value="supervisor">Supervisor</option>
            <option value="produccion">Producción</option>
            <option value="generico">Genérico</option>
            <option value="panol">Pañol</option>
          </select>
        </label>
        <label>
          Activo
          <select value={activoFiltro === "" ? "" : activoFiltro ? "1" : "0"} onChange={(e) => { setActivoFiltro(e.target.value === "" ? "" : e.target.value === "1"); setOffset(0); }}>
            <option value="">Todos</option>
            <option value="1">Sí</option>
            <option value="0">No</option>
          </select>
        </label>
      </div>

      <div className="sol-layout">
        <div className="sol-table-wrap">
          <PersonalTabla items={items} loading={loading} selectedId={sel?.id ?? null} onSelect={setSel} />
        </div>

        {/* Detalle / Edición */}
        {sel && (
          <aside className="sol-detalle" aria-label="Detalle de personal">
            <div className="sol-detalle-head">
              <h2>{sel.nombre}</h2>
              <button type="button" className="btn-ghost btn-sm" onClick={() => setSel(null)}>Cerrar</button>
            </div>
            <div className="sol-detalle-edit">
              <p><strong>Legajo:</strong> {sel.legajo ?? "—"}</p>
              <p><strong>Email:</strong> {sel.email ?? "—"}</p>
              <p><strong>Tipo:</strong> {sel.tipo}</p>
              <p><strong>Área ID:</strong> {sel.area_id ?? "—"}</p>
              <p><strong>Activo:</strong> {sel.activo ? "Sí" : "No"}</p>
              <PersonalMailPrefs personalId={sel.id} personalNombre={sel.nombre} token={token!} />
              {puedeEscribir && (
                <>
                  <button type="button" className="btn-primary btn-sm" onClick={() => setCreando(true)}>
                    Editar
                  </button>
                  <button
                    type="button"
                    className="btn-ghost sol-borrar"
                    onClick={() => handleDelete(sel.id)}
                    disabled={eliminando === sel.id}
                  >
                    {eliminando === sel.id ? "Desactivando…" : "Desactivar"}
                  </button>
                </>
              )}
            </div>
          </aside>
        )}
      </div>

      {/* Paginación */}
      {totalPages > 1 && (
        <div className="sol-pagination">
          <button type="button" className="btn-ghost btn-sm" disabled={offset === 0} onClick={() => setOffset(offset - PAGE_SIZE)}>
            Anterior
          </button>
          <span>Página {Math.floor(offset / PAGE_SIZE) + 1} de {totalPages}</span>
          <button type="button" className="btn-ghost btn-sm" disabled={offset + PAGE_SIZE >= total} onClick={() => setOffset(offset + PAGE_SIZE)}>
            Siguiente
          </button>
        </div>
      )}

      {/* Modal creación/edición */}
      {creando && (
        <div className="sol-modal-backdrop" role="dialog" aria-modal="true">
          <div className="sol-modal sol-modal-wide">
            <PersonalFormModal
              areas={areas}
              editing={sel}
              onGuardado={handleGuardado}
              onCancelar={() => { setCreando(false); setSel(null); }}
              token={token!}
              cargando={false}
            />
          </div>
        </div>
      )}
    </div>
  );
}
