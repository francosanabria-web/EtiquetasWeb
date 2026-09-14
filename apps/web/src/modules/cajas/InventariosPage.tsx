/**
 * InventariosPage — Gestion de inventarios mensuales con header + detalle.
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { permisoDe } from "../../config/navegacion";
import {
  getInventarios, updateInventarioEstado, deleteInventario,
  type Inventario,
} from "../../api/cajasClient";
import { getPersonal, type Personal } from "../../api/personalClient";
import InventarioFormModal from "./InventarioFormModal";

const PAGE_SIZE = 25;

export default function InventariosPage() {
  const navigate = useNavigate();
  const { usuario, token } = useAuth();
  const puedeEscribir = permisoDe(usuario, "cajas") === "escritura";
  const puedeLeer = permisoDe(usuario, "cajas") !== "sin_acceso";

  const [inventarios, setInventarios] = useState<Inventario[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  // Filtros
  const [cajaIdFiltro, setCajaIdFiltro] = useState("");
  const [periodoFiltro, setPeriodoFiltro] = useState("");
  const [estadoFiltro, setEstadoFiltro] = useState("");
  const [qFiltro, setQFiltro] = useState("");

  // Paginacion
  const [offset, setOffset] = useState(0);

  // Modal
  const [creando, setCreando] = useState(false);
  const [eliminando, setEliminando] = useState<number | null>(null);
  const [cerrandoId, setCerrandoId] = useState<number | null>(null);

  // Dropdowns personal
  const [tecnicos, setTecnicos] = useState<Personal[]>([]);
  const [supervisores, setSupervisores] = useState<Personal[]>([]);

  const cargar = useCallback(async () => {
    if (!token || !puedeLeer) return;
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string> = { limit: String(PAGE_SIZE), offset: String(offset) };
      if (cajaIdFiltro) params.caja_id = cajaIdFiltro;
      if (periodoFiltro) params.periodo = periodoFiltro;
      if (estadoFiltro) params.estado = estadoFiltro;
      if (qFiltro) params.q = qFiltro;
      const data = await getInventarios(token, params as any);
      setInventarios(data.items);
      setTotal(data.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudieron cargar los inventarios.");
    } finally {
      setLoading(false);
    }
  }, [token, qFiltro, cajaIdFiltro, periodoFiltro, estadoFiltro, offset, puedeLeer]);

  useEffect(() => { void cargar(); }, [cargar]);

  // Cargar personal para dropdowns
  useEffect(() => {
    if (!token) return;
    const loadPersonal = async () => {
      try {
        const tech = await getPersonal(token, { tipo: "tecnico", limit: 100 });
        const sup = await getPersonal(token, { tipo: "supervisor", limit: 100 });
        setTecnicos(tech.items);
        setSupervisores(sup.items);
      } catch { /* ignore */ }
    };
    loadPersonal();
  }, [token]);

  const inventariosPages = Math.ceil(total / PAGE_SIZE);

  const handleGuardar = async (inv: Inventario) => {
    setCreando(false);
    setAviso(`Inventario ${inv.periodo} guardado.`);
    await cargar();
  };

  const handleDelete = async (id: number) => {
    if (!window.confirm("¿Desea eliminar este inventario? (Solo borradores)")) return;
    setEliminando(id);
    try {
      await deleteInventario(token!, id);
      setAviso("Inventario eliminado correctamente.");
      await cargar();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al eliminar.");
    } finally {
      setEliminando(null);
    }
  };

  const handleCerrar = async (id: number) => {
    setCerrandoId(id);
    try {
      await updateInventarioEstado(token!, id, "cerrado");
      setAviso("Inventario cerrado correctamente.");
      await cargar();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al cerrar.");
    } finally {
      setCerrandoId(null);
    }
  };

  const handleQChange = (v: string) => { setQFiltro(v); setOffset(0); };

  return (
    <div className="page-content sol-page">
      <header className="page-header sol-header">
        <div>
          <h1>Inventarios Mensuales</h1>
          <p className="sub">Gestión de inventarios por caja y período. Un inventario por caja por mes.</p>
        </div>
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
          <button type="button" className="btn-ghost" onClick={() => navigate("/admin/cajas")}>
            ← Volver a Cajas
          </button>
          {puedeEscribir && (
            <button type="button" className="btn-primary" onClick={() => setCreando(true)}>
              + Nuevo Inventario
            </button>
          )}
        </div>
      </header>

      {error && <p className="error" role="status">{error}</p>}
      {aviso && <p className="minuta-ok" role="status">{aviso}</p>}

      {/* Filtros */}
      <div className="sol-filters">
        <label>
          Caja ID
          <input value={cajaIdFiltro} onChange={(e) => { setCajaIdFiltro(e.target.value); setOffset(0); }} placeholder="Ej: 1" />
        </label>
        <label>
          Período
          <input type="month" value={periodoFiltro} onChange={(e) => { setPeriodoFiltro(e.target.value); setOffset(0); }} />
        </label>
        <label>
          Estado
          <select value={estadoFiltro} onChange={(e) => { setEstadoFiltro(e.target.value); setOffset(0); }}>
            <option value="">Todos</option>
            <option value="borrador">Borrador</option>
            <option value="cerrado">Cerrado</option>
          </select>
        </label>
        <label>
          Buscar personal
          <input value={qFiltro} onChange={(e) => handleQChange(e.target.value)} placeholder="Buscar por nombre…" />
        </label>
      </div>

      {loading && <p className="sol-hint">Cargando inventarios…</p>}
      {!loading && inventarios.length === 0 && <p className="sol-hint">Sin resultados.</p>}

      {/* Tabla de inventarios */}
      <table className="sol-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Caja</th>
            <th>Período</th>
            <th>Técnico</th>
            <th>Supervisor</th>
            <th>Estado</th>
            <th>Acciones</th>
          </tr>
        </thead>
        <tbody>
          {inventarios.map((inv) => (
            <tr key={inv.id}>
              <td>{inv.id}</td>
              <td>{inv.caja_codigo}</td>
              <td>{inv.periodo}</td>
              <td>{inv.tecnico_nombre}</td>
              <td>{inv.supervisor_nombre}</td>
              <td>
                <span className={`sol-estado sol-estado-${inv.estado === "cerrado" ? "cancelado" : "cumplido"}`}>
                  {inv.estado}
                </span>
              </td>
              <td>
                {puedeEscribir && inv.estado === "borrador" && (
                  <>
                    <button type="button" className="btn-ghost btn-sm" onClick={() => handleCerrar(inv.id)} disabled={cerrandoId === inv.id}>
                      Cerrar
                    </button>
                    <button type="button" className="btn-ghost btn-sm" onClick={() => handleDelete(inv.id)} disabled={eliminando === inv.id}>
                      Eliminar
                    </button>
                  </>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Paginación */}
      {inventariosPages > 1 && (
        <div className="sol-pagination">
          <button type="button" className="btn-ghost btn-sm" disabled={offset === 0} onClick={() => setOffset(offset - PAGE_SIZE)}>Anterior</button>
          <span>Página {Math.floor(offset / PAGE_SIZE) + 1} de {inventariosPages}</span>
          <button type="button" className="btn-ghost btn-sm" disabled={offset + PAGE_SIZE >= total} onClick={() => setOffset(offset + PAGE_SIZE)}>Siguiente</button>
        </div>
      )}

      {/* Modal creación */}
      {creando && (
        <div className="sol-modal-backdrop" role="dialog" aria-modal="true">
          <div className="sol-modal sol-modal-wide">
            <InventarioFormModal
              tecnicos={tecnicos}
              supervisores={supervisores}
              onGuardado={handleGuardar}
              onCancelar={() => setCreando(false)}
              token={token!}
              cargando={false}
            />
          </div>
        </div>
      )}
    </div>
  );
}
