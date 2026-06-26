import { useCallback, useEffect, useState } from "react";
import { ApiError, buscarCatalogo, crearEtiqueta, getPendientes } from "./api";
import type { CatalogoItem, Pedido, TipoEtiqueta } from "./types";

type Aviso = { tipo: "ok" | "error"; texto: string } | null;

function useSolicitante() {
  const [valor, setValor] = useState<string>(
    () => localStorage.getItem("solicitado_por") ?? ""
  );
  useEffect(() => {
    localStorage.setItem("solicitado_por", valor);
  }, [valor]);
  return [valor, setValor] as const;
}

export default function App() {
  const [tipo, setTipo] = useState<TipoEtiqueta>("codigo");
  const [solicitante, setSolicitante] = useSolicitante();
  const [aviso, setAviso] = useState<Aviso>(null);

  const mostrar = useCallback((a: Aviso) => {
    setAviso(a);
    if (a) window.setTimeout(() => setAviso(null), 4000);
  }, []);

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar-inner">
          <h1>🏷️ Etiquetas — Pañol</h1>
          <input
            className="solicitante"
            placeholder="¿Quién imprime? (ej. tablet-pañol)"
            value={solicitante}
            onChange={(e) => setSolicitante(e.target.value)}
          />
        </div>
      </header>

      <main className="contenido">
        <div className="seg">
          <button
            className={`seg-btn ${tipo === "codigo" ? "active" : ""}`}
            onClick={() => setTipo("codigo")}
          >
            🔎 Código
          </button>
          <button
            className={`seg-btn ${tipo === "simple" ? "active" : ""}`}
            onClick={() => setTipo("simple")}
          >
            ✍️ Rótulo simple
          </button>
        </div>

        {tipo === "simple" ? (
          <FormSimple solicitante={solicitante} onAviso={mostrar} />
        ) : (
          <FormCodigo solicitante={solicitante} onAviso={mostrar} />
        )}

        <ColaPendientes />
      </main>

      {aviso && <div className={`toast toast-${aviso.tipo}`}>{aviso.texto}</div>}
    </div>
  );
}

function CantidadInput({
  cantidad,
  setCantidad,
}: {
  cantidad: number;
  setCantidad: (n: number) => void;
}) {
  return (
    <div className="campo">
      <label>Cantidad de copias</label>
      <div className="stepper">
        <button type="button" onClick={() => setCantidad(Math.max(1, cantidad - 1))}>
          −
        </button>
        <input
          type="number"
          min={1}
          value={cantidad}
          onChange={(e) => setCantidad(Math.max(1, Number(e.target.value) || 1))}
        />
        <button type="button" onClick={() => setCantidad(cantidad + 1)}>
          +
        </button>
      </div>
    </div>
  );
}

function FormSimple({
  solicitante,
  onAviso,
}: {
  solicitante: string;
  onAviso: (a: Aviso) => void;
}) {
  const [texto, setTexto] = useState("");
  const [cantidad, setCantidad] = useState(1);
  const [escala, setEscala] = useState(1);
  const [enviando, setEnviando] = useState(false);

  const ESCALA_MIN = 0.5;
  const ESCALA_MAX = 3;
  const ESCALA_PASO = 0.25;
  const ajustarEscala = (delta: number) =>
    setEscala((e) => Math.round(Math.min(ESCALA_MAX, Math.max(ESCALA_MIN, e + delta)) * 100) / 100);

  const enviar = async () => {
    if (!texto.trim()) {
      onAviso({ tipo: "error", texto: "Escribí el texto de la etiqueta." });
      return;
    }
    setEnviando(true);
    try {
      const r = await crearEtiqueta({
        tipo: "simple",
        texto_libre: texto.trim(),
        cantidad,
        escala_fuente: escala,
        solicitado_por: solicitante || undefined,
      });
      onAviso({ tipo: "ok", texto: `Etiqueta #${r.id} enviada a la cola.` });
      setTexto("");
      setCantidad(1);
      setEscala(1);
    } catch (e) {
      onAviso({ tipo: "error", texto: e instanceof Error ? e.message : "Error al enviar." });
    } finally {
      setEnviando(false);
    }
  };

  return (
    <section className="card">
      <h2>Rótulo simple</h2>
      <p className="hint">Solo texto libre, sin código ni QR.</p>
      <div className="campo">
        <label>Texto</label>
        <textarea
          rows={3}
          placeholder="Ej: ZONA DE CARGA - NO ESTACIONAR"
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
        />
      </div>
      <div className="campo">
        <label>Tamaño de letra</label>
        <div className="stepper">
          <button
            type="button"
            onClick={() => ajustarEscala(-ESCALA_PASO)}
            disabled={escala <= ESCALA_MIN}
            title="Achicar letra"
          >
            A−
          </button>
          <span className="escala-valor">{Math.round(escala * 100)}%</span>
          <button
            type="button"
            onClick={() => ajustarEscala(ESCALA_PASO)}
            disabled={escala >= ESCALA_MAX}
            title="Agrandar letra"
          >
            A+
          </button>
        </div>
      </div>

      <CantidadInput cantidad={cantidad} setCantidad={setCantidad} />

      <div className="vista-previa simple-preview">
        <span style={{ fontSize: `${Math.round(22 * escala)}px` }}>
          {texto.trim() || "Vista previa del texto"}
        </span>
      </div>

      <button className="btn-primario" disabled={enviando} onClick={enviar}>
        {enviando ? "Enviando…" : "🖨️ Enviar a imprimir"}
      </button>
    </section>
  );
}

