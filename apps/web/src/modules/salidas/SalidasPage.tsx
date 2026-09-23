import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useAuth } from "../../auth/AuthContext";
import { permisoDe } from "../../config/navegacion";
import {
  anularMovimiento,
  confirmarSalida,
  editarMovimiento,
  exportarDiario,
  exportarRemito,
  fetchArticulo,
  fetchCatalogosSalidas,
  fetchSalidasHealth,
  fmtNum,
  fmtPesos,
  getAuditoria,
  hoyIsoLocal,
  listarAtenciones,
  listarMovimientos,
  operariosParaSector,
  proyectarStock,
  type ArticuloSalida,
  type AuditoriaRow,
  type CatalogosSalidas,
  type ItemPendiente,
  type MovimientoRow,
  type ProyeccionStock,
} from "../../api/salidasClient";
import "../../styles/salidas.css";
import AtencionModal from "./AtencionModal";
import MaestroStockModal from "./MaestroStockModal";
import PrintRemito from "./PrintRemito";

function nuevoId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

/* ────────────────────────────── Modales v5 ────────────────────────────── */

function AnularModal({
  open,
  row,
  onClose,
  onAnulado,
}: {
  open: boolean;
  row: MovimientoRow | null;
  onClose: () => void;
  onAnulado: () => void;
}) {
  const [motivo, setMotivo] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setMotivo("");
      setErr(null);
      setSaving(false);
    }
  }, [open, row]);

  if (!open || !row) return null;
  const valido = motivo.trim().length >= 3 && motivo.trim().length <= 500;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!valido || !row?.id) return;
    setSaving(true);
    setErr(null);
    try {
      await anularMovimiento(row.id, motivo.trim());
      onAnulado();
      onClose();
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "No se pudo anular.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div role="dialog" aria-modal="true" aria-label="Anular movimiento" style={{ position: "fixed", inset: 0, zIndex: 60, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div onClick={onClose} style={{ position: "absolute", inset: 0, background: "rgba(0,0,0,0.42)" }} />
      <form onSubmit={(e) => void handleSubmit(e)} style={{ position: "relative", background: "var(--surface, #fff)", borderRadius: 12, padding: 20, minWidth: 380, maxWidth: 520, width: "90%", boxShadow: "0 12px 32px rgba(0,0,0,0.2)", display: "flex", flexDirection: "column", gap: 12 }}>
        <h3 style={{ margin: 0, fontSize: "1.05rem" }}>Anular baja</h3>
        <div style={{ fontSize: "0.85rem", lineHeight: 1.5, background: "#fef2f2", border: "0.5px solid #fecaca", borderRadius: 8, padding: "10px 12px" }}>
          <div><b>Código:</b> {row.CODIGO} · <b>Cant:</b> {fmtNum(Number(row.CANTIDAD) || 0)} · <b>Monto:</b> {fmtPesos(Number(row.MONTO_TOTAL_SALIDA) || 0)}</div>
          <div><b>Orden:</b> {row.NUMERO_ORDEN || "—"} · <b>Sector:</b> {row.SECTOR || "—"} · <b>Operario:</b> {row.OPERARIO || "—"}</div>
          <div><b>Fecha:</b> {String(row.FECHA)} · <b>Tipo:</b> {row.TIPO_COMPROBANTE || "—"}</div>
          <p style={{ margin: "8px 0 0", fontSize: "0.78rem", color: "#991b1b" }}>Esta acción es <b>soft-delete auditable</b>: el registro quedará marcado como anulado y no se modificará el stock actual (se corrige en próxima actualización maestro valorizado).</p>
        </div>
        <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span style={{ fontSize: "0.85rem", fontWeight: 600 }}>Motivo obligatorio (3..500) *</span>
          <textarea value={motivo} onChange={(e) => setMotivo(e.target.value)} rows={3} maxLength={500} placeholder="Ej: carga duplicada, error de operario..." required style={{ borderRadius: 8, border: "0.5px solid var(--border)", padding: "8px 10px", fontSize: "0.9rem", resize: "vertical" }} />
          <span style={{ fontSize: "0.75rem", color: valido ? "#16a34a" : "var(--muted)", textAlign: "right" }}>{motivo.trim().length}/500</span>
        </label>
        {err && <p className="error" style={{ margin: 0, fontSize: "0.85rem" }}>{err}</p>}
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button type="button" className="btn-secondary" onClick={onClose} disabled={saving} style={{ minHeight: 36 }}>Cancelar</button>
          <button type="submit" className="btn-primary" disabled={!valido || saving} style={{ minHeight: 36, background: valido ? "#dc2626" : undefined, borderColor: valido ? "#dc2626" : undefined }}>{saving ? "Anulando…" : "Anular movimiento"}</button>
        </div>
      </form>
    </div>
  );
}

