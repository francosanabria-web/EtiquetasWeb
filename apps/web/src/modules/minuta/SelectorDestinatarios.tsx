import type { Contacto } from "../../api/emailClient";

type Props = {
  contactos: Contacto[];
  seleccionados: string[];
  cargando: boolean;
  error: string | null;
  onToggle: (email: string) => void;
  onSeleccionarTodos: () => void;
  onLimpiar: () => void;
};

export default function SelectorDestinatarios({
  contactos,
  seleccionados,
  cargando,
  error,
  onToggle,
  onSeleccionarTodos,
  onLimpiar,
}: Props) {
  return (
    <section className="minuta-section">
      <div className="minuta-section-head">
        <h2>Destinatarios</h2>
        <div className="minuta-actions-inline">
          <button type="button" className="btn-ghost btn-sm" onClick={onSeleccionarTodos}>
            Todos
          </button>
          <button type="button" className="btn-ghost btn-sm" onClick={onLimpiar}>
            Ninguno
          </button>
        </div>
      </div>
      {cargando && <p className="minuta-hint">Cargando contactos desde master_codes…</p>}
      {error && <p className="error">{error}</p>}
      {!cargando && !error && contactos.length === 0 && (
        <p className="minuta-hint">No hay contactos en la hoja correos.</p>
      )}
      <ul className="minuta-contactos">
        {contactos.map((c) => {
          const checked = seleccionados.includes(c.email);
          return (
            <li key={c.id}>
              <label className="minuta-check">
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => onToggle(c.email)}
                />
                <span>
                  <strong>{c.etiqueta}</strong>
                  {c.etiqueta !== c.email && (
                    <span className="minuta-email-sub">{c.email}</span>
                  )}
                  {c.tipo && <span className="minuta-tipo-badge">{c.tipo}</span>}
                </span>
              </label>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
