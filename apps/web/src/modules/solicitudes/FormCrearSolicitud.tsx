import { useEffect, useState, type FormEvent } from "react";
import type { Rol } from "../../config/navegacion";
import {
  crearSolicitud,
  uploadArchivo,
  type CatalogosSolicitudes,
  type Solicitud,
  type SolicitudTipo,
} from "../../api/solicitudesClient";
import BuscadorCatalogo from "../../components/shared/BuscadorCatalogo";

type Props = {
  catalogos: CatalogosSolicitudes;
  rol: Rol;
  creadoPor: string;
  tipoInicial?: SolicitudTipo;
  onCreada: (s: Solicitud) => void;
  onCancelar: () => void;
};

type ItemForm = {
  key: string;
  codigo: string;
  descripcion: string;
  cantidad: string;
  unidad: string;
  area: string;
  imagenFile: File | null;
};

const puedeAdmin = (rol: Rol) => rol === "admin" || rol === "panol";

function nuevoItem(): ItemForm {
  return {
    key: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    codigo: "",
    descripcion: "",
    cantidad: "1",
    unidad: "",
    area: "",
    imagenFile: null,
  };
}

export default function FormCrearSolicitud({
  catalogos,
  rol,
  creadoPor,
  tipoInicial = "normal",
  onCreada,
  onCancelar,
}: Props) {
  const admin = puedeAdmin(rol);
  const [tipo, setTipo] = useState<SolicitudTipo>(tipoInicial);
  const [cuenta, setCuenta] = useState(catalogos.cuentas_contables[0] ?? "");
  const [solicitante, setSolicitante] = useState("");
  const [proveedor, setProveedor] = useState("");
  const [notas, setNotas] = useState("");
  const [remitoNro, setRemitoNro] = useState("");
  const [presupuestoNro, setPresupuestoNro] = useState("");
  const [remitoFile, setRemitoFile] = useState<File | null>(null);
  const [presupuestoFile, setPresupuestoFile] = useState<File | null>(null);
  const [items, setItems] = useState<ItemForm[]>([nuevoItem()]);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setTipo(tipoInicial);
  }, [tipoInicial]);

  const setItem = (key: string, patch: Partial<ItemForm>) => {
    setItems((prev) => prev.map((it) => (it.key === key ? { ...it, ...patch } : it)));
  };

  const enviar = async (e: FormEvent) => {
    e.preventDefault();
    if (tipo === "tr" && !proveedor.trim()) {
      setError("En un TR el proveedor es obligatorio.");
      return;
    }
    setGuardando(true);
    setError(null);
    try {
      let remito_archivo = "";
      let presupuesto_archivo = "";
      if (tipo === "tr" && remitoFile) {
        const up = await uploadArchivo(remitoFile, "remito");
        remito_archivo = up.path;
      }
      if (tipo === "tr" && presupuestoFile) {
        const up = await uploadArchivo(presupuestoFile, "presupuesto");
        presupuesto_archivo = up.path;
      }

      const itemsPayload = [];
      for (const it of items) {
        let imagen_path = "";
        if (it.imagenFile) {
          const up = await uploadArchivo(it.imagenFile, "imagen");
          imagen_path = up.path;
        }
        itemsPayload.push({
          codigo: it.codigo.trim(),
          descripcion: it.descripcion.trim(),
          cantidad: Number(it.cantidad),
          unidad: admin ? it.unidad : it.unidad,
          area: it.area.trim(),
          imagen_path,
        });
      }

      const s = await crearSolicitud({
        tipo,
        cuenta_contable: cuenta,
        solicitante: solicitante.trim(),
        proveedor: proveedor.trim(),
        notas: notas.trim(),
        remito_nro: tipo === "tr" ? remitoNro.trim() : "",
        remito_archivo,
        presupuesto_nro: tipo === "tr" ? presupuestoNro.trim() : "",
        presupuesto_archivo,
        creado_por: creadoPor,
        estado: "en_proceso",
        rol,
        items: itemsPayload,
      });
      onCreada(s);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo crear la solicitud.");
    } finally {
      setGuardando(false);
    }
  };

  return (
    <form className="sol-form" onSubmit={enviar}>
      <h2>Crear solicitud</h2>
      {error && (
        <p className="error" role="status">
          {error}
        </p>
      )}

      <div className="sol-tipo-row" role="group" aria-label="Tipo">
        {catalogos.tipos.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`sol-tipo-btn${tipo === t.id ? " active" : ""}`}
            onClick={() => setTipo(t.id as SolicitudTipo)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <p className="sol-hint">
        El Nº {tipo === "tr" ? "TR" : "de pedido"} se asigna automáticamente al guardar (
        {tipo === "tr" ? "TR-####" : "P-####"}).
      </p>

      <div className="sol-grid-2">
        <label>
          Cuenta contable *
          <select required value={cuenta} onChange={(e) => setCuenta(e.target.value)}>
            {catalogos.cuentas_contables.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
        <label>
          Solicitante *
          <input
            required
            value={solicitante}
            onChange={(e) => setSolicitante(e.target.value)}
            placeholder="Nombre y apellido"
          />
        </label>
      </div>

      <label>
        Proveedor {tipo === "tr" ? "*" : "(opcional)"}
        <input
          list="sol-proveedores-sugeridos"
          required={tipo === "tr"}
          value={proveedor}
          onChange={(e) => setProveedor(e.target.value)}
          placeholder="Ej. ACME S.A."
        />
      </label>
      <datalist id="sol-proveedores-sugeridos">
        {catalogos.proveedores.map((p) => (
          <option key={p} value={p} />
        ))}
      </datalist>

      <fieldset className="sol-fieldset">
        <legend>Ítems del pedido</legend>
        <p className="sol-hint">
          Un pedido puede tener varios ítems. El código es opcional (catálogo). Área/máquina indica
          dónde se usará el insumo, repuesto o servicio.
        </p>

        {items.map((it, idx) => (
          <div key={it.key} className="sol-item-card">
            <div className="sol-item-head">
              <strong>Ítem {idx + 1}</strong>
              {items.length > 1 && (
                <button
                  type="button"
                  className="btn-ghost btn-sm"
                  onClick={() => setItems((prev) => prev.filter((x) => x.key !== it.key))}
                >
                  Quitar
                </button>
              )}
            </div>

            <BuscadorCatalogo
              value={it.codigo}
              onCodigoChange={(codigo) => setItem(it.key, { codigo })}
              onPick={(a) =>
                setItem(it.key, {
                  codigo: a.codigo ?? "",
                  descripcion: a.desc ?? it.descripcion,
                })
              }
            />

            <label>
              Descripción *
              <input
                required
                value={it.descripcion}
                onChange={(e) => setItem(it.key, { descripcion: e.target.value })}
              />
            </label>

            <div className="sol-grid-3">
              <label>
                Cantidad *
                <input
                  required
                  type="number"
                  min="0.01"
                  step="any"
                  value={it.cantidad}
                  onChange={(e) => setItem(it.key, { cantidad: e.target.value })}
                />
              </label>
              <label>
                Unidad
                <select
                  value={it.unidad}
                  onChange={(e) => setItem(it.key, { unidad: e.target.value })}
                  disabled={!admin}
                >
                  <option value="">—</option>
                  {catalogos.unidades_medida.map((u) => (
                    <option key={u} value={u}>
                      {u}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Área / máquina *
                <input
                  required
                  list="sol-areas-sugeridas"
                  value={it.area}
                  onChange={(e) => setItem(it.key, { area: e.target.value })}
                  placeholder="Ej. Compresor 2, Edificio, etc."
                />
              </label>
            </div>

            <label>
              Imagen (opcional)
              <input
                type="file"
                accept="image/*"
                onChange={(e) => setItem(it.key, { imagenFile: e.target.files?.[0] ?? null })}
              />
            </label>
          </div>
        ))}

        <datalist id="sol-areas-sugeridas">
          {catalogos.areas.map((a) => (
            <option key={a} value={a} />
          ))}
        </datalist>

        <button type="button" className="btn-ghost" onClick={() => setItems((p) => [...p, nuevoItem()])}>
          + Agregar ítem
        </button>
      </fieldset>

      {tipo === "tr" && (
        <fieldset className="sol-fieldset">
          <legend>Datos TR</legend>
          <p className="sol-hint">Remito y presupuesto los puede cargar cualquier usuario.</p>
          <label>
            Nº remito
            <input value={remitoNro} onChange={(e) => setRemitoNro(e.target.value)} />
          </label>
          <label>
            Archivo remito
            <input
              type="file"
              accept="image/*,.pdf"
              onChange={(e) => setRemitoFile(e.target.files?.[0] ?? null)}
            />
          </label>
          <label>
            Nº presupuesto
            <input value={presupuestoNro} onChange={(e) => setPresupuestoNro(e.target.value)} />
          </label>
          <label>
            Archivo presupuesto
            <input
              type="file"
              accept="image/*,.pdf"
              onChange={(e) => setPresupuestoFile(e.target.files?.[0] ?? null)}
            />
          </label>
        </fieldset>
      )}

      <label>
        Notas
        <textarea value={notas} onChange={(e) => setNotas(e.target.value)} rows={2} />
      </label>

      <div className="sol-form-actions">
        <button type="button" className="btn-ghost" onClick={onCancelar} disabled={guardando}>
          Cancelar
        </button>
        <button type="submit" className="btn-primary" disabled={guardando}>
          {guardando ? "Guardando…" : "Crear solicitud"}
        </button>
      </div>
    </form>
  );
}