function EditarModal({
  open,
  row,
  cats,
  onClose,
  onGuardado,
}: {
  open: boolean;
  row: MovimientoRow | null;
  cats: CatalogosSalidas | null;
  onClose: () => void;
  onGuardado: () => void;
}) {
  const [tipo, setTipo] = useState("");
  const [orden, setOrden] = useState("");
  const [maquina, setMaquina] = useState("");
  const [sector, setSector] = useState("");
  const [operario, setOperario] = useState("");
  const [cantidad, setCantidad] = useState("");
  const [precio, setPrecio] = useState("");
  const [motivo, setMotivo] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const operariosEdit = useMemo(() => operariosParaSector(cats, sector), [cats, sector]);

  useEffect(() => {
    if (open && row) {
      setTipo(String(row.TIPO_COMPROBANTE || ""));
      setOrden(String(row.NUMERO_ORDEN || ""));
      setMaquina(String(row.MAQUINA_SITIO || ""));
      setSector(String(row.SECTOR || ""));
      setOperario(String(row.OPERARIO || ""));
      setCantidad(String(row.CANTIDAD ?? ""));
      setPrecio(row.PRECIO_UNITARIO != null ? String(row.PRECIO_UNITARIO) : "");
      setMotivo("");
      setErr(null);
      setSaving(false);
    }
  }, [open, row]);

  useEffect(() => {
    if (operariosEdit.length && operario && !operariosEdit.includes(operario)) {
      // keep value but hint; don't auto-clear to allow custom operario
    }
  }, [operariosEdit, operario]);

  if (!open || !row) return null;

  function hasChanges(): boolean {
    if (!row) return false;
    const curTipo = String(row.TIPO_COMPROBANTE || "").toUpperCase();
    const curOrden = String(row.NUMERO_ORDEN || "");
    const curMaq = String(row.MAQUINA_SITIO || "").toUpperCase();
    const curSector = String(row.SECTOR || "").toUpperCase();
    const curOper = String(row.OPERARIO || "").toUpperCase();
    const curCant = String(row.CANTIDAD ?? "");
    const curPrec = row.PRECIO_UNITARIO != null ? String(row.PRECIO_UNITARIO) : "";
    return (
      tipo.trim().toUpperCase() !== curTipo ||
      orden.trim() !== curOrden ||
      maquina.trim().toUpperCase() !== curMaq ||
      sector.trim().toUpperCase() !== curSector ||
      operario.trim().toUpperCase() !== curOper ||
      cantidad.trim() !== curCant.trim() ||
      precio.trim() !== curPrec.trim()
    );
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!row?.id) return;
    if (!hasChanges()) {
      setErr("Sin cambios.");
      return;
    }
    setSaving(true);
    setErr(null);
    const payload: Record<string, unknown> = {};
    const curTipo = String(row.TIPO_COMPROBANTE || "").toUpperCase();
    if (tipo.trim().toUpperCase() !== curTipo) payload["tipo_comprobante"] = tipo.trim();
    const curOrden = String(row.NUMERO_ORDEN || "");
    if (orden.trim() !== curOrden) payload["numero_orden"] = orden.trim();
    if (maquina.trim().toUpperCase() !== String(row.MAQUINA_SITIO || "").toUpperCase()) payload["maquina_sitio"] = maquina.trim();
    if (sector.trim().toUpperCase() !== String(row.SECTOR || "").toUpperCase()) payload["sector_nombre"] = sector.trim();
    if (operario.trim().toUpperCase() !== String(row.OPERARIO || "").toUpperCase()) payload["operario_nombre"] = operario.trim();
    if (cantidad.trim() !== String(row.CANTIDAD ?? "").trim()) {
      const cNum = Number(String(cantidad).replace(",", "."));
      if (!Number.isFinite(cNum) || cNum === 0) {
        setErr("Cantidad inválida.");
        setSaving(false);
        return;
      }
      payload["cantidad"] = cNum;
    }
    const curPrec = row.PRECIO_UNITARIO != null ? String(row.PRECIO_UNITARIO) : "";
    if (precio.trim() !== curPrec.trim() && precio.trim() !== "") {
      const pNum = Number(String(precio).replace(",", "."));
      if (!Number.isFinite(pNum) || pNum < 0) {
        setErr("Precio inválido.");
        setSaving(false);
        return;
      }
      payload["precio_unitario"] = pNum;
    } else if (precio.trim() === "" && curPrec !== "") {
      // allow clearing? skip
    }
    if (motivo.trim()) payload["motivo"] = motivo.trim();
    if (Object.keys(payload).length === 0 || (Object.keys(payload).length === 1 && "motivo" in payload)) {
      setErr("Sin cambios relevantes.");
      setSaving(false);
      return;
    }
    try {
      await editarMovimiento(row.id, payload as never);
      onGuardado();
      onClose();
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "No se pudo guardar.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div role="dialog" aria-modal="true" aria-label="Editar movimiento" style={{ position: "fixed", inset: 0, zIndex: 60, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div onClick={onClose} style={{ position: "absolute", inset: 0, background: "rgba(0,0,0,0.42)" }} />
      <form onSubmit={(e) => void handleSubmit(e)} style={{ position: "relative", background: "var(--surface, #fff)", borderRadius: 12, padding: 20, minWidth: 420, maxWidth: 640, width: "94%", maxHeight: "90vh", overflowY: "auto", boxShadow: "0 12px 32px rgba(0,0,0,0.2)", display: "flex", flexDirection: "column", gap: 12 }}>
        <h3 style={{ margin: 0, fontSize: "1.05rem" }}>Editar baja #{row.id} · {row.CODIGO}</h3>
        <p style={{ margin: 0, fontSize: "0.78rem", color: "var(--muted)" }}>Solo campos de tipeo. <b>Código</b> y <b>Fecha</b> no editables. Stock no se revierte (corrección histórica).</p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 10 }}>
          <label className="sal-field">
            <span className="sal-muted">Tipo comprobante</span>
            <select value={tipo} onChange={(e) => setTipo(e.target.value)}>
              <option value="">—</option>
              {(cats?.tipos_comprobante || []).map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </label>
          <label className="sal-field">
            <span className="sal-muted">N° orden</span>
            <input value={orden} onChange={(e) => setOrden(e.target.value)} placeholder="Ej 12345" />
          </label>
          <label className="sal-field">
            <span className="sal-muted">Máquina / sitio</span>
            <input value={maquina} onChange={(e) => setMaquina(e.target.value.toUpperCase())} placeholder="Ej L3" />
          </label>
          <label className="sal-field">
            <span className="sal-muted">Sector</span>
            <select value={sector} onChange={(e) => setSector(e.target.value)}>
              <option value="">—</option>
              {(cats?.sectores || []).map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </label>
          <label className="sal-field">
            <span className="sal-muted">Operario</span>
            <input list="edit-operarios" value={operario} onChange={(e) => setOperario(e.target.value.toUpperCase())} placeholder="Nombre" />
            <datalist id="edit-operarios">
              {operariosEdit.map((o) => (
                <option key={o} value={o} />
              ))}
            </datalist>
          </label>
          <label className="sal-field">
            <span className="sal-muted">Cantidad *</span>
            <input value={cantidad} onChange={(e) => setCantidad(e.target.value)} inputMode="decimal" placeholder="Ej 2" />
          </label>
          <label className="sal-field">
            <span className="sal-muted">Precio unit.</span>
            <input value={precio} onChange={(e) => setPrecio(e.target.value)} inputMode="decimal" placeholder="Editable" />
          </label>
        </div>
        <label className="sal-field">
          <span className="sal-muted">Motivo edición (opcional, audit)</span>
          <input value={motivo} onChange={(e) => setMotivo(e.target.value)} maxLength={500} placeholder="Ej: corrección tipeo sector" />
        </label>
        {err && <p className="error" style={{ margin: 0, fontSize: "0.85rem" }}>{err}</p>}
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button type="button" className="btn-secondary" onClick={onClose} disabled={saving} style={{ minHeight: 36 }}>Cancelar</button>
          <button type="submit" className="btn-primary" disabled={saving || !hasChanges()} style={{ minHeight: 36 }}>{saving ? "Guardando…" : "Guardar"}</button>
        </div>
      </form>
    </div>
  );
}

