import { useEffect, useMemo, useState } from "react";
import { actualizarAlias, buscarArticulos, fmtNum, fmtPesos, type ArticuloSalida } from "../../api/salidasClient";

type Props = {
  open: boolean;
  onClose: () => void;
  onSelect: (art: ArticuloSalida) => void;
};

export default function MaestroStockModal({ open, onClose, onSelect }: Props) {
  const [q, setQ] = useState("");
  const [items, setItems] = useState<ArticuloSalida[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const pageSize = 15;

  // Alias editing state
  const [editingCodigo, setEditingCodigo] = useState<string | null>(null);
  const [draftAlias, setDraftAlias] = useState("");
  const [savingAlias, setSavingAlias] = useState(false);
  const [aliasError, setAliasError] = useState<string | null>(null);

  const qTrim = useMemo(() => q.trim(), [q]);

  useEffect(() => {
    if (!open) return;
    setQ("");
    setItems([]);
    setError(null);
    setPage(0);
    setEditingCodigo(null);
    setDraftAlias("");
    setAliasError(null);
  }, [open]);

  const fetchItems = async (term: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await buscarArticulos({ q: term || undefined, limite: 50 });
      setItems(res.items || []);
      setPage(0);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo buscar.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!open) return;
    let cancel = false;
    const t = window.setTimeout(() => {
      if (cancel) return;
      void fetchItems(qTrim);
    }, 320);
    return () => {
      cancel = true;
      window.clearTimeout(t);
    };
  }, [open, qTrim]);

  useEffect(() => {
    if (!open) return;
    function onKey(ev: KeyboardEvent) {
      if (ev.key === "Escape" && editingCodigo === null) onClose();
      if (ev.key === "Escape" && editingCodigo !== null) setEditingCodigo(null);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose, editingCodigo]);

  const startEdit = (art: ArticuloSalida) => {
    setEditingCodigo(art.codigo);
    setDraftAlias(art.alias ?? "");
    setAliasError(null);
  };

  const cancelEdit = () => {
    setEditingCodigo(null);
    setDraftAlias("");
    setAliasError(null);
  };

  const saveAlias = async (art: ArticuloSalida) => {
    const val = draftAlias.trim();
    if (val.length > 300) {
      setAliasError("Máximo 300 caracteres.");
      return;
    }
    setSavingAlias(true);
    setAliasError(null);
    try {
      const updated = await actualizarAlias(art.codigo, val === "" ? null : val);
      // Update local list
      setItems((prev) => prev.map((it) => (it.codigo === art.codigo ? { ...it, alias: updated.alias ?? (val === "" ? null : val) } : it)));
      setEditingCodigo(null);
    } catch (e) {
      setAliasError(e instanceof Error ? e.message : "No se pudo guardar el alias.");
    } finally {
      setSavingAlias(false);
    }
  };

  if (!open) return null;

  const totalPages = Math.max(1, Math.ceil(items.length / pageSize));
  const safePage = Math.min(page, totalPages - 1);
  const pageItems = items.slice(safePage * pageSize, (safePage + 1) * pageSize);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Maestro de stock"
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(15,23,42,0.48)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 65,
        padding: 16,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "var(--surface, #fff)",
          border: "0.5px solid var(--border, #e2e8f0)",
          borderRadius: 12,
          width: "min(820px, 96vw)",
          maxHeight: "90vh",
          overflow: "auto",
          boxShadow: "0 20px 60px rgba(0,0,0,0.22)",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <div style={{ padding: "14px 16px 0", display: "flex", justifyContent: "space-between", gap: 12, alignItems: "start" }}>
          <div>
            <h2 style={{ margin: 0, fontFamily: "var(--font-display)", fontSize: "1.15rem" }}>🔍 Maestro de stock</h2>
            <p className="sub" style={{ margin: "4px 0 0" }}>
              Buscá por código, descripción, <strong>alias</strong> o ubicación. F3 activo. Seleccioná para cargar en Salidas.
            </p>
          </div>
          <button type="button" className="btn-secondary" onClick={onClose} aria-label="Cerrar" style={{ minHeight: 36 }}>
            ✕
          </button>
        </div>

        <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 10, flex: 1, minHeight: 0 }}>
          <div style={{ display: "flex", gap: 8 }}>
            <input
              autoFocus
              value={q}
              onChange={(e) => setQ(e.target.value.toUpperCase())}
              placeholder="Código, descripción, alias o ubicación (ej: T10, TORNILLO, DEMO-001)"
              aria-label="Buscar maestro"
              style={{
                flex: 1,
                font: "inherit",
                color: "var(--text)",
                background: "var(--bg)",
                border: "0.5px solid var(--border)",
                borderRadius: 8,
                padding: "10px 12px",
                minHeight: 44,
              }}
            />
            <button type="button" className="btn-secondary" onClick={() => setQ("")} disabled={!q} style={{ minHeight: 44 }}>
              Limpiar
            </button>
          </div>

          {error && (
            <p className="error" role="alert" style={{ margin: 0 }}>
              {error}
            </p>
          )}
          {loading && <p className="sub" style={{ margin: 0 }}>Buscando…</p>}

          {!loading && items.length === 0 && !error && (
            <p className="sub" style={{ margin: 0, padding: "12px 0", textAlign: "center" }}>
              Sin resultados para “{qTrim || "—"}”. Probá otro código, alias o descripción.
            </p>
          )}

          {items.length > 0 && (
            <>
              <div style={{ flex: 1, overflow: "auto", border: "0.5px solid var(--border)", borderRadius: 8 }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.88rem" }}>
                  <thead style={{ position: "sticky", top: 0, background: "var(--surface)", zIndex: 1 }}>
                    <tr>
                      <th style={{ textAlign: "left", padding: "8px 10px", borderBottom: "0.5px solid var(--border)", fontSize: "0.75rem", textTransform: "uppercase", color: "var(--muted)" }}>Código</th>
                      <th style={{ textAlign: "left", padding: "8px 10px", borderBottom: "0.5px solid var(--border)", fontSize: "0.75rem", textTransform: "uppercase", color: "var(--muted)" }}>Descripción</th>
                      <th style={{ textAlign: "left", padding: "8px 10px", borderBottom: "0.5px solid var(--border)", fontSize: "0.75rem", textTransform: "uppercase", color: "var(--muted)" }}>Alias</th>
                      <th style={{ textAlign: "left", padding: "8px 10px", borderBottom: "0.5px solid var(--border)", fontSize: "0.75rem", textTransform: "uppercase", color: "var(--muted)" }}>Ubic.</th>
                      <th style={{ textAlign: "right", padding: "8px 10px", borderBottom: "0.5px solid var(--border)", fontSize: "0.75rem", textTransform: "uppercase", color: "var(--muted)" }}>Stock</th>
                      <th style={{ textAlign: "right", padding: "8px 10px", borderBottom: "0.5px solid var(--border)", fontSize: "0.75rem", textTransform: "uppercase", color: "var(--muted)" }}>P. unit.</th>
                      <th style={{ padding: "8px 10px", borderBottom: "0.5px solid var(--border)" }}></th>
                    </tr>
                  </thead>
                  <tbody>
                    {pageItems.map((a) => (
                      <tr key={a.codigo} style={{ borderBottom: "0.5px solid var(--border)" }}>
                        <td style={{ padding: "8px 10px", fontWeight: 700 }}>{a.codigo}</td>
                        <td style={{ padding: "8px 10px", maxWidth: 260, wordBreak: "break-word" }}>{a.descripcion}</td>
                        <td style={{ padding: "8px 10px", maxWidth: 160 }}>
                          {editingCodigo === a.codigo ? (
                            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                              <input
                                autoFocus
                                value={draftAlias}
                                onChange={(e) => setDraftAlias(e.target.value)}
                                placeholder="Alias (ej: T10)"
                                maxLength={300}
                                aria-label={`Alias para ${a.codigo}`}
                                style={{
                                  font: "inherit",
                                  fontSize: "0.85rem",
                                  padding: "6px 8px",
                                  border: "0.5px solid var(--border)",
                                  borderRadius: 6,
                                  background: "var(--bg)",
                                  color: "var(--text)",
                                  minWidth: 120,
                                }}
                              />
                              {aliasError && <span style={{ color: "var(--danger, #dc2626)", fontSize: "0.75rem" }}>{aliasError}</span>}
                              <div style={{ display: "flex", gap: 6 }}>
                                <button
                                  type="button"
                                  className="btn-primary"
                                  disabled={savingAlias}
                                  onClick={() => void saveAlias(a)}
                                  style={{ minHeight: 28, padding: "4px 10px", fontSize: "0.78rem" }}
                                >
                                  {savingAlias ? "Guardando…" : "Guardar"}
                                </button>
                                <button
                                  type="button"
                                  className="btn-secondary"
                                  disabled={savingAlias}
                                  onClick={cancelEdit}
                                  style={{ minHeight: 28, padding: "4px 10px", fontSize: "0.78rem" }}
                                >
                                  Cancelar
                                </button>
                              </div>
                            </div>
                          ) : (
                            <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                              <span style={{ fontWeight: a.alias ? 600 : 400, color: a.alias ? "var(--text)" : "var(--muted)", wordBreak: "break-word" }}>
                                {a.alias || "—"}
                              </span>
                              <button
                                type="button"
                                className="btn-ghost"
                                onClick={() => startEdit(a)}
                                title={a.alias ? "Editar alias" : "Agregar alias"}
                                style={{ minHeight: 24, padding: "2px 8px", fontSize: "0.75rem", border: "0.5px solid var(--border)", borderRadius: 6, background: "var(--surface)" }}
                              >
                                {a.alias ? "Editar" : "Alias"}
                              </button>
                            </div>
                          )}
                        </td>
                        <td style={{ padding: "8px 10px" }}>{a.ubicacion || "—"}</td>
                        <td style={{ padding: "8px 10px", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{fmtNum(a.stock_actual)}</td>
                        <td style={{ padding: "8px 10px", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{fmtPesos(a.precio_unitario)}</td>
                        <td style={{ padding: "6px 10px", textAlign: "right" }}>
                          <button
                            type="button"
                            className="btn-primary"
                            onClick={() => {
                              onSelect(a);
                              onClose();
                            }}
                            style={{ minHeight: 32, padding: "6px 12px", fontSize: "0.82rem" }}
                            disabled={editingCodigo === a.codigo}
                          >
                            Seleccionar
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                <span className="sub" style={{ margin: 0, fontSize: "0.85rem" }}>
                  {items.length} resultado(s) · Página {safePage + 1} de {totalPages}
                </span>
                <div style={{ display: "flex", gap: 8 }}>
                  <button type="button" className="btn-secondary" disabled={safePage === 0} onClick={() => setPage((p) => Math.max(0, p - 1))} style={{ minHeight: 36 }}>
                    Anterior
                  </button>
                  <button type="button" className="btn-secondary" disabled={safePage + 1 >= totalPages} onClick={() => setPage((p) => p + 1)} style={{ minHeight: 36 }}>
                    Siguiente
                  </button>
                </div>
              </div>
            </>
          )}

          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 4 }}>
            <button type="button" className="btn-secondary" onClick={onClose} style={{ minHeight: 40 }}>
              Cerrar
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