function FormCodigo({
  solicitante,
  onAviso,
}: {
  solicitante: string;
  onAviso: (a: Aviso) => void;
}) {
  const [codigo, setCodigo] = useState("");
  const [item, setItem] = useState<CatalogoItem | null>(null);
  const [cantidad, setCantidad] = useState(1);
  const [buscando, setBuscando] = useState(false);
  const [enviando, setEnviando] = useState(false);

  const buscar = async () => {
    const q = codigo.trim();
    if (!q) return;
    setBuscando(true);
    setItem(null);
    try {
      const encontrado = await buscarCatalogo(q);
      if (!encontrado) {
        onAviso({ tipo: "error", texto: `No se encontró el código "${q}".` });
      } else {
        setItem(encontrado);
      }
    } catch (e) {
      const msg =
        e instanceof ApiError && e.status === 503
          ? "El catálogo (Firebase) no está configurado en el servidor."
          : e instanceof Error
            ? e.message
            : "Error al buscar.";
      onAviso({ tipo: "error", texto: msg });
    } finally {
      setBuscando(false);
    }
  };

  const enviar = async () => {
    if (!item) return;
    setEnviando(true);
    try {
      const r = await crearEtiqueta({
        tipo: "codigo",
        codigo: item.codigo,
        descripcion: item.descripcion,
        ubicacion: item.ubicacion,
        qr_data: item.codigo,
        cantidad,
        solicitado_por: solicitante || undefined,
      });
      onAviso({ tipo: "ok", texto: `Etiqueta #${r.id} (${item.codigo}) enviada a la cola.` });
      setItem(null);
      setCodigo("");
      setCantidad(1);
    } catch (e) {
      onAviso({ tipo: "error", texto: e instanceof Error ? e.message : "Error al enviar." });
    } finally {
      setEnviando(false);
    }
  };

  return (
    <section className="card">
      <h2>Código reconocido</h2>
      <p className="hint">Buscá el código en el catálogo; la etiqueta lleva descripción, código y ubicación.</p>

      <div className="buscador">
        <input
          placeholder="Ingresá el código y Enter…"
          value={codigo}
          onChange={(e) => setCodigo(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void buscar();
          }}
          autoFocus
        />
        <button className="btn-secundario" disabled={buscando} onClick={buscar}>
          {buscando ? "Buscando…" : "Buscar"}
        </button>
      </div>

      {item && (
        <>
          <div className="vista-previa etq-real">
            <div className="etq">
              <div className="etq-desc">{item.descripcion}</div>
              <div className="etq-codigo">{item.codigo}</div>
              <div className="etq-ubic">
                <div className="etq-ubic-lbl">UBICACIÓN</div>
                <div className="etq-ubic-val">{item.ubicacion}</div>
              </div>
            </div>
          </div>

          <CantidadInput cantidad={cantidad} setCantidad={setCantidad} />

          <button className="btn-primario" disabled={enviando} onClick={enviar}>
            {enviando ? "Enviando…" : "🖨️ Enviar a imprimir"}
          </button>
        </>
      )}
    </section>
  );
}

function ColaPendientes() {
  const [pendientes, setPendientes] = useState<Pedido[]>([]);
  const [error, setError] = useState(false);

  useEffect(() => {
    let activo = true;
    const cargar = async () => {
      try {
        const p = await getPendientes();
        if (activo) {
          setPendientes(p);
          setError(false);
        }
      } catch {
        if (activo) setError(true);
      }
    };
    void cargar();
    const id = window.setInterval(cargar, 4000);
    return () => {
      activo = false;
      window.clearInterval(id);
    };
  }, []);

  return (
    <section className="card cola">
      <div className="cola-head">
        <h2>Cola pendiente</h2>
        <span className={`badge ${pendientes.length ? "" : "vacia"}`}>
          {pendientes.length}
        </span>
      </div>
      {error ? (
        <p className="hint error">No se puede contactar la API.</p>
      ) : pendientes.length === 0 ? (
        <p className="hint">Sin etiquetas pendientes. Todo impreso ✅</p>
      ) : (
        <ul className="lista-pendientes">
          {pendientes.map((p) => (
            <li key={p.id}>
              <span className="lp-id">#{p.id}</span>
              <span className="lp-tipo">{p.tipo === "simple" ? "Rótulo" : "Código"}</span>
              <span className="lp-detalle">
                {p.tipo === "simple" ? p.texto_libre : p.codigo}
              </span>
              <span className="lp-cant">×{p.cantidad}</span>
              {p.intentos > 0 && <span className="lp-reintento">reintento {p.intentos}</span>}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