function AuditoriaModal({
  open,
  row,
  onClose,
}: {
  open: boolean;
  row: MovimientoRow | null;
  onClose: () => void;
}) {
  const [items, setItems] = useState<AuditoriaRow[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !row?.id) return;
    setLoading(true);
    setErr(null);
    setItems(null);
    void (async () => {
      try {
        const res = await getAuditoria(row.id!);
        setItems(res.items);
      } catch (e) {
        setErr(e instanceof Error ? e.message : "No se pudo cargar auditoría.");
      } finally {
        setLoading(false);
      }
    })();
  }, [open, row]);

  if (!open || !row) return null;

  function fmtJson(v: unknown): string {
    if (v == null) return "—";
    if (typeof v === "string") {
      try {
        const parsed = JSON.parse(v);
        return JSON.stringify(parsed, null, 2);
      } catch {
        return v;
      }
    }
    try {
      return JSON.stringify(v, null, 2);
    } catch {
      return String(v);
    }
  }

  return (
    <div role="dialog" aria-modal="true" aria-label="Auditoría" style={{ position: "fixed", inset: 0, zIndex: 60, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div onClick={onClose} style={{ position: "absolute", inset: 0, background: "rgba(0,0,0,0.42)" }} />
      <div style={{ position: "relative", background: "var(--surface, #fff)", borderRadius: 12, padding: 20, minWidth: 480, maxWidth: 760, width: "94%", maxHeight: "86vh", overflowY: "auto", boxShadow: "0 12px 32px rgba(0,0,0,0.2)", display: "flex", flexDirection: "column", gap: 12 }}>
        <h3 style={{ margin: 0, fontSize: "1.05rem" }}>Auditoría · #{row.id} · {row.CODIGO}</h3>
        <div style={{ fontSize: "0.82rem", background: "#f8fafc", border: "0.5px solid var(--border)", borderRadius: 8, padding: "8px 10px" }}>
          <div><b>Estado:</b> {Number(row.anulado) === 1 ? <span style={{ color: "#dc2626", fontWeight: 700 }}>Anulado</span> : <span style={{ color: "#16a34a" }}>Activo</span>} {row.motivo_anulacion ? <>· <b>Motivo:</b> {row.motivo_anulacion}</> : null}</div>
          {row.anulado_por && <div><b>Anulado por:</b> {row.anulado_por} {row.anulado_en ? `· ${row.anulado_en}` : ""}</div>}
          {row.editado_por && <div><b>Editado por:</b> {row.editado_por} {row.editado_en ? `· ${row.editado_en}` : ""}</div>}
        </div>
        {loading && <p className="sub">Cargando auditoría…</p>}
        {err && <p className="error" style={{ fontSize: "0.85rem" }}>{err}</p>}
        {items && items.length === 0 && <p className="sub">Sin registros de auditoría.</p>}
        {items && items.length > 0 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {items.map((a) => (
              <div key={a.id} style={{ border: "0.5px solid var(--border)", borderRadius: 8, padding: 10, background: a.accion === "anular" ? "#fef2f2" : "#f0fdf4" }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap", fontSize: "0.82rem" }}>
                  <strong style={{ textTransform: "uppercase", color: a.accion === "anular" ? "#dc2626" : "#16a34a" }}>{a.accion}</strong>
                  <span style={{ color: "var(--muted)" }}>{a.realizado_por || "—"} · {a.realizado_en ? new Date(a.realizado_en).toLocaleString("es-AR") : ""}</span>
                </div>
                {a.motivo && <div style={{ fontSize: "0.82rem", marginTop: 4 }}><b>Motivo:</b> {a.motivo}</div>}
                <details style={{ marginTop: 6 }}>
                  <summary style={{ cursor: "pointer", fontSize: "0.82rem" }}>Ver snapshot</summary>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 8 }}>
                    <div>
                      <div style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--muted)" }}>ANTES</div>
                      <pre style={{ fontSize: "0.72rem", background: "#fff", border: "0.5px solid #e5e7eb", borderRadius: 6, padding: 8, maxHeight: 220, overflow: "auto", whiteSpace: "pre-wrap", wordBreak: "break-word" }}>{fmtJson(a.datos_before)}</pre>
                    </div>
                    <div>
                      <div style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--muted)" }}>DESPUÉS</div>
                      <pre style={{ fontSize: "0.72rem", background: "#fff", border: "0.5px solid #e5e7eb", borderRadius: 6, padding: 8, maxHeight: 220, overflow: "auto", whiteSpace: "pre-wrap", wordBreak: "break-word" }}>{fmtJson(a.datos_after)}</pre>
                    </div>
                  </div>
                </details>
              </div>
            ))}
          </div>
        )}
        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <button type="button" className="btn-secondary" onClick={onClose} style={{ minHeight: 36 }}>Cerrar</button>
        </div>
      </div>
    </div>
  );
}

