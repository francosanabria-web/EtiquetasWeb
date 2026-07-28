import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "../../auth/AuthContext";
import { PERMISOS_ROL } from "../../config/usuarios_permisos";
import {
  fetchCatalogos,
  fetchResumen,
  fetchSolicitudes,
  labelEstado,
  labelTipo,
  type CatalogosSolicitudes,
  type ResumenSolicitudes,
  type Solicitud,
  type SolicitudTipo,
} from "../../api/solicitudesClient";
import FormCrearSolicitud from "./FormCrearSolicitud";
import DetalleSolicitud from "./DetalleSolicitud";

type TabId = "pedidos" | "tr";

function fmtFecha(iso: string): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("es-AR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export default function SolicitudesPage() {
  const { usuario } = useAuth();
  const rol = usuario?.rol ?? "jefatura";
  const permiso = PERMISOS_ROL[rol].solicitudes;
  const puedeEscribir = permiso === "escritura";
  const puedeCrear = puedeEscribir && rol !== "jefatura";

  const [tab, setTab] = useState<TabId>("pedidos");
  const [catalogos, setCatalogos] = useState<CatalogosSolicitudes | null>(null);
  const [resumen, setResumen] = useState<ResumenSolicitudes | null>(null);
  const [lista, setLista] = useState<Solicitud[]>([]);
  const [q, setQ] = useState("");
  const [estadoFiltro, setEstadoFiltro] = useState("");
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mostrarCrear, setMostrarCrear] = useState(false);
  const [seleccionada, setSeleccionada] = useState<Solicitud | null>(null);

  const cargar = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      const tipoApi = tab === "tr" ? "tr" : "pedidos";
      const [cats, res, sols] = await Promise.all([
        fetchCatalogos(),
        fetchResumen(),
        fetchSolicitudes({
          tipo: tipoApi,
          estado: estadoFiltro || undefined,
          q: q.trim() || undefined,
          limite: 300,
        }),
      ]);
      setCatalogos(cats);
      setResumen(res);
      setLista(sols);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo cargar.");
    } finally {
      setCargando(false);
    }
  }, [tab, estadoFiltro, q]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  const tipoCrear: SolicitudTipo = tab === "tr" ? "tr" : "normal";

  const contadores = useMemo(() => {
    if (!resumen) return [];
    return [
      { label: "Total", value: resumen.total },
      { label: "Urgentes", value: resumen.urgentes_activos },
      { label: "TR activos", value: resumen.tr_activos },
      { label: "En proceso", value: resumen.por_estado.en_proceso ?? 0 },
      { label: "Parcial", value: resumen.por_estado.parcial ?? 0 },
      { label: "Cumplidos", value: resumen.por_estado.cumplido ?? 0 },
    ];
  }, [resumen]);

  return (
    <div className="sol-page">
      <header className="page-header sol-header">
        <div>
          <h1>Solicitud de pedidos</h1>
          <p className="sub">
            Un pedido puede incluir varios ítems. Se guarda en el Excel compartido de Drive; descarga
            en PDF o Excel.
          </p>
        </div>
        {puedeCrear && (
          <button type="button" className="btn-primary" onClick={() => setMostrarCrear(true)}>
            + Crear solicitud
          </button>
        )}
      </header>

      {error && (
        <p className="error" role="status">
          {error}
        </p>
      )}

      <div className="sol-kpis">
        {contadores.map((c) => (
          <div key={c.label} className="sol-kpi">
            <span className="sol-kpi-val">{c.value}</span>
            <span className="sol-kpi-label">{c.label}</span>
          </div>
        ))}
      </div>

      <div className="sol-tabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={tab === "pedidos"}
          className={`sol-tab${tab === "pedidos" ? " active" : ""}`}
          onClick={() => {
            setTab("pedidos");
            setSeleccionada(null);
          }}
        >
          Pedidos (Normal / Urgente)
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "tr"}
          className={`sol-tab${tab === "tr" ? " active" : ""}`}
          onClick={() => {
            setTab("tr");
            setSeleccionada(null);
          }}
        >
          TR
        </button>
      </div>

      <div className="sol-toolbar">
        <input
          className="sol-search"
          type="search"
          placeholder="Buscar pedido, TR, código, descripción, área, solicitante…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <select
          value={estadoFiltro}
          onChange={(e) => setEstadoFiltro(e.target.value)}
          aria-label="Filtrar por estado"
        >
          <option value="">Todos los estados</option>
          {(catalogos?.estados ?? []).map((e) => (
            <option key={e.id} value={e.id}>
              {e.label}
            </option>
          ))}
        </select>
        <button type="button" className="btn-ghost btn-sm" onClick={() => void cargar()}>
          Actualizar
        </button>
      </div>

      <div className={`sol-layout${seleccionada ? " con-detalle" : ""}`}>
        <div className="sol-table-wrap">
          {cargando ? (
            <p className="sol-hint">Cargando…</p>
          ) : lista.length === 0 ? (
            <p className="sol-hint">No hay solicitudes en esta vista.</p>
          ) : (
            <table className="sol-table">
              {tab === "tr" ? (
                <>
                  <thead>
                    <tr>
                      <th>Nº TR</th>
                      <th>Descripción</th>
                      <th>Máquina / línea</th>
                      <th>Cantidad</th>
                      <th>Proveedor</th>
                      <th>Nº presup.</th>
                      <th>Nº remito</th>
                      <th>Estado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {lista.map((s) => {
                      const it = s.items?.[0];
                      const extra =
                        (s.items_count ?? s.items?.length ?? 0) > 1
                          ? ` (+${(s.items_count ?? s.items.length) - 1})`
                          : "";
                      return (
                        <tr
                          key={s.id}
                          className={seleccionada?.id === s.id ? "selected" : ""}
                          onClick={() => setSeleccionada(s)}
                        >
                          <td>{s.n_tr || `#${s.id}`}</td>
                          <td className="sol-desc">
                            {(it?.descripcion || s.preview || "—") + extra}
                          </td>
                          <td className="sol-desc">{it?.area || s.areas_resumen || "—"}</td>
                          <td>
                            {it ? `${it.cantidad}${it.unidad ? ` ${it.unidad}` : ""}` : "—"}
                          </td>
                          <td>{s.proveedor || "—"}</td>
                          <td>{s.presupuesto_nro || "—"}</td>
                          <td>{s.remito_nro || "—"}</td>
                          <td>
                            <span className={`sol-estado sol-estado-${s.estado}`}>
                              {labelEstado(s.estado, catalogos?.estados)}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </>
              ) : (
                <>
                  <thead>
                    <tr>
                      <th>ID / Pedido</th>
                      <th>Tipo</th>
                      <th>Ítems</th>
                      <th>Resumen</th>
                      <th>Áreas</th>
                      <th>Solicitante</th>
                      <th>Estado</th>
                      <th>Fecha</th>
                    </tr>
                  </thead>
                  <tbody>
                    {lista.map((s) => (
                      <tr
                        key={s.id}
                        className={seleccionada?.id === s.id ? "selected" : ""}
                        onClick={() => setSeleccionada(s)}
                      >
                        <td>{s.n_pedido || `#${s.id}`}</td>
                        <td>
                          <span className={`sol-badge sol-badge-${s.tipo}`}>
                            {labelTipo(s.tipo, catalogos?.tipos)}
                          </span>
                        </td>
                        <td>{s.items_count ?? s.items?.length ?? 0}</td>
                        <td className="sol-desc">{s.preview || "—"}</td>
                        <td className="sol-desc">{s.areas_resumen || "—"}</td>
                        <td>{s.solicitante}</td>
                        <td>
                          <span className={`sol-estado sol-estado-${s.estado}`}>
                            {labelEstado(s.estado, catalogos?.estados)}
                          </span>
                        </td>
                        <td>{fmtFecha(s.creado_en)}</td>
                      </tr>
                    ))}
                  </tbody>
                </>
              )}
            </table>
          )}
        </div>

        {seleccionada && catalogos && (
          <DetalleSolicitud
            solicitud={seleccionada}
            catalogos={catalogos}
            rol={rol}
            puedeEscribir={puedeEscribir}
            onActualizada={(s) => {
              setSeleccionada(s);
              setLista((prev) => prev.map((x) => (x.id === s.id ? s : x)));
              void fetchResumen().then(setResumen);
            }}
            onEliminada={(id) => {
              setSeleccionada(null);
              setLista((prev) => prev.filter((x) => x.id !== id));
              void fetchResumen().then(setResumen);
            }}
            onCerrar={() => setSeleccionada(null)}
          />
        )}
      </div>

      {mostrarCrear && catalogos && puedeCrear && (
        <div className="sol-modal-backdrop" role="dialog" aria-modal="true">
          <div className="sol-modal sol-modal-wide">
            <FormCrearSolicitud
              catalogos={catalogos}
              rol={rol}
              creadoPor={usuario?.email ?? ""}
              tipoInicial={tipoCrear}
              onCancelar={() => setMostrarCrear(false)}
              onCreada={(s) => {
                setMostrarCrear(false);
                setSeleccionada(s);
                if ((tab === "tr") !== (s.tipo === "tr")) {
                  setTab(s.tipo === "tr" ? "tr" : "pedidos");
                }
                void cargar();
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
