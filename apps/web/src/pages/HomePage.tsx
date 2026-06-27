import { Link } from "react-router-dom";
import { etiquetaRol } from "../auth/demoUsers";
import { useAuth } from "../auth/AuthContext";
import { modulosParaRol, type ModuloDef } from "../config/modulos";

function TarjetaModulo({ mod }: { mod: ModuloDef }) {
  const contenido = (
    <>
      <span className="mod-icon">{mod.icono}</span>
      <h3>{mod.titulo}</h3>
      <p>{mod.descripcion}</p>
      {!mod.disponible && <span className="badge prox">Próximamente</span>}
    </>
  );

  if (!mod.disponible) {
    return <article className="mod-card disabled">{contenido}</article>;
  }

  if (mod.externo) {
    return (
      <a className="mod-card" href={mod.ruta} target="_blank" rel="noreferrer">
        {contenido}
        <span className="badge ext">Abrir módulo</span>
      </a>
    );
  }

  return (
    <Link className="mod-card" to={mod.ruta}>
      {contenido}
    </Link>
  );
}

export default function HomePage() {
  const { usuario, cerrarSesion } = useAuth();
  if (!usuario) return null;

  const modulos = modulosParaRol(usuario.rol);

  return (
    <div className="shell">
      <header className="top">
        <div>
          <h1>Bienvenido, {usuario.nombre}</h1>
          <p className="sub">
            Rol: <strong>{etiquetaRol(usuario.rol)}</strong> — elegí un módulo
          </p>
        </div>
        <button type="button" className="btn-ghost" onClick={cerrarSesion}>
          Cerrar sesión
        </button>
      </header>

      <section className="grid-modulos">
        {modulos.map((m) => (
          <TarjetaModulo key={m.id} mod={m} />
        ))}
      </section>

      <footer className="pie">
        Shell v0.1 — módulos se integran progresivamente en este portal.
      </footer>
    </div>
  );
}
