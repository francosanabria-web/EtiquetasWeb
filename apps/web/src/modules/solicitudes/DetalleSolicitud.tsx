import { useEffect, useState } from "react";
import type { Rol } from "../../config/navegacion";
import {
  actualizarSolicitud,
  eliminarSolicitud,
  labelEstado,
  labelTipo,
  urlArchivo,
  urlExcel,
  urlPdf,
  type CatalogosSolicitudes,
  type Solicitud,
} from "../../api/solicitudesClient";

type Props = {
  solicitud: Solicitud;
  catalogos: CatalogosSolicitudes;
  rol: Rol;
  puedeEscribir: boolean;
  onActualizada: (s: Solicitud) => void;
  onEliminada: (id: number) => void;
  onCerrar: () => void;
};

export default function DetalleSolicitud({
  solicitud,
  catalogos,
  rol,
  puedeEscribir,
  onActualizada,
  onEliminada,
  onCerrar,
}: Props) {
  const [estado, setEstado] = useState(solicitud.estado);
  const [nPedido, setNPedido] = useState(solicitud.n_pedido);
  const [proveedor, setProveedor] = useState(solicitud.proveedor ?? "");
  const [remitoNro, setRemitoNro] = useState(solicitud.remito_nro ?? "");
  const [presupuestoNro, setPresupuestoNro] = useState(solicitud.presupuesto_nro ?? "");
  const [guardando, setGuardando] = useState(false);
  const [borrando, setBorrando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const esAdmin = rol === "admin";
  const esAdminOPanol = rol === "admin" || rol === "panol";
  const esTr = solicitud.tipo === "tr";

  useEffect(() => {
    setEstado(solicitud.estado);
    setNPedido(solicitud.n_pedido);
    setProveedor(solicitud.proveedor ?? "");
    setRemitoNro(solicitud.remito_nro ?? "");
    setPresupuestoNro(solicitud.presupuesto_nro ?? "");
  }, [solicitud]);

  const guardar = async () => {
    if (!puedeEscribir) return;
    if (esTr && !proveedor.trim()) {
      setError("En un TR el proveedor es obligatorio.");
      return;
    }
    setGuardando(true);
    setError(null);
    try {
      const payload: Record<string, string> = {
        estado: String(estado),
        proveedor: proveedor.trim(),
        remito_nro: remitoNro.trim(),
        presupuesto_nro: presupuestoNro.trim(),
        rol,
      };
      if (esAdminOPanol) payload.n_pedido = nPedido;
      const s = await actualizarSolicitud(solicitud.id, payload);
      onActualizada(s);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo actualizar.");
    } finally {
      setGuardando(false);
    }
  };

  const borrar = async () => {
    if (!esAdmin) return;
    const ok = window.confirm(
      `¿Borrar el pedido #${solicitud.id}${solicitud.n_tr ? ` (${solicitud.n_tr})` : ""}? Esta acción no se puede deshacer.`,
    );
    if (!ok) return;
    setBorrando(true);
    setError(null);
    try {
      await eliminarSolicitud(solicitud.id, "admin");
      onEliminada(solicitud.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo borrar.");
    } finally {
      setBorrando(false);
    }
  };

  const items = solicitud.items ?? [];

  return (
    <aside className="sol-detalle" aria-label="Detalle de solicitud">
      <div className="sol-detalle-head">
        <h2>
          {solicitud.tipo === "tr"
            ? solicitud.n_tr || `TR #${solicitud.id}`
            : solicitud.n_pedido || `Pedido #${solicitud.id}`}
        </h2>
        <button type="button" className="btn-ghost btn-sm" onClick={onCerrar}>
          Cerrar
        </button>
      </div>

      {error && (
        <p className="error" role="status">
          {error}
        </p>
      )}

      <dl className="sol-dl">
        <div>
          <dt>Tipo</dt>
          <dd>{labelTipo(solicitud.tipo, catalogos.tipos)}</dd>
        </div>
        <div>
          <dt>Cuenta contable</dt>
          <dd>{solicitud.cuenta_contable}</dd>
        </div>
        <div>
          <dt>Solicitante</dt>
          <dd>{solicitud.solicitante}</dd>
        </div>
        {solicitud.proveedor ? (
          <div>
            <dt>Proveedor</dt>
            <dd>{solicitud.proveedor}</dd>
          </div>
        ) : null}
        {solicitud.n_tr ? (
          <div>
            <dt>Nº TR</dt>
            <dd>{solicitud.n_tr}</dd>
          </div>
        ) : null}
        {solicitud.remito_nro || solicitud.remito_archivo ? (
          <div>
            <dt>Remito</dt>
            <dd>
              {solicitud.remito_nro || "—"}
              {solicitud.remito_archivo ? (
                <>
                  {" · "}
                  <a href={urlArchivo(solicitud.remito_archivo)} target="_blank" rel="noreferrer">
                    archivo
                  </a>
                </>
              ) : null}
            </dd>
          </div>
        ) : null}
        {solicitud.presupuesto_nro || solicitud.presupuesto_archivo ? (
          <div>
            <dt>Presupuesto</dt>
            <dd>
              {solicitud.presupuesto_nro || "—"}
              {solicitud.presupuesto_archivo ? (
                <>
                  {" · "}
                  <a
                    href={urlArchivo(solicitud.presupuesto_archivo)}
                    target="_blank"
                    rel="noreferrer"
                  >
                    archivo
                  </a>
                </>
              ) : null}
            </dd>
          </div>
        ) : null}
        {solicitud.notas ? (
          <div>
            <dt>Notas</dt>
            <dd>{solicitud.notas}</dd>
          </div>
        ) : null}
      </dl>

      <div className="sol-detalle-items">
        <h3>Ítems ({items.length})</h3>
        <ul>
          {items.map((it, idx) => (
            <li key={it.id ?? idx}>
              <strong>{it.codigo || "Sin código"}</strong>
              <span>{it.descripcion}</span>
              <span>
                {it.cantidad}
                {it.unidad ? ` ${it.unidad}` : ""} · {it.area || "—"}
              </span>
              {it.imagen_path ? (
                <a href={urlArchivo(it.imagen_path)} target="_blank" rel="noreferrer">
                  Imagen
                </a>
              ) : null}
            </li>
          ))}
        </ul>
      </div>

      {puedeEscribir ? (
        <div className="sol-detalle-edit">
          <label>
            Estado
            <select value={estado} onChange={(e) => setEstado(e.target.value)}>
              {catalogos.estados.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Proveedor {esTr ? "*" : ""}
            <input
              list="sol-proveedores-detalle"
              value={proveedor}
              onChange={(e) => setProveedor(e.target.value)}
              placeholder="Ej. ACME S.A."
            />
          </label>
          <datalist id="sol-proveedores-detalle">
            {catalogos.proveedores.map((p) => (
              <option key={p} value={p} />
            ))}
          </datalist>
          <div className="sol-grid-2">
            <label>
              Nº remito
              <input value={remitoNro} onChange={(e) => setRemitoNro(e.target.value)} />
            </label>
            <label>
              Nº presupuesto
              <input value={presupuestoNro} onChange={(e) => setPresupuestoNro(e.target.value)} />
            </label>
          </div>
          {esAdminOPanol && (
            <label>
              Nº pedido
              <input value={nPedido} onChange={(e) => setNPedido(e.target.value)} />
            </label>
          )}
          <button
            type="button"
            className="btn-primary btn-sm"
            disabled={guardando}
            onClick={() => void guardar()}
          >
            {guardando ? "Guardando…" : "Guardar cambios"}
          </button>
        </div>
      ) : (
        <p className="sol-hint">
          Estado: <strong>{labelEstado(solicitud.estado, catalogos.estados)}</strong>
        </p>
      )}

      <div className="sol-detalle-export">
        <a className="btn-primary sol-pdf-btn" href={urlPdf(solicitud.id)} target="_blank" rel="noreferrer">
          Descargar PDF
        </a>
        <a className="btn-ghost sol-pdf-btn" href={urlExcel(solicitud.id)} target="_blank" rel="noreferrer">
          Descargar Excel
        </a>
      </div>

      {esAdmin && (
        <button
          type="button"
          className="btn-ghost sol-borrar"
          disabled={borrando}
          onClick={() => void borrar()}
        >
          {borrando ? "Borrando…" : "Borrar pedido"}
        </button>
      )}
    </aside>
  );
}
