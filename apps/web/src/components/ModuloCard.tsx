import { Link } from "react-router-dom";
import type { ModuloNav } from "../config/navegacion";

type Props = {
  mod: ModuloNav;
};

export default function ModuloCard({ mod }: Props) {
  const contenido = (
    <>
      <span className="mod-icon">{mod.icono}</span>
      <h3>{mod.titulo}</h3>
      <p>{mod.descripcion}</p>
      {mod.tipo === "proximo" && <span className="badge prox">Próximamente</span>}
      {mod.tipo === "externo" && <span className="badge ext">Abrir módulo ↗</span>}
    </>
  );

  if (mod.tipo === "proximo") {
    return <article className="mod-card disabled">{contenido}</article>;
  }

  if (mod.tipo === "externo" && mod.href) {
    return (
      <a className="mod-card" href={mod.href} target="_blank" rel="noopener noreferrer">
        {contenido}
      </a>
    );
  }

  if (mod.ruta) {
    return (
      <Link className="mod-card" to={mod.ruta}>
        {contenido}
      </Link>
    );
  }

  return <article className="mod-card disabled">{contenido}</article>;
}
