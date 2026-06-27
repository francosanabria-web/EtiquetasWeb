import { Link } from "react-router-dom";

export default function ModuloPlaceholder({ titulo }: { titulo: string }) {
  return (
    <div className="shell">
      <header className="top compact">
        <Link to="/" className="back">
          ← Inicio
        </Link>
        <h2>{titulo}</h2>
      </header>
      <div className="placeholder">
        <p>Este módulo se está integrando al shell principal.</p>
        <p className="sub">Próximo paso: migrar la app de pañol existente acá.</p>
      </div>
    </div>
  );
}
