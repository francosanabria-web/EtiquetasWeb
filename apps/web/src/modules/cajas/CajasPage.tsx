/**
 * CajasPage — Módulo completo de gestión de cajas y herramientas con datagrid, filtros y modales.
 */

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { useAuth } from "../../auth/AuthContext";
import { permisoDe } from "../../config/navegacion";
import {
  getCajas, getHerramientas, deleteCaja, deleteHerramienta,
  type Caja, type Herramienta,
} from "../../api/cajasClient";
import CajasTabla from "./CajasTabla";
import CajaFormModal from "./CajaFormModal";
import HerramientaFormModal from "./HerramientaFormModal";

const PAGE_SIZE = 25;

export default function CajasPage() {
  const { usuario, token } = useAuth();
  const puedeEscribir = permisoDe(usuario, "cajas") === "escritura";
  const puedeLeer = permisoDe(usuario, "cajas") !== "sin_acceso";

  const [cajas, setCajas] = useState<Caja[]>([]);
  const [herramientas, setHerramientas] = useState<Herramienta[]>([]);
  const [cajasTotal, setCajasTotal] = useState(0);
  const [herramientasTotal, setHerramientasTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  // Filtros cajas
  const [q, setQ] = useState("");
  const [activaFiltro, setActivaFiltro] = useState<boolean | "">("");

  // Filtros herramientas
  const [catFiltro, setCatFiltro] = useState("");

  // Paginación
  const [offset, setOffset] = useState(0);

  // Modales
  const [selCaja, setSelCaja] = useState<Caja | null>(null);
  const [selHerramienta, setSelHerramienta] = useState<Herramienta | null>(null);
  const [creandoCaja, setCreandoCaja] = useState(false);
  const [creandoHerramienta, setCreandoHerramienta] = useState(false);
  const [eliminando, setEliminando] = useState<number | null>(null);

  const cargar = useCallback(async () => {
    if (!token || !puedeLeer) return;
    setLoading(true);
    setError(null);
    try {
      const cData = await getCajas(token, { q, activa: activaFiltro !== "" ? activaFiltro : undefined, limit: PAGE_SIZE, offset });
      const hData = await getHerramientas(token, { q: "", categoria: catFiltro || undefined, limit: PAGE_SIZE, offset });
      setCajas(cData.items);
      setCajasTotal(cData.total);
      setHerramientas(hData.items);
      setHerramientasTotal(hData.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudieron cargar los registros.");
    } finally {
      setLoading(false);
    }
  }, [token, q, activaFiltro, catFiltro, offset, puedeLeer]);

  useEffect(() => { void cargar(); }, [cargar]);

  const cajasPages = Math.ceil(cajasTotal / PAGE_SIZE);
  const herramientasPages = Math.ceil(herramientasTotal / PAGE_SIZE);

  const handleGuardarCaja = async (c: Caja) => {
    setSelCaja(null);
    setCreandoCaja(false);
    setAviso(c.id ? `Caja "${c.codigo}" actualizada.` : `Caja "${c.codigo}" creada.`);
    await cargar();
  };

  const handleGuardarHerramienta = async (h: Herramienta) => {
    setSelHerramienta(null);
    setCreandoHerramienta(false);
    setAviso(h.id ? `Herramienta "${h.codigo}" actualizada.` : `Herramienta "${h.codigo}" creada.`);
    await cargar();
  };

  const handleDeleteCaja = async (id: number) => {
    if (!window.confirm("¿Desea eliminar esta caja? (Se requiere que no tenga registros asociados)")) return;
    setEliminando(id);
    try {
      await deleteCaja(token!, id);
      setAviso("Caja eliminada correctamente.");
      await cargar();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al eliminar.");
    } finally {
      setEliminando(null);
    }
  };

  const handleDeleteHerramienta = async (id: number) => {
    if (!window.confirm("¿Desea eliminar esta herramienta? (Se requiere que no tenga registros de inventario)")) return;
    setEliminando(id);
    try {
      await deleteHerramienta(token!, id);
      setAviso("Herramienta eliminada correctamente.");
      await cargar();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al eliminar.");
    } finally {
      setEliminando(null);
    }
  };

  const handleQChange = (v: string) => { setQ(v); setOffset(0); };
  const handleActivaChange = (v: boolean | "") => { setActivaFiltro(v); setOffset(0); };
  const handleCatChange = (v: string) => { setCatFiltro(v); setOffset(0); };

  return (
    <div className="page-content sol-page">
      <header className="page-header sol-header">
        <div>
          <h1>Cajas de Herramientas</h1>
          <p className="sub">Gestión de cajas y herramientas. Busca, filtra y administra registros.</p>
        </div>
        {puedeEscribir && (
          <>
            <button type="button" className="btn-primary" onClick={() => { setSelCaja(null); setCreandoCaja(true); }}>
              + Nueva Caja
            </button>
            <button type="button" className="btn-primary" onClick={() => { setSelHerramienta(null); setCreandoHerramienta(true); }}>
              + Nueva Herramienta
            </button>
          </>
        )}
      </header>

      {error && <p className="error" role="status">{error}</p>}
      {aviso && <p className="minuta-ok" role="status">{aviso}</p>}

      {/* Filtros Cajas */}
      <div className="sol-filters">
        <label>
          Buscar cajas
          <input value={q} onChange={(e) => handleQChange(e.target.value)} placeholder="Buscar por código…" />
        </label>
        <label>
          Activa
          <select value={activaFiltro} onChange={(e) => { setActivaFiltro(e.target.value === "" ? "" : e.target.value === "1"); setOffset(0); }}>
            <option value="">Todas</option>
            <option value="1">Sí</option>
            <option value="0">No</option>
          </select>
        </label>
      </div>

      {/* Filtros Herramientas */}
      <div className="sol-filters">
        <label>
          Categoría
          <select value={catFiltro} onChange={(e) => handleCatChange(e.target.value)}>
            <option value="">Todas</option>
            <option value="HERRAMIENTA">Herramienta</option>
            <option value="REPUESTO">Repuesto</option>
            <option value="ACCESORIO">Accesorio</option>
            <option value="MEDIDA">Medida</option>
            <option value="OTRO">Otro</option>
          </select>
        </label>
      </div>

      <div className="sol-layout">
        <div className="sol-table-wrap">
          <CajasTabla
            cajas={cajas} herramientas={herramientas} loading={loading}
            selectedCajaId={selCaja?.id ?? null} selectedHerramientaId={selHerramienta?.id ?? null}
            onSelectCaja={setSelCaja} onSelectHerramienta={setSelHerramienta}
          />
        </div>
      </div>

      {/* Paginación Cajas */}
      {cajasPages > 1 && (
        <div className="sol-pagination">
          <button type="button" className="btn-ghost btn-sm" disabled={offset === 0} onClick={() => setOffset(offset - PAGE_SIZE)}>Anterior</button>
          <span>Página {Math.floor(offset / PAGE_SIZE) + 1} de {cajasPages}</span>
          <button type="button" className="btn-ghost btn-sm" disabled={offset + PAGE_SIZE >= cajasTotal} onClick={() => setOffset(offset + PAGE_SIZE)}>Siguiente</button>
        </div>
      )}

      {/* Paginación Herramientas */}
      {herramientasPages > 1 && (
        <div className="sol-pagination">
          <button type="button" className="btn-ghost btn-sm" disabled={offset === 0} onClick={() => setOffset(offset - PAGE_SIZE)}>Anterior</button>
          <span>Página {Math.floor(offset / PAGE_SIZE) + 1} de {herramientasPages}</span>
          <button type="button" className="btn-ghost btn-sm" disabled={offset + PAGE_SIZE >= herramientasTotal} onClick={() => setOffset(offset + PAGE_SIZE)}>Siguiente</button>
        </div>
      )}

      {/* Modal creación/edición Caja */}
      {creandoCaja && (
        <div className="sol-modal-backdrop" role="dialog" aria-modal="true">
          <div className="sol-modal sol-modal-wide">
            <CajaFormModal
              editing={selCaja}
              onGuardado={handleGuardarCaja}
              onCancelar={() => { setCreandoCaja(false); setSelCaja(null); }}
              token={token!}
              cargando={false}
            />
          </div>
        </div>
      )}

      {/* Modal creación/edición Herramienta */}
      {creandoHerramienta && (
        <div className="sol-modal-backdrop" role="dialog" aria-modal="true">
          <div className="sol-modal sol-modal-wide">
            <HerramientaFormModal
              editing={selHerramienta}
              onGuardado={handleGuardarHerramienta}
              onCancelar={() => { setCreandoHerramienta(false); setSelHerramienta(null); }}
              token={token!}
              cargando={false}
            />
          </div>
        </div>
      )}
    </div>
  );
}