export default function SalidasPage() {
  const { usuario } = useAuth();
  const puedeEscribir = permisoDe(usuario, "salidas") === "escritura";
  const esAdmin = usuario?.rol === "admin" && puedeEscribir;

  const [cats, setCats] = useState<CatalogosSalidas | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [okMsg, setOkMsg] = useState<string | null>(null);
  const [cargandoCats, setCargandoCats] = useState(true);
  const [buscando, setBuscando] = useState(false);
  const [finalizando, setFinalizando] = useState(false);

  // Cabecera de salida (arriba)
  const [fecha, setFecha] = useState(hoyIsoLocal());
  const [tipo, setTipo] = useState("");
  const [orden, setOrden] = useState("");
  const [maquina, setMaquina] = useState("");
  const [sector, setSector] = useState("");
  const [operario, setOperario] = useState("");
  const [ordenBloqueada, setOrdenBloqueada] = useState(false);
  const [cabeceraError, setCabeceraError] = useState<string | null>(null);

  // Item actual
  const [codigo, setCodigo] = useState("");
  const [articulo, setArticulo] = useState<ArticuloSalida | null>(null);
  const [cantidad, setCantidad] = useState("");
  const [pendientes, setPendientes] = useState<ItemPendiente[]>([]);
  const [proyeccion, setProyeccion] = useState<ProyeccionStock | null>(null);
  const [proyError, setProyError] = useState<string | null>(null);
  const [seleccionadoId, setSeleccionadoId] = useState<string | null>(null);

  // Maestro modal
  const [showMaestro, setShowMaestro] = useState(false);

  // Atenciones
  const [showAtencion, setShowAtencion] = useState(false);
  const [atHoy, setAtHoy] = useState<{ total: number; con: number; sin: number } | null>(null);

  // DB health badge (Punto 2 - DB directo)
  const [dbEnabled, setDbEnabled] = useState<boolean | null>(null);

  // Historial
  const [histFiltros, setHistFiltros] = useState({ desde: "", hasta: "", q: "", codigo: "", sector: "" });
  const [histItems, setHistItems] = useState<MovimientoRow[]>([]);
  const [histTotal, setHistTotal] = useState(0);
  const [histLoading, setHistLoading] = useState(false);
  const [histPage, setHistPage] = useState(0);
  const histPageSize = 20;
  const [incluirAnulados, setIncluirAnulados] = useState(false);
  const [anularRow, setAnularRow] = useState<MovimientoRow | null>(null);
  const [editarRow, setEditarRow] = useState<MovimientoRow | null>(null);
  const [auditoriaRow, setAuditoriaRow] = useState<MovimientoRow | null>(null);

  // Remito preview
  const [showRemito, setShowRemito] = useState(false);
  const [remitoData, setRemitoData] = useState<{
    fecha: string;
    numero_orden: string | number;
    tipo_comprobante: string;
    sector: string;
    operario: string;
    maquina: string;
    items: ItemPendiente[] | MovimientoRow[];
  } | null>(null);

  const codigoRef = useRef<HTMLInputElement>(null);
  const cantidadRef = useRef<HTMLInputElement>(null);

  const cargarAtHoy = useCallback(async () => {
    const hoy = hoyIsoLocal();
    try {
      const r = await listarAtenciones({ desde: hoy, hasta: hoy, limite: 500 });
      const con = r.items.filter((x) => x.con_retiro === 1 || x.con_retiro === true).length;
      setAtHoy({ total: r.total, con, sin: r.total - con });
    } catch {
      // silencioso
    }
  }, []);

  const cargarHistorial = useCallback(async () => {
    setHistLoading(true);
    try {
      const res = await listarMovimientos({
        desde: histFiltros.desde || undefined,
        hasta: histFiltros.hasta || undefined,
        q: histFiltros.q || undefined,
        codigo: histFiltros.codigo || undefined,
        sector: histFiltros.sector || undefined,
        limite: 200,
        incluir_anulados: esAdmin ? incluirAnulados : false,
      });
      setHistItems(res.items as unknown as MovimientoRow[]);
      setHistTotal(res.total);
      setHistPage(0);
    } catch {
      // silencioso, no bloquear
      setHistItems([]);
      setHistTotal(0);
    } finally {
      setHistLoading(false);
    }
  }, [histFiltros, incluirAnulados, esAdmin]);

  useEffect(() => {
    void cargarAtHoy();
  }, [cargarAtHoy]);

  useEffect(() => {
    void cargarHistorial();
  }, [cargarHistorial]);

  useEffect(() => {
    let cancel = false;
    (async () => {
      try {
        const h = (await fetchSalidasHealth()) as unknown as { db_enabled?: boolean; excel_backup?: boolean };
        if (!cancel) setDbEnabled(!!h.db_enabled);
      } catch {
        if (!cancel) setDbEnabled(null);
      }
    })();
    return () => {
      cancel = true;
    };
  }, []);

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
    () => pendientes.reduce((acc, p) => acc + Math.abs(p.monto), 0),
    [pendientes],
  );

  // Atajos: F2 atencion, F3 maestro/foco codigo
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement)?.tagName;
      const isInput = tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA";
      if (e.key === "F2") {
        e.preventDefault();
        if (puedeEscribir) setShowAtencion(true);
      } else if (e.key === "F3") {
        e.preventDefault();
        // F3 ahora abre maestro de stock (nueva semantica) o enfoca codigo si ya abierto
        if (showMaestro) return;
        setShowMaestro(true);
      } else if ((e.key === "Delete" || e.key === "Del") && seleccionadoId) {
        if (isInput && (e.target as HTMLElement)?.id !== "sal-codigo" && (e.target as HTMLElement)?.id !== "sal-cantidad") return;
        if (isInput) return;
        e.preventDefault();
        setPendientes((prev) => prev.filter((p) => p.id !== seleccionadoId));
        setSeleccionadoId(null);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [puedeEscribir, seleccionadoId, showMaestro]);

  useEffect(() => {
    const cod = (articulo?.codigo || codigo).trim().toUpperCase();
    const cantNum = Number(String(cantidad).replace(",", "."));
    if (!cod || !articulo || articulo.codigo !== cod || !Number.isFinite(cantNum) || cantNum === 0) {
      setProyeccion(null);
      setProyError(null);
      return;
    }
    const cantSigned = Math.abs(cantNum);
    let cancel = false;
    const t = window.setTimeout(() => {
      void (async () => {
        try {
          const proy = await proyectarStock({
            codigo: articulo.codigo,
            cantidad: cantSigned,
            es_devolucion: false,
            pendientes: pendientes.map((p) => ({ codigo: p.codigo, cantidad: p.cantidad })),
          });
          if (!cancel) {
            setProyeccion(proy);
            setProyError(null);
          }
        } catch (e) {
          if (!cancel) {
            setProyeccion(null);
            setProyError(e instanceof Error ? e.message : "No se pudo calcular stock proyectado.");
          }
        }
      })();
    }, 280);
    return () => {
      cancel = true;
      window.clearTimeout(t);
    };
  }, [articulo, codigo, cantidad, pendientes]);

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
    setProyeccion(null);
    setProyError(null);
    setFecha(hoyIsoLocal());
    setSeleccionadoId(null);
    setCabeceraError(null);
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
      window.setTimeout(() => cantidadRef.current?.focus(), 60);
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
    const cantSigned = Math.abs(cantNum);
    try {
      const proy = await proyectarStock({
        codigo: art.codigo,
        cantidad: cantSigned,
        es_devolucion: false,
        pendientes: pendientes.map((p) => ({ codigo: p.codigo, cantidad: p.cantidad })),
      });
      setProyeccion(proy);
      const monto = Math.round(Math.abs(cantSigned) * Math.abs(art.precio_unitario) * 100) / 100;
      const item: ItemPendiente = {
        id: nuevoId(),
        fecha,
        codigo: art.codigo,
        descripcion: art.descripcion,
        ubicacion: art.ubicacion,
        cantidad: cantSigned,
        tipo_comprobante: (tipo || "").trim().toUpperCase(),
        numero_orden: String(orden || "").trim(),
        maquina: maquina.trim().toUpperCase(),
        precio_unitario: art.precio_unitario,
        monto,
        operario: (operario || "").trim().toUpperCase(),
        sector: (sector || "").trim().toUpperCase(),
        es_devolucion: false,
      };
      setPendientes((prev) => [...prev, item]);
      setCantidad("");
      setCodigo("");
      setArticulo(null);
      setProyeccion(null);
      setProyError(null);
      setOrdenBloqueada(true);
      setOkMsg(`Agregado: ${item.codigo} × ${fmtNum(cantSigned)}`);
      setSeleccionadoId(item.id);
      window.setTimeout(() => {
        codigoRef.current?.focus();
        codigoRef.current?.select();
      }, 30);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo agregar.");
    }
  }

  function quitarPendiente(id: string) {
    setPendientes((prev) => prev.filter((p) => p.id !== id));
    if (seleccionadoId === id) setSeleccionadoId(null);
  }

  function limpiarCarga() {
    if (pendientes.length && !window.confirm("¿Borrar la carga pendiente no guardada?")) return;
    resetFormularioParaSiguienteOrden();
    setOkMsg(null);
    setError(null);
  }

  async function finalizar() {
    if (!pendientes.length || !puedeEscribir) return;
    const tipoEff = (tipo || "").trim();
    const ordenEff = String(orden || "").trim();
    const sectorEff = (sector || "").trim();
    const operarioEff = (operario || "").trim();
    const faltan: string[] = [];
    if (!tipoEff) faltan.push("comprobante");
    if (!ordenEff) faltan.push("N° orden");
    if (!sectorEff) faltan.push("sector");
    if (!operarioEff) faltan.push("operario/técnico");
    if (faltan.length) {
      setCabeceraError(`Completá cabecera antes de finalizar: ${faltan.join(", ")}.`);
      setError(`Completá cabecera antes de finalizar: ${faltan.join(", ")}. Usá "Cambiar cabecera" si está bloqueada.`);
      return;
    }
    setCabeceraError(null);
    const pendientesNormalizados = pendientes.map((p) => ({
      ...p,
      tipo_comprobante: p.tipo_comprobante || tipoEff.toUpperCase(),
      numero_orden: p.numero_orden || ordenEff,
      sector: p.sector || sectorEff.toUpperCase(),
      operario: p.operario || operarioEff.toUpperCase(),
      maquina: p.maquina || maquina.trim().toUpperCase(),
    }));
    const incompletos = pendientesNormalizados.filter((p) => !p.tipo_comprobante || !String(p.numero_orden).trim() || !p.sector || !p.operario);
    if (incompletos.length) {
      setError(`Hay ${incompletos.length} ítem(s) sin cabecera completa.`);
      return;
    }
    if (!window.confirm(`¿Confirmar ${pendientes.length} ítem(s) y grabar?`)) return;
    setFinalizando(true);
    setError(null);
    setOkMsg(null);
    const items = pendientesNormalizados.map((p) => ({
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
      const res = await confirmarSalida({ items, forzar_negativos: true });
      setOkMsg(`${res.mensaje} · ${res.movimientos} movimiento(s).`);
      // Fix 3: No auto-mostrar remito al finalizar — usar botón manual "Previsualizar remito (carga actual)" si se necesita
      void cargarHistorial();
      resetFormularioParaSiguienteOrden();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "No se pudo finalizar.";
      const limpio = msg.replace(/forzar_negativos\s*=\s*true/gi, "").replace(/permitir_stock_negativo/gi, "").replace(/\s{2,}/g, " ").trim();
      setError(limpio || "No se pudo finalizar la carga.");
    } finally {
      setFinalizando(false);
    }
  }

  async function handleExportDiario() {
    const f = fecha || hoyIsoLocal();
    try {
      const blob = await exportarDiario(f);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `salidas_${f.replace(/-/g, "-")}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setOkMsg(`Diario ${f} descargado.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo exportar diario.");
    }
  }

  async function handleRemitoHistorial(row: MovimientoRow) {
    const ordenVal = String(row.NUMERO_ORDEN || "").trim();
    if (!ordenVal) {
      setError("Fila sin Nº orden, no se puede generar remito.");
      return;
    }
    const fechaVal = typeof row.FECHA === "string" ? row.FECHA : hoyIsoLocal();
    // Intentar normalizar fecha a YYYY-MM-DD
    let fechaIso: string | undefined;
    try {
      if (fechaVal.includes("/")) {
        const [d, m, y] = fechaVal.split("/").map((s) => s.trim());
        fechaIso = `${y.padStart(4, "0")}-${m.padStart(2, "0")}-${d.padStart(2, "0")}`;
      } else {
        fechaIso = fechaVal;
      }
    } catch {
      fechaIso = undefined;
    }
    try {
      const blob = await exportarRemito({ orden: ordenVal, fecha: fechaIso });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `remito_${ordenVal}_${fechaIso || "s-f"}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setOkMsg(`Remito ${ordenVal} descargado.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo generar remito.");
    }
  }

  const usuarioNombre =
    (usuario as unknown as { usuario?: string; nombre?: string } | null)?.usuario ||
    (usuario as unknown as { usuario?: string } | null)?.usuario ||
    null;

  const histPageItems = useMemo(() => {
    const start = histPage * histPageSize;
    return histItems.slice(start, start + histPageSize);
  }, [histItems, histPage]);
  const histPages = Math.max(1, Math.ceil(histItems.length / histPageSize));

  return (
    <div className="page-content sal-page">
      {/* Breadcrumb */}
      <nav aria-label="Breadcrumb" style={{ fontSize: "0.82rem", color: "var(--muted)" }}>
        <span>Inicio</span> <span style={{ margin: "0 6px" }}>›</span> <strong style={{ color: "var(--text)" }}>Salidas</strong>
      </nav>

      <header className="page-header sal-header">
        <div>
          <h1>Salidas</h1>
          <p className="sub">
            Egreso de material del pañol.{" "}
            {dbEnabled === null ? (
              <span style={{ opacity: 0.6 }}>verificando modo…</span>
            ) : dbEnabled ? (
              <span style={{ color: "#16a34a", fontWeight: 700 }} title="Bajas en vivo a MariaDB panol.salida_historial (SALIDAS_DB_ENABLED=1)">
                ● DB activa
              </span>
            ) : (
              <span style={{ color: "#6b7280" }} title="Modo Excel fallback (SALIDAS_DB_ENABLED=0)">
                ○ Excel
              </span>
            )}{" "}
            · Maestro solo lectura.
          </p>
        </div>
        <div className="sal-header-actions" style={{ flexWrap: "wrap" }}>
          <div className="sal-toggle" style={{ flexDirection: "column", alignItems: "flex-start", gap: 2, minWidth: 168 }} aria-live="polite">
            <span style={{ fontSize: "0.78rem", fontWeight: 700 }}>Ventanilla hoy</span>
            <span style={{ fontSize: "0.82rem", fontVariantNumeric: "tabular-nums" }}>
              {atHoy ? (
                <>
                  {atHoy.total} at. · <span style={{ color: "#16a34a" }}>{atHoy.con} con</span> · <span style={{ color: "#dc2626" }}>{atHoy.sin} sin</span>
                </>
              ) : (
                "—"
              )}
            </span>
          </div>
          <button type="button" className="btn-primary" onClick={() => setShowAtencion(true)} disabled={!puedeEscribir} title="Atajo F2" style={{ minHeight: 44, whiteSpace: "nowrap" }}>
            + Atención (F2)
          </button>
        </div>
      </header>

      {/* Paso a paso prolijo */}
      <section
        style={{
          background: "var(--surface)",
          border: "0.5px solid var(--border)",
          borderRadius: "var(--radius)",
          padding: "12px 16px",
          display: "flex",
          flexWrap: "wrap",
          gap: "12px 18px",
          alignItems: "center",
        }}
      >
        <strong style={{ fontSize: "0.9rem" }}>Paso a paso:</strong>
        <span className="sub" style={{ margin: 0, fontSize: "0.86rem" }}>
          <b>1.</b> Completá cabecera
        </span>
        <span style={{ color: "var(--border)" }}>→</span>
        <span className="sub" style={{ margin: 0, fontSize: "0.86rem" }}>
          <b>2.</b> Cargá ítems
        </span>
        <span style={{ color: "var(--border)" }}>→</span>
        <span className="sub" style={{ margin: 0, fontSize: "0.86rem" }}>
          <b>3.</b> Finalizá
        </span>
        <span style={{ color: "var(--border)" }}>→</span>
        <span className="sub" style={{ margin: 0, fontSize: "0.86rem" }}>
          <b>4.</b> Imprimí remito / Registrá atención sin stock (F2)
        </span>
      </section>

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

      {/* Cabecera de salida */}
      <section
        style={{
          background: "var(--surface)",
          border: "0.5px solid var(--border)",
          borderRadius: "var(--radius)",
          padding: "14px 16px",
          boxShadow: "0 1px 6px rgba(0,0,0,0.04)",
        }}
      >
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "baseline", justifyContent: "space-between", gap: 8, marginBottom: 10 }}>
          <h2 style={{ margin: 0, fontFamily: "var(--font-display)", fontSize: "1.1rem" }}>Cabecera de salida</h2>
          <span className="sub" style={{ margin: 0, fontSize: "0.78rem" }}>
            Campos se aplican a todos los ítems al finalizar. Editá arriba antes de confirmar.
          </span>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 10 }}>
          <label className="sal-field">
            <span className="sal-muted">Fecha *</span>
            <input id="sal-fecha" type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} disabled={ordenBloqueada} required aria-label="Fecha" />
          </label>

          <label className="sal-field">
            <span className="sal-muted">Comprobante *</span>
            <select id="sal-comprobante" value={tipo} onChange={(e) => setTipo(e.target.value)} disabled={ordenBloqueada} aria-label="Comprobante">
              <option value="">Seleccione…</option>
              {(cats?.tipos_comprobante || []).map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>

          <label className="sal-field">
            <span className="sal-muted">Nº orden *</span>
            <input id="sal-orden" value={orden} onChange={(e) => setOrden(e.target.value)} disabled={ordenBloqueada} placeholder="Ej 12345" aria-label="Número de orden" />
          </label>

          <label className="sal-field">
            <span className="sal-muted">Máquina / sitio</span>
            <input id="sal-maquina" value={maquina} onChange={(e) => setMaquina(e.target.value.toUpperCase())} disabled={ordenBloqueada} placeholder="Ej L3, Taller" aria-label="Máquina o sitio" />
          </label>

          <label className="sal-field">
            <span className="sal-muted">Sector *</span>
            <select id="sal-sector" value={sector} onChange={(e) => setSector(e.target.value)} disabled={ordenBloqueada} aria-label="Sector">
              <option value="" disabled>
                Seleccione sector…
              </option>
              {(cats?.sectores || []).map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>

          <label className="sal-field">
            <span className="sal-muted">Técnico / operario *</span>
            <select id="sal-operario" value={operario} onChange={(e) => setOperario(e.target.value)} aria-label="Operario" disabled={!sector || ordenBloqueada}>
              <option value="" disabled>
                {sector ? "Seleccione operario…" : "Seleccione sector primero…"}
              </option>
              {operarios.map((o) => (
                <option key={o} value={o}>
                  {o}
                </option>
              ))}
            </select>
          </label>
        </div>

        {ordenBloqueada && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center", marginTop: 10 }}>
            <span className="sub" style={{ margin: 0, fontSize: "0.78rem", flex: 1 }}>
              Cabecera bloqueada para carga rápida tras primer ítem.
            </span>
            <button type="button" className="btn-secondary" onClick={() => setOrdenBloqueada(false)} style={{ minHeight: 36 }}>
              Cambiar cabecera
            </button>
          </div>
        )}
        {cabeceraError && (
          <p className="error" role="alert" style={{ margin: "8px 0 0" }}>
            {cabeceraError}
          </p>
        )}
      </section>

      {/* Registro de ítems */}
      <div className="sal-grid" style={{ gridTemplateColumns: "minmax(280px, 420px) 1fr" }}>
        <form
          className="sal-form"
          onSubmit={(e) => void onAgregar(e)}
          style={{ display: "flex", flexDirection: "column", gap: 10, background: "var(--surface)", border: "0.5px solid var(--border)", borderRadius: "var(--radius)", padding: "14px 16px" }}
        >
          <fieldset disabled={!puedeEscribir || finalizando} style={{ border: 0, margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 10 }}>
            <legend style={{ fontFamily: "var(--font-display)", fontSize: "1.1rem", fontWeight: 700, marginBottom: 4, padding: 0 }}>Registro de ítems de salida</legend>

            <div className="sal-row">
              <div className="sal-field sal-grow">
                <span className="sal-muted">Código *</span>
                <input
                  ref={codigoRef}
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
                  placeholder="Código — F3 maestro"
                  autoComplete="off"
                  aria-label="Código"
                />
              </div>
              {/* Maestro accesible sin cabecera — no depende de sector/operario/orden; solo permiso escritura */}
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setShowMaestro(true)}
                disabled={!puedeEscribir || finalizando}
                title="Maestro de stock (F3) — usable sin completar cabecera"
                style={{ minHeight: 44, alignSelf: "flex-end", whiteSpace: "nowrap" }}
              >
                🔍 Maestro de stock
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

            <label className="sal-field">
              <span className="sal-muted">Cantidad *</span>
              <input
                ref={cantidadRef}
                id="sal-cantidad"
                value={cantidad}
                onChange={(e) => setCantidad(e.target.value)}
                onKeyDown={(ev) => {
                  if (ev.key === "Enter") {
                    ev.preventDefault();
                    const form = (ev.target as HTMLElement).closest("form");
                    if (form) form.requestSubmit();
                  }
                }}
                inputMode="decimal"
                required
                placeholder="Cantidad — Enter para agregar"
                aria-label="Cantidad"
              />
            </label>

            {(proyeccion || proyError) && (
              <p className={`sal-proy${proyeccion?.alerta_negativo || proyError ? " sal-proy-warn" : ""}`} role="status" aria-live="polite">
                {proyError
                  ? proyError
                  : proyeccion?.alerta_negativo
                    ? `Stock proyectado: ${fmtNum(proyeccion.stock_proyectado)} (quedaría en negativo). Se permitirá al confirmar.`
                    : `Stock proyectado: ${fmtNum(proyeccion!.stock_proyectado)}`}
              </p>
            )}

            <div className="sal-form-actions">
              <button type="submit" className="btn-primary" style={{ flex: 1 }}>
                Agregar a carga (Enter)
              </button>
              <button type="button" className="btn-secondary" onClick={() => void onBuscarCodigo()} disabled={buscando || !codigo.trim()} title="Buscar">
                {buscando ? "…" : "Validar"}
              </button>
            </div>
            <p className="sub" style={{ margin: 0, fontSize: "0.78rem" }}>F3 abre maestro · Enter valida/agrega · Cabecera se valida al finalizar.</p>
          </fieldset>
        </form>

        <section className="sal-carga" style={{ background: "var(--surface)", border: "0.5px solid var(--border)", borderRadius: "var(--radius)", padding: "14px 16px" }}>
          <div className="sal-carga-head">
            <h2>Carga pendiente</h2>
            <p className="sub">
              {pendientes.length} ítem(s) · Total {fmtPesos(totalCarga)} {pendientes.length > 0 && <span>· Supr quita seleccionado</span>}
            </p>
          </div>

          {pendientes.length === 0 ? (
            <div style={{ padding: "18px 12px", textAlign: "center", border: "0.5px dashed var(--border)", borderRadius: 8, background: "color-mix(in srgb, var(--bg) 60%, transparent)" }}>
              <p style={{ margin: 0, color: "var(--muted)", fontSize: "0.9rem" }}>Sin ítems. Agregá con <b>Maestro de stock</b> → Código → Cantidad → Agregar.</p>
            </div>
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
                      <tr
                        key={p.id}
                        className={seleccionadoId === p.id ? "sal-row-sel" : ""}
                        onClick={() => setSeleccionadoId(p.id)}
                        style={{ cursor: "pointer", outline: seleccionadoId === p.id ? "1.5px solid var(--primary)" : undefined }}
                      >
                        <td>{p.codigo}</td>
                        <td>{p.descripcion}</td>
                        <td className="sal-num">{fmtNum(p.cantidad)}</td>
                        <td className="sal-num">{fmtPesos(p.precio_unitario)}</td>
                        <td className="sal-num">{fmtPesos(p.monto)}</td>
                        <td>
                          <button type="button" className="sal-link-btn" onClick={(e) => { e.stopPropagation(); quitarPendiente(p.id); }} disabled={!puedeEscribir || finalizando} title="Supr">
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
                  <li key={`m-${p.id}`} className={`sal-card-item ${seleccionadoId === p.id ? "sal-row-sel" : ""}`} onClick={() => setSeleccionadoId(p.id)}>
                    <div className="sal-card-top">
                      <strong>{p.codigo}</strong>
                      <button type="button" className="sal-link-btn" onClick={(e) => { e.stopPropagation(); quitarPendiente(p.id); }} disabled={!puedeEscribir || finalizando}>
                        Quitar
                      </button>
                    </div>
                    <p className="sal-card-desc">{p.descripcion}</p>
                    <div className="sal-card-meta">
                      <span>
                        Cant. <b className="sal-num">{fmtNum(p.cantidad)}</b>
                      </span>
                      <span>
                        Monto <b className="sal-num">{fmtPesos(p.monto)}</b>
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            </>
          )}

          <div className="sal-carga-actions">
            <button type="button" className="btn-primary" disabled={!puedeEscribir || !pendientes.length || finalizando} onClick={() => void finalizar()} style={{ flex: 1 }}>
              {finalizando ? "Guardando…" : "Finalizar carga"}
            </button>
            <button type="button" className="btn-secondary" disabled={!pendientes.length || finalizando} onClick={limpiarCarga}>
              Limpiar
            </button>
          </div>
          {pendientes.length > 0 && (
            <button type="button" className="btn-secondary" onClick={() => {
              const eff = { fecha, numero_orden: orden || "s/n", tipo_comprobante: tipo || "—", sector: sector || "—", operario: operario || "—", maquina: maquina || "—" };
              setRemitoData({ ...eff, items: pendientes });
              setShowRemito(true);
            }} style={{ width: "100%", marginTop: 8, minHeight: 40 }}>
              🖨️ Previsualizar remito (carga actual)
            </button>
          )}
          {!puedeEscribir && <p className="sub">Tu usuario tiene solo lectura en Salidas.</p>}
        </section>
      </div>

      {/* Historial */}
      <section style={{ background: "var(--surface)", border: "0.5px solid var(--border)", borderRadius: "var(--radius)", padding: "14px 16px" }}>
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "baseline", justifyContent: "space-between", gap: 8, marginBottom: 10 }}>
          <h2 style={{ margin: 0, fontFamily: "var(--font-display)", fontSize: "1.1rem" }}>Historial</h2>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
            {esAdmin && (
              <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "0.82rem", userSelect: "none", background: incluirAnulados ? "#fef3c7" : "#f8fafc", border: "0.5px solid var(--border)", borderRadius: 8, padding: "6px 10px" }}>
                <input type="checkbox" checked={incluirAnulados} onChange={(e) => setIncluirAnulados(e.target.checked)} />
                Mostrar anulados
              </label>
            )}
            <button type="button" className="btn-secondary" onClick={() => void cargarHistorial()} disabled={histLoading} style={{ minHeight: 36 }}>
              {histLoading ? "…" : "↻ Actualizar"}
            </button>
            <button type="button" className="btn-secondary" onClick={() => void handleExportDiario()} style={{ minHeight: 36 }}>
              📥 Diario del día ({fecha})
            </button>
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 8, marginBottom: 10 }}>
          <label className="sal-field" style={{ margin: 0 }}>
            <span className="sal-muted">Desde</span>
            <input type="date" value={histFiltros.desde} onChange={(e) => setHistFiltros((p) => ({ ...p, desde: e.target.value }))} />
          </label>
          <label className="sal-field" style={{ margin: 0 }}>
            <span className="sal-muted">Hasta</span>
            <input type="date" value={histFiltros.hasta} onChange={(e) => setHistFiltros((p) => ({ ...p, hasta: e.target.value }))} />
          </label>
          <label className="sal-field" style={{ margin: 0 }}>
            <span className="sal-muted">Buscar (código/desc/orden)</span>
            <input value={histFiltros.q} onChange={(e) => setHistFiltros((p) => ({ ...p, q: e.target.value.toUpperCase() }))} placeholder="Ej TORNILLO, 123" />
          </label>
          <label className="sal-field" style={{ margin: 0 }}>
            <span className="sal-muted">Sector</span>
            <select value={histFiltros.sector} onChange={(e) => setHistFiltros((p) => ({ ...p, sector: e.target.value }))}>
              <option value="">Todos</option>
              {(cats?.sectores || []).map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
          <label className="sal-field" style={{ margin: 0 }}>
            <span className="sal-muted">Código exacto</span>
            <input value={histFiltros.codigo} onChange={(e) => setHistFiltros((p) => ({ ...p, codigo: e.target.value.toUpperCase() }))} placeholder="Filtrar código" />
          </label>
        </div>

        <div style={{ display: "flex", gap: 8, marginBottom: 10, flexWrap: "wrap" }}>
          <button type="button" className="btn-primary" onClick={() => void cargarHistorial()} disabled={histLoading} style={{ minHeight: 36 }}>
            Buscar
          </button>
          <button
            type="button"
            className="btn-secondary"
            onClick={() => setHistFiltros({ desde: "", hasta: "", q: "", codigo: "", sector: "" })}
            style={{ minHeight: 36 }}
          >
            Limpiar filtros
          </button>
          <span className="sub" style={{ margin: 0, alignSelf: "center", fontSize: "0.82rem" }}>
            {histTotal} registro(s) · {histItems.length} cargados
          </span>
        </div>

        {histLoading && <p className="sub">Cargando historial…</p>}
        {!histLoading && histItems.length === 0 ? (
          <div style={{ padding: "18px 12px", textAlign: "center", border: "0.5px dashed var(--border)", borderRadius: 8 }}>
            <p style={{ margin: 0, color: "var(--muted)", fontSize: "0.9rem" }}>Sin movimientos para los filtros. Ajustá fechas o buscá sin filtros.</p>
          </div>
        ) : (
          <>
            <div className="sal-table-wrap" style={{ maxHeight: "min(48vh, 520px)" }}>
              <table className="sal-table">
                <thead>
                  <tr>
                    <th>Fecha</th>
                    <th>Código</th>
                    <th>Descripción</th>
                    <th>Cant.</th>
                    <th>Monto</th>
                    <th>Orden</th>
                    <th>Sector</th>
                    <th>Operario</th>
                    <th>Estado</th>
                    <th>Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {histPageItems.map((r, idx) => {
                    const anulada = Number(r.anulado) === 1;
                    return (
                      <tr key={`${r.CODIGO}-${r.NUMERO_ORDEN}-${idx}-${r.FECHA}-${r.id}`} style={anulada ? { opacity: 0.72, background: "#fef2f2" } : undefined}>
                        <td style={anulada ? { textDecoration: "line-through" } : undefined}>{typeof r.FECHA === "string" ? r.FECHA : String(r.FECHA)}</td>
                        <td style={{ fontWeight: 600, textDecoration: anulada ? "line-through" : undefined }}>{r.CODIGO}</td>
                        <td style={{ maxWidth: 220, wordBreak: "break-word", textDecoration: anulada ? "line-through" : undefined }}>{r.DESCRIPCION}</td>
                        <td className="sal-num" style={anulada ? { textDecoration: "line-through" } : undefined}>{fmtNum(Number(r.CANTIDAD) || 0)}</td>
                        <td className="sal-num" style={anulada ? { textDecoration: "line-through" } : undefined}>{fmtPesos(Number(r.MONTO_TOTAL_SALIDA) || 0)}</td>
                        <td style={anulada ? { textDecoration: "line-through" } : undefined}>{r.NUMERO_ORDEN || "—"}</td>
                        <td style={anulada ? { textDecoration: "line-through" } : undefined}>{r.SECTOR || "—"}</td>
                        <td style={anulada ? { textDecoration: "line-through" } : undefined}>{r.OPERARIO || "—"}</td>
                        <td>
                          {anulada ? (
                            <span title={r.motivo_anulacion || ""} style={{ display: "inline-block", fontSize: "0.72rem", fontWeight: 700, color: "#dc2626", background: "#fee2e2", border: "0.5px solid #fecaca", borderRadius: 999, padding: "2px 8px", whiteSpace: "nowrap" }}>Anulado</span>
                          ) : r.editado_por ? (
                            <span title={`Editado por ${r.editado_por} ${r.editado_en || ""}`} style={{ display: "inline-block", fontSize: "0.72rem", fontWeight: 600, color: "#2563eb", background: "#dbeafe", border: "0.5px solid #bfdbfe", borderRadius: 999, padding: "2px 8px", whiteSpace: "nowrap" }}>Editado</span>
                          ) : (
                            <span style={{ display: "inline-block", fontSize: "0.72rem", color: "#16a34a", background: "#dcfce7", border: "0.5px solid #bbf7d0", borderRadius: 999, padding: "2px 8px" }}>Activo</span>
                          )}
                        </td>
                        <td>
                          <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                            <button type="button" className="btn-secondary" onClick={() => void handleRemitoHistorial(r)} style={{ minHeight: 28, padding: "2px 8px", fontSize: "0.74rem", whiteSpace: "nowrap" }} title="Descargar remito">
                              🖨️
                            </button>
                            {esAdmin && !anulada && (
                              <>
                                <button type="button" className="btn-secondary" onClick={() => setEditarRow(r)} style={{ minHeight: 28, padding: "2px 8px", fontSize: "0.74rem" }} title="Editar">
                                  ✏️
                                </button>
                                <button type="button" className="btn-secondary" onClick={() => setAnularRow(r)} style={{ minHeight: 28, padding: "2px 8px", fontSize: "0.74rem", borderColor: "#fca5a5", color: "#dc2626" }} title="Anular">
                                  🗑️
                                </button>
                              </>
                            )}
                            {(esAdmin || !!r.anulado || !!r.editado_por) && (
                              <button type="button" className="btn-secondary" onClick={() => setAuditoriaRow(r)} style={{ minHeight: 28, padding: "2px 8px", fontSize: "0.74rem" }} title="Ver auditoría">
                                📋
                              </button>
                            )}
                            {anulada && !esAdmin && (
                              <button type="button" className="btn-secondary" onClick={() => setAuditoriaRow(r)} style={{ minHeight: 28, padding: "2px 8px", fontSize: "0.74rem" }} title="Ver motivo anulación">
                                👁️
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {histPages > 1 && (
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
                <button type="button" className="btn-secondary" disabled={histPage === 0} onClick={() => setHistPage((p) => Math.max(0, p - 1))} style={{ minHeight: 36 }}>
                  Anterior
                </button>
                <span className="sub" style={{ margin: 0, fontSize: "0.85rem" }}>
                  Página {histPage + 1} de {histPages} · {histItems.length} fila(s)
                </span>
                <button type="button" className="btn-secondary" disabled={histPage + 1 >= histPages} onClick={() => setHistPage((p) => p + 1)} style={{ minHeight: 36 }}>
                  Siguiente
                </button>
              </div>
            )}
          </>
        )}
      </section>

      <AtencionModal open={showAtencion} onClose={() => setShowAtencion(false)} onSaved={() => { setOkMsg("Atención registrada."); void cargarAtHoy(); }} usuarioActual={usuarioNombre} />
      <MaestroStockModal open={showMaestro} onClose={() => setShowMaestro(false)} onSelect={(art) => { setCodigo(art.codigo); setArticulo(art); window.setTimeout(() => cantidadRef.current?.focus(), 60); }} />
      <AnularModal open={!!anularRow} row={anularRow} onClose={() => setAnularRow(null)} onAnulado={() => { setOkMsg("Movimiento anulado (sin reversión de stock)."); void cargarHistorial(); }} />
      <EditarModal open={!!editarRow} row={editarRow} cats={cats} onClose={() => setEditarRow(null)} onGuardado={() => { setOkMsg("Movimiento editado."); void cargarHistorial(); }} />
      <AuditoriaModal open={!!auditoriaRow} row={auditoriaRow} onClose={() => setAuditoriaRow(null)} />
      {showRemito && remitoData && (
        <PrintRemito
          data={{
            fecha: String(remitoData.fecha),
            numero_orden: remitoData.numero_orden,
            tipo_comprobante: remitoData.tipo_comprobante,
            sector: remitoData.sector,
            operario: remitoData.operario,
            maquina: remitoData.maquina,
            items: (remitoData.items as unknown as Array<{ codigo: string; descripcion: string; ubicacion: string; cantidad: number; precio_unitario: number; monto: number }>)?.map((it: unknown) => {
              const x = it as Record<string, unknown>;
              if ("codigo" in x && "cantidad" in x) {
                return {
                  codigo: String(x.codigo || x.CODIGO || ""),
                  descripcion: String(x.descripcion || x.DESCRIPCION || ""),
                  ubicacion: String(x.ubicacion || x.UBICACION || ""),
                  cantidad: Number(x.cantidad ?? x.CANTIDAD ?? 0),
                  precio_unitario: Number(x.precio_unitario ?? x.PRECIO_UNITARIO ?? 0),
                  monto: Number(x.monto ?? x.MONTO_TOTAL_SALIDA ?? 0),
                };
              }
              return {
                codigo: String(x.CODIGO || ""),
                descripcion: String(x.DESCRIPCION || ""),
                ubicacion: String(x.UBICACION || ""),
                cantidad: Number(x.CANTIDAD || 0),
                precio_unitario: Number(x.PRECIO_UNITARIO || 0),
                monto: Number(x.MONTO_TOTAL_SALIDA || 0),
              };
            }) || [],
          }}
          onClose={() => setShowRemito(false)}
        />
      )}
    </div>
  );
}
