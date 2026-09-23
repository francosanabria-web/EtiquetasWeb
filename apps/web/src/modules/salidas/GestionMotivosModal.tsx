import { useEffect, useState } from "react";
import {
  actualizarMotivo,
  crearMotivo,
  eliminarMotivo,
  listarMotivosAtencion,
  type MotivoRow,
} from "../../api/salidasClient";

type Props = {
  open: boolean;
  onClose: () => void;
  onChanged?: () => void;
};

export default function GestionMotivosModal({ open, onClose, onChanged }: Props) {
  const [motivos, setMotivos] = useState<MotivoRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [okMsg, setOkMsg] = useState<string | null>(null);

  // Form state
  const [editingId, setEditingId] = useState<number | null>(null);
  const [clave, setClave] = useState("");
  const [nombre, setNombre] = useState("");
  const [orden, setOrden] = useState("");
  const [activo, setActivo] = useState(true);

  async function cargar() {
    setLoading(true);
    setError(null);
    try {
      const r = await listarMotivosAtencion({ activos_only: false });
      setMotivos(r.items || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudieron cargar motivos.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!open) return;
    void cargar();
    // reset form when opening fresh (keep if editing)
  }, [open]);

  function resetForm() {
    setEditingId(null);
    setClave("");
    setNombre("");
    setOrden("");
    setActivo(true);
    setError(null);
    setOkMsg(null);
  }

  function startEdit(m: MotivoRow) {
    setEditingId(m.id);
    setClave(m.clave);
    setNombre(m.nombre);
    setOrden(String(m.orden ?? ""));
    setActivo(Boolean(m.activo));
    setError(null);
    setOkMsg(null);
  }

  async function handleGuardar(e?: React.FormEvent) {
    e?.preventDefault();
    setError(null);
    setOkMsg(null);
    const claveU = clave.trim().toUpperCase().replace(/\s+/g, "_");
    if (!claveU) {
      setError("Clave es obligatoria (ej SIN_STOCK).");
      return;
    }
    if (!nombre.trim()) {
      setError("Nombre es obligatorio.");
      return;
    }
    const ordenN = orden.trim() === "" ? undefined : Number(orden);
    if (orden.trim() !== "" && (!Number.isFinite(ordenN) || ordenN! < 0 || ordenN! > 127)) {
      setError("Orden debe ser entero 0..127.");
      return;
    }
    setSaving(true);
    try {
      if (editingId !== null) {
        const res = await actualizarMotivo(editingId, {
          clave: claveU,
          nombre: nombre.trim(),
          orden: ordenN,
          activo: activo ? 1 : 0,
        });
        setOkMsg(res.mensaje || "Motivo actualizado.");
      } else {
        const res = await crearMotivo({
          clave: claveU,
          nombre: nombre.trim(),
          orden: ordenN,
          activo: activo ? 1 : 0,
        });
        setOkMsg(res.mensaje || "Motivo creado.");
      }
      await cargar();
      resetForm();
      onChanged?.();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "No se pudo guardar.";
      if (/403|admin/i.test(msg)) {
        setError("Solo admin puede editar motivos (403). Iniciá sesión como admin.");
      } else {
        setError(msg);
      }
    } finally {
      setSaving(false);
    }
  }

  async function handleToggleActivo(m: MotivoRow) {
    setError(null);
    setOkMsg(null);
    setSaving(true);
    try {
      const res = await actualizarMotivo(m.id, { activo: m.activo ? 0 : 1 });
      setOkMsg(res.mensaje || (m.activo ? "Desactivado." : "Activado."));
      await cargar();
      onChanged?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo actualizar.");
    } finally {
      setSaving(false);
    }
  }

  async function handleEliminar(m: MotivoRow) {
    if (!window.confirm(`¿Eliminar "${m.clave}" — ${m.nombre}? Si tiene usos se desactivará en lugar de borrarse.`)) return;
    setError(null);
    setOkMsg(null);
    setSaving(true);
    try {
      const res = await eliminarMotivo(m.id);
      setOkMsg(res.mensaje || res.accion || "OK");
      await cargar();
      if (editingId === m.id) resetForm();
      onChanged?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo eliminar.");
    } finally {
      setSaving(false);
    }
  }

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Gestión de motivos"
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(15,23,42,0.48)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 70,
        padding: 16,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "var(--surface, #fff)",
          border: "0.5px solid var(--border, #e2e8f0)",
          borderRadius: 12,
          width: "min(720px, 98vw)",
          maxHeight: "92vh",
          overflow: "auto",
          boxShadow: "0 20px 60px rgba(0,0,0,0.22)",
        }}
      >
        <div style={{ padding: "14px 16px 0", display: "flex", justifyContent: "space-between", gap: 12, alignItems: "start" }}>
          <div>
            <h2 style={{ margin: 0, fontFamily: "var(--font-display)", fontSize: "1.15rem" }}>⚙️ Motivos sin retiro</h2>
            <p className="sub" style={{ margin: "4px 0 0" }}>
              Catálogo editable — solo admin. Clave UPPER sin espacios, nombre legible, orden y activo. Esc cierra.
            </p>
          </div>
          <button type="button" className="btn-secondary" onClick={onClose} aria-label="Cerrar" style={{ minHeight: 36 }}>
            ✕
          </button>
        </div>

        <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
          {loading && <p className="sub">Cargando motivos…</p>}
          {error && (
            <p className="error" role="alert" style={{ margin: 0 }}>
              {error}
            </p>
          )}
          {okMsg && (
            <p className="sal-ok" role="status" style={{ margin: 0 }}>
              {okMsg}
            </p>
          )}

          {/* Tabla */}
          <div style={{ overflow: "auto", border: "0.5px solid var(--border)", borderRadius: 8, maxHeight: 280 }}>
            <table className="sal-table" style={{ minWidth: 520 }}>
              <thead>
                <tr>
                  <th>Clave</th>
                  <th>Nombre</th>
                  <th style={{ textAlign: "center" }}>Activo</th>
                  <th style={{ textAlign: "right" }}>Orden</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {motivos.length === 0 && !loading ? (
                  <tr>
                    <td colSpan={5} style={{ textAlign: "center", color: "var(--muted)", padding: 16 }}>
                      Sin motivos (¿migración v3 no ejecutada?)
                    </td>
                  </tr>
                ) : (
                  motivos
                    .slice()
                    .sort((a, b) => (a.orden ?? 0) - (b.orden ?? 0) || a.clave.localeCompare(b.clave))
                    .map((m) => (
                      <tr key={m.id} style={{ opacity: m.activo ? 1 : 0.55, background: m.activo ? undefined : "color-mix(in srgb, var(--muted) 8%, transparent)" }}>
                        <td style={{ fontFamily: "monospace", fontWeight: 700 }}>{m.clave}</td>
                        <td>{m.nombre}</td>
                        <td style={{ textAlign: "center" }}>
                          <button
                            type="button"
                            onClick={() => void handleToggleActivo(m)}
                            disabled={saving}
                            aria-label={m.activo ? "Desactivar" : "Activar"}
                            style={{
                              minWidth: 72,
                              padding: "4px 8px",
                              borderRadius: 6,
                              border: m.activo ? "1px solid #16a34a" : "1px solid var(--border)",
                              background: m.activo ? "#16a34a" : "var(--bg)",
                              color: m.activo ? "#fff" : "var(--text)",
                              fontWeight: 700,
                              cursor: "pointer",
                              fontSize: "0.8rem",
                            }}
                          >
                            {m.activo ? "Activo" : "Inactivo"}
                          </button>
                        </td>
                        <td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{m.orden}</td>
                        <td style={{ display: "flex", gap: 6, justifyContent: "flex-end", flexWrap: "wrap" }}>
                          <button
                            type="button"
                            className="sal-link-btn"
                            onClick={() => startEdit(m)}
                            disabled={saving}
                            style={{ minHeight: 32, padding: "4px 8px", color: "var(--primary)" }}
                          >
                            Editar
                          </button>
                          <button
                            type="button"
                            className="sal-link-btn"
                            onClick={() => void handleEliminar(m)}
                            disabled={saving}
                            style={{ minHeight: 32, padding: "4px 8px" }}
                          >
                            Eliminar
                          </button>
                        </td>
                      </tr>
                    ))
                )}
              </tbody>
            </table>
          </div>

          {/* Form */}
          <form onSubmit={(e) => void handleGuardar(e)} style={{ display: "flex", flexDirection: "column", gap: 10, background: "var(--bg)", border: "0.5px solid var(--border)", borderRadius: 8, padding: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              <strong style={{ fontSize: "0.95rem" }}>{editingId !== null ? `Editando #${editingId}` : "Nuevo motivo"}</strong>
              {editingId !== null && (
                <button type="button" className="btn-secondary" onClick={resetForm} disabled={saving} style={{ minHeight: 32 }}>
                  Cancelar edición
                </button>
              )}
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
              <label className="sal-field" style={{ margin: 0 }}>
                <span className="sal-muted">Clave * (UPPER, sin espacios)</span>
                <input
                  value={clave}
                  onChange={(e) => setClave(e.target.value.toUpperCase().replace(/\s+/g, "_"))}
                  placeholder="EJ: FALTA_AUTORIZACION"
                  autoComplete="off"
                  required
                  maxLength={30}
                  style={{ fontFamily: "monospace" }}
                />
              </label>
              <label className="sal-field" style={{ margin: 0 }}>
                <span className="sal-muted">Orden</span>
                <input value={orden} onChange={(e) => setOrden(e.target.value.replace(/[^0-9-]/g, ""))} inputMode="numeric" placeholder="Ej 6" />
              </label>
            </div>

            <label className="sal-field" style={{ margin: 0 }}>
              <span className="sal-muted">Nombre *</span>
              <input value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Ej Falta de autorización" required maxLength={60} />
            </label>

            <label className="sal-toggle" style={{ alignSelf: "flex-start", cursor: "pointer" }}>
              <input type="checkbox" checked={activo} onChange={(e) => setActivo(e.target.checked)} />
              Activo (visible en combo de Atención)
            </label>

            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button type="submit" className="btn-primary" disabled={saving} style={{ flex: 1, minHeight: 44 }}>
                {saving ? "Guardando…" : editingId !== null ? "Guardar cambios" : "Crear motivo"}
              </button>
              <button type="button" className="btn-secondary" onClick={resetForm} disabled={saving} style={{ minHeight: 44 }}>
                Limpiar
              </button>
            </div>
            <p className="sub" style={{ margin: 0, fontSize: "0.78rem" }}>
              Tip: Clave queda UPPER. Si el motivo tiene usos en atenciones, Eliminar hará soft-delete (desactivar) en lugar de borrar. Desactivar oculta del combo pero preserva histórico.
            </p>
          </form>

          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <button type="button" className="btn-secondary" onClick={onClose} style={{ minHeight: 36 }}>
              Cerrar
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
