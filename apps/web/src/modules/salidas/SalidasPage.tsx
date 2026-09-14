import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useAuth } from "../../auth/AuthContext";
import { permisoDe } from "../../config/navegacion";
import {
  confirmarDevolucion,
  confirmarSalida,
  fetchArticulo,
  fetchCatalogosSalidas,
  fmtNum,
  fmtPesos,
  hoyIsoLocal,
  operariosParaSector,
  proyectarStock,
  type ArticuloSalida,
  type CatalogosSalidas,
  type ItemPendiente,
  type ProyeccionStock,
} from "../../api/salidasClient";
import "../../styles/salidas.css";

function nuevoId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export default function SalidasPage() {
  const { usuario } = useAuth();
  const puedeEscribir = permisoDe(usuario, "salidas") === "escritura";

  const [cats, setCats] = useState<CatalogosSalidas | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [okMsg, setOkMsg] = useState<string | null>(null);
  const [cargandoCats, setCargandoCats] = useState(true);
  const [buscando, setBuscando] = useState(false);
  const [finalizando, setFinalizando] = useState(false);

  const [modoDevolucion, setModoDevolucion] = useState(false);
  const [fecha, setFecha] = useState(hoyIsoLocal());
  const [codigo, setCodigo] = useState("");
  const [articulo, setArticulo] = useState<ArticuloSalida | null>(null);
  const [cantidad, setCantidad] = useState("");
  const [tipo, setTipo] = useState("");
  const [orden, setOrden] = useState("");
  const [maquina, setMaquina] = useState("");
  const [sector, setSector] = useState("");
  const [operario, setOperario] = useState("");
  const [ordenBloqueada, setOrdenBloqueada] = useState(false);
  const [pendientes, setPendientes] = useState<ItemPendiente[]>([]);
  const [proyeccion, setProyeccion] = useState<ProyeccionStock | null>(null);
  const [proyError, setProyError] = useState<string | null>(null);

  useEffect(() => {
    let cancel = false;
    (async () => {
      setCargandoCats(true);
      setError(null);
      try {
        const c = await fetchCatalogosSalidas();
        if (cancel) return;
        setCats(c);
      } catch (e) {
        if (!cancel) setError(e instanceof Error ? e.message : "No se pudieron cargar catálogos.");
      } finally {
        if (!cancel) setCargandoCats(false);
      }
    })();
    return () => {
      cancel = true;
    };
  }, []);

  const operarios = useMemo(() => operariosParaSector(cats, sector), [cats, sector]);

  useEffect(() => {
    if (!operarios.length) {
      setOperario("");
      return;
    }
    if (operario && !operarios.includes(operario)) {
      setOperario("");
    }
  }, [operarios, operario]);

  const totalCarga = useMemo(
    () => pendientes.reduce((acc, p) => acc + (p.es_devolucion ? -Math.abs(p.monto) : Math.abs(p.monto)), 0),
    [pendientes],
  );

  /** Aviso en pantalla: stock proyectado al tener código + cantidad. */
  useEffect(() => {
    const cod = (articulo?.codigo || codigo).trim().toUpperCase();
    const cantNum = Number(String(cantidad).replace(",", "."));
    if (!cod || !articulo || articulo.codigo !== cod || !Number.isFinite(cantNum) || cantNum === 0) {
      setProyeccion(null);
      setProyError(null);
      return;
    }
    const esDev = modoDevolucion || cantNum < 0;
    const cantSigned = esDev ? -Math.abs(cantNum) : Math.abs(cantNum);
    let cancel = false;
    const t = window.setTimeout(() => {
      void (async () => {
        try {
          const proy = await proyectarStock({
            codigo: articulo.codigo,
            cantidad: cantSigned,
            es_devolucion: esDev,
            pendientes: pendientes.map((p) => ({ codigo: p.codigo, cantidad: p.cantidad })),
          });
          if (!cancel) {
            setProyeccion(proy);
            setProyError(null);
          }
        } catch (e) {
          if (!cancel) {
            setProyeccion(null);
            setProyError(e instanceof Error ? e.message : "No se pudo calcular el stock proyectado.");
          }
        }
      })();
    }, 280);
    return () => {
      cancel = true;
      window.clearTimeout(t);
    };
  }, [articulo, codigo, cantidad, modoDevolucion, pendientes]);

  function resetFormularioParaSiguienteOrden() {
    setPendientes([]);
    setOrdenBloqueada(false);
    setCodigo("");
    setArticulo(null);
    setCantidad("");
    setOrden("");
    setMaquina("");
    setTipo("");
    setSector("");
    setOperario("");
    setModoDevolucion(false);
    setProyeccion(null);
    setProyError(null);
    setFecha(hoyIsoLocal());
  }

  async function onBuscarCodigo() {
    const cod = codigo.trim().toUpperCase();
    if (!cod) return;
    setBuscando(true);
    setError(null);
    setOkMsg(null);
    try {
      const art = await fetchArticulo(cod);
      setArticulo(art);
      setCodigo(art.codigo);
    } catch (e) {
      setArticulo(null);
      setError(e instanceof Error ? e.message : "No se encontró el código.");
    } finally {
      setBuscando(false);
    }
  }

  async function onAgregar(e: FormEvent) {
    e.preventDefault();
    if (!puedeEscribir) return;
    setError(null);
    setOkMsg(null);
    const cod = (articulo?.codigo || codigo).trim().toUpperCase();
    if (!cod) {
      setError("Ingresá un código.");
      return;
    }
    let art = articulo;
    if (!art || art.codigo !== cod) {
      try {
        art = await fetchArticulo(cod);
        setArticulo(art);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Código no encontrado.");
        return;
      }
    }
    const cantNum = Number(String(cantidad).replace(",", "."));
    if (!Number.isFinite(cantNum) || cantNum === 0) {
      setError("Cantidad inválida.");
      return;
    }
    if (!tipo || !String(orden).trim() || !sector || !operario) {
      setError("Completá comprobante, N° orden, sector y operario.");
      return;
    }

    const esDev = modoDevolucion || cantNum < 0;
    const cantSigned = esDev ? -Math.abs(cantNum) : Math.abs(cantNum);

    try {
      // Refresca proyección (aviso inline); no bloquea con popup si queda negativo.
      const proy = await proyectarStock({
        codigo: art.codigo,
        cantidad: cantSigned,
        es_devolucion: esDev,
        pendientes: pendientes.map((p) => ({ codigo: p.codigo, cantidad: p.cantidad })),
      });
      setProyeccion(proy);

      const monto = Math.round(Math.abs(cantSigned) * Math.abs(art.precio_unitario) * 100) / 100;
      const item: ItemPendiente = {
        id: nuevoId(),
        fecha,
        codigo: art.codigo,
        descripcion: (esDev ? "(DEVOLUCIÓN) " : "") + art.descripcion,
        ubicacion: art.ubicacion,
        cantidad: cantSigned,
        tipo_comprobante: tipo,
        numero_orden: orden,
        maquina: maquina.trim().toUpperCase(),
        precio_unitario: art.precio_unitario,
        monto,
        operario: operario.toUpperCase(),
        sector: sector.toUpperCase(),
        es_devolucion: esDev,
      };
      setPendientes((prev) => [...prev, item]);
      setCantidad("");
      setCodigo("");
      setArticulo(null);
      setProyeccion(null);
      setProyError(null);
      setOrdenBloqueada(true);
      setOkMsg(`Agregado a la carga: ${item.codigo}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo agregar.");
    }
  }

  function quitarPendiente(id: string) {
    setPendientes((prev) => prev.filter((p) => p.id !== id));
  }

  function limpiarCarga() {
    if (pendientes.length && !window.confirm("¿Borrar la carga pendiente no guardada?")) return;
    resetFormularioParaSiguienteOrden();
    setOkMsg(null);
    setError(null);
  }

  async function finalizar() {
    if (!pendientes.length || !puedeEscribir) return;
    if (!window.confirm(`¿Confirmar ${pendientes.length} ítem(s) y grabar?`)) return;
    setFinalizando(true);
    setError(null);
    setOkMsg(null);
    // Como en escritorio: permite stock negativo sin diálogo técnico.
    const items = pendientes.map((p) => ({
      fecha: p.fecha,
      codigo: p.codigo,
      cantidad: p.cantidad,
      tipo_comprobante: p.tipo_comprobante,
      numero_orden: p.numero_orden,
      maquina: p.maquina,
      sector: p.sector,
      operario: p.operario,
      precio_unitario: p.precio_unitario,
      permitir_stock_negativo: true,
    }));
    try {
      const hayDev = pendientes.every((p) => p.es_devolucion);
      const res = hayDev
        ? await confirmarDevolucion({ items })
        : await confirmarSalida({ items, forzar_negativos: true });
      setOkMsg(`${res.mensaje} · ${res.movimientos} movimiento(s) en salidas_web.`);
      resetFormularioParaSiguienteOrden();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "No se pudo finalizar.";
      // Sin jerga de API en pantalla
      const limpio = msg
        .replace(/forzar_negativos\s*=\s*true/gi, "")
        .replace(/permitir_stock_negativo/gi, "")
        .replace(/\s{2,}/g, " ")
        .trim();
      setError(limpio || "No se pudo finalizar la carga.");
    } finally {
      setFinalizando(false);
    }
  }

  return (
    <div className="page-content sal-page">
      <header className="page-header sal-header">
        <div>
          <h1>Salidas</h1>
          <p className="sub">
            Egreso de material del pañol (no confundir con Activos fuera de planta). Escritura en
            salidas_web; el maestro de producción es solo lectura.
          </p>
        </div>
        <div className="sal-header-actions">
          <label className="sal-toggle" htmlFor="sal-modo-devolucion">
            <input
              id="sal-modo-devolucion"
              type="checkbox"
              checked={modoDevolucion}
              onChange={(e) => setModoDevolucion(e.target.checked)}
              disabled={!puedeEscribir}
            />
            Devolución (cantidad negativa)
          </label>
        </div>
      </header>

      {error && (
        <p className="error" role="status">
          {error}
        </p>
      )}
      {okMsg && (
        <p className="sal-ok" role="status">
          {okMsg}
        </p>
      )}
      {cargandoCats && <p className="sub">Cargando catálogos…</p>}

      <div className="sal-grid">
        <form className="sal-form" onSubmit={(e) => void onAgregar(e)}>
          <fieldset disabled={!puedeEscribir || finalizando}>
            <legend>Registro de movimiento</legend>

            <div className="sal-field">
              <input
                id="sal-fecha"
                type="date"
                value={fecha}
                onChange={(e) => setFecha(e.target.value)}
                disabled={ordenBloqueada}
                required
                aria-label="Fecha"
              />
            </div>

            <div className="sal-row">
              <div className="sal-field sal-grow">
                <input
                  id="sal-codigo"
                  value={codigo}
                  onChange={(e) => {
                    setCodigo(e.target.value.toUpperCase());
                    setArticulo(null);
                    setProyeccion(null);
                  }}
                  onKeyDown={(ev) => {
                    if (ev.key === "Enter") {
                      ev.preventDefault();
                      void onBuscarCodigo();
                    }
                  }}
                  placeholder="Ingrese el código"
                  autoComplete="off"
                  aria-label="Código"
                />
              </div>
              <button type="button" className="btn-secondary" onClick={() => void onBuscarCodigo()} disabled={buscando}>
                {buscando ? "…" : "Buscar"}
              </button>
            </div>

            <div className="sal-readonly" aria-live="polite">
              <div>
                <span className="sal-muted">Descripción</span>
                <strong>{articulo?.descripcion || "—"}</strong>
              </div>
              <div>
                <span className="sal-muted">Ubicación</span>
                <strong>{articulo?.ubicacion || "—"}</strong>
              </div>
              <div>
                <span className="sal-muted">Stock</span>
                <strong>{articulo ? fmtNum(articulo.stock_actual) : "—"}</strong>
              </div>
              <div>
                <span className="sal-muted">P. unit.</span>
                <strong>{articulo ? fmtPesos(articulo.precio_unitario) : "—"}</strong>
              </div>
            </div>

            <div className="sal-field">
              <input
                id="sal-cantidad"
                value={cantidad}
                onChange={(e) => setCantidad(e.target.value)}
                inputMode="decimal"
                required
                placeholder="Ingrese la cantidad"
                aria-label="Cantidad"
              />
            </div>

            {(proyeccion || proyError) && (
              <p
                className={`sal-proy${proyeccion?.alerta_negativo || proyError ? " sal-proy-warn" : ""}`}
                role="status"
                aria-live="polite"
              >
                {proyError
                  ? proyError
                  : proyeccion?.alerta_negativo
                    ? `Stock proyectado: ${fmtNum(proyeccion.stock_proyectado)} (quedaría en negativo). Se permitirá al confirmar, como en escritorio.`
                    : `Stock proyectado: ${fmtNum(proyeccion!.stock_proyectado)}`}
              </p>
            )}

            <div className="sal-field">
              <select
                id="sal-comprobante"
                value={tipo}
                onChange={(e) => setTipo(e.target.value)}
                disabled={ordenBloqueada}
                required
                aria-label="Comprobante"
              >
                <option value="" disabled>
                  Seleccione comprobante…
                </option>
                {(cats?.tipos_comprobante || []).map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>

            <div className="sal-field">
              <input
                id="sal-orden"
                value={orden}
                onChange={(e) => setOrden(e.target.value)}
                disabled={ordenBloqueada}
                required
                placeholder="Ingrese el N° de orden"
                aria-label="Número de orden"
              />
            </div>

            <div className="sal-field">
              <input
                id="sal-maquina"
                value={maquina}
                onChange={(e) => setMaquina(e.target.value.toUpperCase())}
                disabled={ordenBloqueada}
                placeholder="Ingrese máquina o sitio"
                aria-label="Máquina o sitio"
              />
            </div>

            <div className="sal-field">
              <select
                id="sal-sector"
                value={sector}
                onChange={(e) => setSector(e.target.value)}
                disabled={ordenBloqueada}
                required
                aria-label="Sector"
              >
                <option value="" disabled>
                  Seleccione sector…
                </option>
                {(cats?.sectores || []).map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>

            <div className="sal-field">
              <select
                id="sal-operario"
                value={operario}
                onChange={(e) => setOperario(e.target.value)}
                required
                aria-label="Operario"
                disabled={!sector}
              >
                <option value="" disabled>
                  {sector ? "Seleccione operario…" : "Seleccione sector primero…"}
                </option>
                {operarios.map((o) => (
                  <option key={o} value={o}>
                    {o}
                  </option>
                ))}
              </select>
            </div>

            <div className="sal-form-actions">
              <button type="submit" className="btn-primary">
                {modoDevolucion ? "Agregar devolución" : "Agregar a carga"}
              </button>
              {ordenBloqueada && (
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setOrdenBloqueada(false)}
                >
                  Cambiar orden / cabecera
                </button>
              )}
            </div>
          </fieldset>
        </form>

        <section className="sal-carga">
          <div className="sal-carga-head">
            <h2>Carga pendiente</h2>
            <p className="sub">
              {pendientes.length} ítem(s) · Total {fmtPesos(totalCarga)}
            </p>
          </div>

          {pendientes.length === 0 ? (
            <p className="sal-empty">Sin ítems. Buscá un código y agregalo a la carga.</p>
          ) : (
            <>
              <div className="sal-table-wrap sal-table-desktop">
                <table className="sal-table">
                  <thead>
                    <tr>
                      <th>Código</th>
                      <th>Descripción</th>
                      <th>Cant.</th>
                      <th>P. unit.</th>
                      <th>Monto</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {pendientes.map((p) => (
                      <tr key={p.id} className={p.es_devolucion ? "sal-row-dev" : undefined}>
                        <td>{p.codigo}</td>
                        <td>{p.descripcion}</td>
                        <td className="sal-num">{fmtNum(p.cantidad)}</td>
                        <td className="sal-num">{fmtPesos(p.precio_unitario)}</td>
                        <td className="sal-num">{fmtPesos(p.es_devolucion ? -p.monto : p.monto)}</td>
                        <td>
                          <button
                            type="button"
                            className="sal-link-btn"
                            onClick={() => quitarPendiente(p.id)}
                            disabled={!puedeEscribir || finalizando}
                          >
                            Quitar
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <ul className="sal-cards-mobile">
                {pendientes.map((p) => (
                  <li
                    key={`m-${p.id}`}
                    className={`sal-card-item${p.es_devolucion ? " sal-row-dev" : ""}`}
                  >
                    <div className="sal-card-top">
                      <strong>{p.codigo}</strong>
                      <button
                        type="button"
                        className="sal-link-btn"
                        onClick={() => quitarPendiente(p.id)}
                        disabled={!puedeEscribir || finalizando}
                      >
                        Quitar
                      </button>
                    </div>
                    <p className="sal-card-desc">{p.descripcion}</p>
                    <div className="sal-card-meta">
                      <span>
                        Cant. <b className="sal-num">{fmtNum(p.cantidad)}</b>
                      </span>
                      <span>
                        Monto{" "}
                        <b className="sal-num">
                          {fmtPesos(p.es_devolucion ? -p.monto : p.monto)}
                        </b>
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            </>
          )}

          <div className="sal-carga-actions">
            <button
              type="button"
              className="btn-primary"
              disabled={!puedeEscribir || !pendientes.length || finalizando}
              onClick={() => void finalizar()}
            >
              {finalizando ? "Guardando…" : "Finalizar carga"}
            </button>
            <button
              type="button"
              className="btn-secondary"
              disabled={!pendientes.length || finalizando}
              onClick={limpiarCarga}
            >
              Limpiar
            </button>
          </div>
          {!puedeEscribir && (
            <p className="sub">Tu usuario tiene solo lectura en Salidas.</p>
          )}
        </section>
      </div>
    </div>
  );
}
