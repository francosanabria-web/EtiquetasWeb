/**
 * IdealEditorModal — Editor of Caja Ideal with BuscadorCatalogo integration.
 * Each row: herramienta_codigo (BuscadorCatalogo), cantidad_minima, articulo_codigo display, remove.
 */

// Imported from shared — migrated via cajas-fase2-polish (was ../solicitudes/BuscadorCatalogo)
import BuscadorCatalogo from "../../components/shared/BuscadorCatalogo";
import type { ArticuloCatalogo } from "../../lib/articulosCatalog";
import { useState, type FormEvent } from "react";
import type { Ideal } from "../../api/cajasClient";
import { putIdeal } from "../../api/cajasClient";

type Row = {
  herramienta_codigo: string;
  cantidad_minima: number;
  articulo_codigo: string;
};

type Props = {
  ideal: Ideal | null;
  token: string;
  onClose: () => void;
  onSaved: (ideal: Ideal) => void;
};

export default function IdealEditorModal({ ideal, token, onClose, onSaved }: Props) {
  const [nombre, setNombre] = useState(ideal?.nombre ?? "");
  const [descripcion, setDescripcion] = useState(ideal?.descripcion ?? "");
  const [detalle, setDetalle] = useState<Row[]>(() => {
    if (ideal?.herramientas && ideal.herramientas.length > 0) {
      return ideal.herramientas.map((h) => ({
        herramienta_codigo: h.codigo,
        cantidad_minima: h.cantidad_minima,
        articulo_codigo: h.articulo_codigo ?? "",
      }));
    }
    return [{ herramienta_codigo: "", cantidad_minima: 1, articulo_codigo: "" }];
  });
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [dupErrorIdx, setDupErrorIdx] = useState<number | null>(null);

  const handleAdd = () => {
    setDetalle((prev) => [...prev, { herramienta_codigo: "", cantidad_minima: 1, articulo_codigo: "" }]);
  };

  const handleRemove = (idx: number) => {
    setDetalle((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleCodigoChange = (idx: number, value: string) => {
    setDetalle((prev) => {
      const next = [...prev];
      next[idx] = { ...next[idx], herramienta_codigo: value };
      return next;
    });
    setDupErrorIdx(null);
    setError(null);
  };

  const handlePick = (idx: number, art: ArticuloCatalogo) => {
    const codigo = (art.codigo ?? "").trim().toUpperCase();
    const artCodigo = (art.codigo ?? "").trim();
    setDetalle((prev) => {
      const next = [...prev];
      next[idx] = {
        ...next[idx],
        herramienta_codigo: codigo || artCodigo,
        articulo_codigo: artCodigo,
      };
      return next;
    });
    setDupErrorIdx(null);
    setError(null);
  };

  const handleCantidadChange = (idx: number, value: number) => {
    setDetalle((prev) => {
      const next = [...prev];
      next[idx] = { ...next[idx], cantidad_minima: value };
      return next;
    });
    setError(null);
  };

  const handleArticuloChange = (idx: number, value: string) => {
    setDetalle((prev) => {
      const next = [...prev];
      next[idx] = { ...next[idx], articulo_codigo: value };
      return next;
    });
  };

  const validate = (): string | null => {
    if (!nombre.trim()) return "El nombre es obligatorio.";
    if (detalle.length === 0) return "Debe agregar al menos una herramienta.";
    const seen = new Map<string, number>();
    for (let i = 0; i < detalle.length; i++) {
      const row = detalle[i];
      if (!row.herramienta_codigo.trim()) return `Fila ${i + 1}: el código es obligatorio.`;
      if (!Number.isInteger(row.cantidad_minima) || row.cantidad_minima <= 0)
        return `Fila ${i + 1}: cantidad mínima debe ser > 0.`;
      const norm = row.herramienta_codigo.trim().toUpperCase();
      if (seen.has(norm)) {
        const prevIdx = seen.get(norm)!;
        setDupErrorIdx(i);
        return `Herramienta duplicada: "${row.herramienta_codigo}" ya está en fila ${prevIdx + 1}.`;
      }
      seen.set(norm, i);
    }
    return null;
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setDupErrorIdx(null);
    const v = validate();
    if (v) {
      setError(v);
      return;
    }
    setSaving(true);
    try {
      const payload = {
        nombre: nombre.trim(),
        descripcion: descripcion.trim() ? descripcion.trim() : null,
        detalle: detalle.map((d) => ({
          herramienta_codigo: d.herramienta_codigo.trim().toUpperCase(),
          cantidad_minima: d.cantidad_minima,
          articulo_codigo: d.articulo_codigo.trim() ? d.articulo_codigo.trim() : null,
        })),
      };
      const saved = await putIdeal(token, payload);
      onSaved(saved);
      onClose();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Error al guardar.";
      const low = msg.toLowerCase();
      if (low.includes("ya asignada") || low.includes("duplicate") || low.includes("409") || low.includes("duplicado")) {
        setError("Herramienta ya asignada a esta Caja Ideal — revisá duplicados.");
      } else if (low.includes("no autorizado") || low.includes("401")) {
        setError("No autorizado — verificá tu sesión.");
      } else {
        setError(msg);
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <form className="sol-form" onSubmit={handleSubmit}>
      <h2>{ideal?.id ? "Editar Caja Ideal" : "Definir Caja Ideal"}</h2>
      {error && (
        <p className="error" role="status" style={{ whiteSpace: "pre-wrap" }}>
          {error}
        </p>
      )}

      <label>
        Nombre *
        <input
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
          placeholder="Ej: Caja Ideal Técnica 2025"
          required
        />
      </label>

      <label>
        Descripción
        <input
          value={descripcion}
          onChange={(e) => setDescripcion(e.target.value)}
          placeholder="Descripción (opcional)"
        />
      </label>

      <div style={{ marginTop: "0.75rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
          <strong>Herramientas (detalle)</strong>
          <button type="button" className="btn-ghost btn-sm" onClick={handleAdd}>
            + Agregar herramienta
          </button>
        </div>

        {detalle.length === 0 && <p className="sol-hint">Sin herramientas. Agregá al menos una.</p>}

        <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", maxHeight: "42vh", overflowY: "auto", paddingRight: "0.25rem" }}>
          {detalle.map((row, idx) => (
            <div
              key={idx}
              style={{
                border: "1px solid #e5e7eb",
                borderRadius: 8,
                padding: "0.75rem",
                background: dupErrorIdx === idx ? "#fff1f2" : "#fff",
                display: "flex",
                flexDirection: "column",
                gap: "0.5rem",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <strong style={{ fontSize: "0.9rem" }}>Ítem {idx + 1}</strong>
                <button
                  type="button"
                  className="btn-ghost btn-sm"
                  onClick={() => handleRemove(idx)}
                  disabled={detalle.length <= 1}
                  title={detalle.length <= 1 ? "Debe quedar al menos un ítem" : "Eliminar"}
                  style={{ color: "#b91c1c" }}
                >
                  ✕ Quitar
                </button>
              </div>

              <BuscadorCatalogo
                value={row.herramienta_codigo}
                onCodigoChange={(v) => handleCodigoChange(idx, v)}
                onPick={(art) => handlePick(idx, art)}
              />

              <div className="sol-grid-2">
                <label>
                  Cantidad mínima *
                  <input
                    type="number"
                    min={1}
                    step={1}
                    value={row.cantidad_minima}
                    onChange={(e) => handleCantidadChange(idx, parseInt(e.target.value, 10) || 0)}
                    required
                  />
                </label>
                <label>
                  Código artículo
                  <input
                    value={row.articulo_codigo}
                    onChange={(e) => handleArticuloChange(idx, e.target.value)}
                    placeholder="Autocompletado desde catálogo"
                  />
                </label>
              </div>

              {row.herramienta_codigo && (
                <p className="sol-hint" style={{ margin: 0, fontSize: "0.8rem" }}>
                  Código normalizado: <strong>{row.herramienta_codigo.trim().toUpperCase()}</strong>
                  {row.articulo_codigo ? <> — artículo: {row.articulo_codigo}</> : null}
                </p>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="sol-form-actions">
        <button type="button" className="btn-ghost" onClick={onClose} disabled={saving}>
          Cancelar
        </button>
        <button type="submit" className="btn-primary" disabled={saving}>
          {saving ? "Guardando…" : ideal?.id ? "Actualizar Caja Ideal" : "Crear Caja Ideal"}
        </button>
      </div>
    </form>
  );
}
