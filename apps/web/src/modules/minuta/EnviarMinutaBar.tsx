type Props = {
  enviando: boolean;
  onEnviar: () => void;
  onAbandonar: () => void;
};

export default function EnviarMinutaBar({ enviando, onEnviar, onAbandonar }: Props) {
  return (
    <footer className="minuta-footer">
      <button type="button" className="btn-ghost" onClick={onAbandonar} disabled={enviando}>
        Abandonar reunión
      </button>
      <button type="button" className="btn-primary" onClick={onEnviar} disabled={enviando}>
        {enviando ? "Enviando…" : "Finalizar reunión y enviar"}
      </button>
    </footer>
  );
}
