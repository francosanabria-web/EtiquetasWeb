import { useEffect, useMemo, useRef, useState } from "react";
import {
  ensureCatalogLoaded,
  filterArticulos,
  type ArticuloCatalogo,
} from "../../lib/articulosCatalog";

type Props = {
  value: string;
  onCodigoChange: (codigo: string) => void;
  onPick: (art: ArticuloCatalogo) => void;
  disabled?: boolean;
};

/**
 * Buscador de catálogo Firestore — misma lógica que AppPanolWeb
 * (ensureCatalogLoaded + filterArticulos sobre codigo/desc/alias).
 */
export default function BuscadorCatalogo({
  value,
  onCodigoChange,
  onPick,
  disabled,
}: Props) {
  const [q, setQ] = useState(value);
  const [catalog, setCatalog] = useState<ArticuloCatalogo[]>([]);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [abierto, setAbierto] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setQ(value);
  }, [value]);

  useEffect(() => {
    let cancel = false;
    setCargando(true);
    ensureCatalogLoaded()
      .then((lista) => {
        if (!cancel) setCatalog(lista);
      })
      .catch((e) => {
        if (!cancel) {
          setError(e instanceof Error ? e.message : "No se pudo cargar el catálogo.");
        }
      })
      .finally(() => {
        if (!cancel) setCargando(false);
      });
    return () => {
      cancel = true;
    };
  }, []);

  useEffect(() => {
    const onDoc = (ev: MouseEvent) => {
      if (!wrapRef.current?.contains(ev.target as Node)) setAbierto(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const { items, totalMatches } = useMemo(
    () => filterArticulos(catalog, q),
    [catalog, q],
  );

  return (
    <div className="sol-catalog" ref={wrapRef}>
      <label>
        Código (catálogo)
        <input
          type="search"
          value={q}
          disabled={disabled}
          placeholder={cargando ? "Cargando catálogo…" : "Buscar por código, descripción o alias"}
          autoComplete="off"
          onChange={(e) => {
            const v = e.target.value;
            setQ(v);
            onCodigoChange(v);
            setAbierto(true);
          }}
          onFocus={() => setAbierto(true)}
        />
      </label>
      {error && <p className="sol-hint sol-warn">{error}</p>}
      {!error && !cargando && catalog.length > 0 && (
        <p className="sol-hint">{catalog.length.toLocaleString()} artículos en memoria</p>
      )}
      {abierto && q.trim() && items.length > 0 && (
        <ul className="sol-catalog-list" role="listbox">
          {items.map((a) => (
            <li key={a.id}>
              <button
                type="button"
                className="sol-catalog-item"
                onClick={() => {
                  onPick(a);
                  setQ(a.codigo ?? "");
                  setAbierto(false);
                }}
              >
                <strong>{a.codigo || "—"}</strong>
                <span>{a.desc || ""}</span>
                {a.alias ? <em>{a.alias}</em> : null}
              </button>
            </li>
          ))}
          {totalMatches > items.length && (
            <li className="sol-hint">Mostrando {items.length} de {totalMatches}</li>
          )}
        </ul>
      )}
      {abierto && q.trim() && !cargando && items.length === 0 && (
        <p className="sol-hint">Sin coincidencias en catálogo. Podés seguir con descripción libre.</p>
      )}
    </div>
  );
}
